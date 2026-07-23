"""
Strips HTML-formatted email bodies down to plain text.
Order-confirmation emails are almost always HTML (tables, styling, tracking
pixels, footer boilerplate) - feeding raw HTML to the LLM wastes tokens and
adds noise the extraction prompt has to fight through.
"""

import re

from bs4 import BeautifulSoup

# Matches Indian 6-digit PIN codes - a reliable signal that a line contains
# a physical address (restaurant or, more sensitively, the delivery/home
# address). We redact the whole line rather than trying to surgically keep
# part of it, since delivery addresses often span multiple comma-separated
# fragments before the pincode.
_PINCODE_LINE_PATTERN = re.compile(r".*\b\d{6}\b.*")


def redact_addresses(text):
    """
    Strip out any line containing what looks like a full address (signalled
    by a 6-digit PIN code). This is a privacy safeguard: Swiggy/Zomato order
    emails include the delivery address, which is the user's home address -
    we never want that persisted to disk, logged, or sent to the LLM.
    Restaurant name (needed for classification) is captured separately and
    doesn't depend on the address line.
    """
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        if _PINCODE_LINE_PATTERN.match(line):
            cleaned.append("[address redacted]")
        else:
            cleaned.append(line)
    return "\n".join(cleaned)


def html_to_text(html):
    """Convert an HTML email body to clean, whitespace-collapsed plain text."""
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # Drop elements that never contain useful order content
    for tag in soup(["script", "style", "img", "head", "meta", "link"]):
        tag.decompose()

    text = soup.get_text(separator="\n")

    # Collapse repeated blank lines / excess whitespace left behind by tables
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def truncate_for_llm(text, max_chars=6000):
    """
    Safety cap so a single mail with a huge inline promo section doesn't
    blow past the LLM's context window. Order details are almost always in
    the first portion of the email; truncate rather than fail.
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated]"


# --- Swiggy-specific distillation ---
# Real Swiggy order emails follow a consistent section structure:
#   ORDER JOURNEY  -> restaurant name, [address], order timestamp,
#                      delivery person name, [address], delivery timestamp
#   BILL DETAILS   -> item lines (name, then price on next line), followed
#                      by fee/discount/tax lines, then "Paid Via X" + total
#   Disclaimer...  -> footer boilerplate we don't need
# We use these section headers as anchors rather than hardcoding line
# positions, since a few extra promo lines at the top/bottom shouldn't
# break parsing.

_DATE_TIME_PATTERN = re.compile(r"^[A-Za-z]{3}\s+\d{1,2},\s+\d{1,2}:\d{2}\s?[APap][Mm]$")
_PRICE_PATTERN = re.compile(r"^-?\s*₹[\d,]+(\.\d+)?$")
_NON_ITEM_LABELS = {
    "restaurant packaging",
    "platform fee with gst",
    "discount applied",
    "delivery fee (free with swiggy one)",
    "taxes",
}


def _find_line_index(lines, marker):
    for i, line in enumerate(lines):
        if line.strip().lower() == marker.lower():
            return i
    return None


def distill_order_text(text):
    """
    Parse a redacted, HTML-stripped Swiggy order email down to just:
    restaurant name, order time, delivery time, item lines, total paid.
    Drops promo banners, fee/discount/tax breakdown, and footer boilerplate.

    Returns None if the expected section markers ("ORDER JOURNEY" /
    "BILL DETAILS") aren't found. This happens for Swiggy-family emails
    that aren't standard food-delivery orders - Instamart (groceries),
    Dineout (reservations), etc. use different templates. For MVP scope
    we treat those as unsupported rather than guessing: sending
    unrecognized raw HTML-stripped text to a small local LLM produces
    hallucinated dates/restaurant names rather than a clean failure, which
    is worse than just skipping the email.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    idx_journey = _find_line_index(lines, "ORDER JOURNEY")
    idx_bill = _find_line_index(lines, "BILL DETAILS")

    if idx_journey is None or idx_bill is None:
        return None

    idx_disclaimer = None
    for i, line in enumerate(lines):
        if line.lower().startswith("disclaimer"):
            idx_disclaimer = i
            break
    bill_end = idx_disclaimer if idx_disclaimer is not None else len(lines)

    # --- Restaurant name + order/delivery timestamps ---
    journey_lines = [l for l in lines[idx_journey + 1 : idx_bill] if l != "[address redacted]"]
    timestamps = [l for l in journey_lines if _DATE_TIME_PATTERN.match(l)]
    non_timestamps = [l for l in journey_lines if not _DATE_TIME_PATTERN.match(l)]

    restaurant_name = non_timestamps[0] if non_timestamps else "Unknown"
    order_time = timestamps[0] if timestamps else ""
    delivery_time = timestamps[-1] if timestamps else ""

    # --- Item lines + total paid ---
    bill_lines = lines[idx_bill + 1 : bill_end]
    items = []
    total_paid = ""
    i = 0
    while i < len(bill_lines):
        line = bill_lines[i]
        low = line.lower()

        if any(low.startswith(label) for label in _NON_ITEM_LABELS) or low == "free":
            i += 1
            continue

        if low.startswith("paid via"):
            if i + 1 < len(bill_lines) and _PRICE_PATTERN.match(bill_lines[i + 1]):
                total_paid = bill_lines[i + 1]
            i += 2
            continue

        # item name followed by a price line = a real order item
        if i + 1 < len(bill_lines) and _PRICE_PATTERN.match(bill_lines[i + 1]):
            items.append((line, bill_lines[i + 1]))
            i += 2
        else:
            i += 1  # unrecognized line (e.g. a stray discount amount) - drop

    result = [f"Restaurant: {restaurant_name}"]
    if order_time:
        result.append(f"Order Time: {order_time}")
    if delivery_time:
        result.append(f"Delivery Time: {delivery_time}")
    result.append("Items:")
    for name, price in items:
        result.append(f"  {name} - {price}")
    if total_paid:
        result.append(f"Total Paid: {total_paid}")

    return "\n".join(result)


if __name__ == "__main__":
    sample_html = """
    <html><body>
      <style>.x{color:red}</style>
      <h2>Order Delivered</h2>
      <table><tr><td>Chicken Biryani x2</td><td>Rs 450</td></tr></table>
      <p>Thank you for ordering!</p>
      <img src="tracker.png">
    </body></html>
    """
    cleaned = html_to_text(sample_html)
    print(cleaned)
