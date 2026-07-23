"""
Distiller for Swiggy Instamart (grocery/quick-commerce) order emails.
Structurally different from Swiggy's food-delivery emails
(ingestion/html_clean.py's distill_order_text): different section headers,
a leading rather than trailing quantity marker, no store/restaurant name,
and no order timestamp anywhere in the email body.

Output is normalized to the SAME intermediate text shape as the food
distiller ("Item Name x1 - ₹price", "Restaurant: X", "Total Paid: ₹Y") so
the existing extraction prompt works for both platforms unchanged - one
extractor, multiple distillers feeding it a common format.
"""

import re
from email.utils import parsedate_to_datetime

_ITEM_LINE_PATTERN = re.compile(r"^(\d+)\s*x\s+(.+)$", re.IGNORECASE)
_PRICE_PATTERN = re.compile(r"^-?\s*₹[\d,]+(\.\d+)?$")
_ZERO_PRICES = {"₹0.00", "₹0"}


def _find_line_index(lines, marker):
    for i, line in enumerate(lines):
        if line.strip().lower() == marker.lower():
            return i
    return None


def _resolve_order_date(email_date_header):
    """
    Instamart emails don't include an order date/time anywhere in the body
    - so we compute it deterministically from Gmail's own Date header
    instead of asking the LLM to infer or guess a date it doesn't actually
    have information for in the text it's given.
    """
    if not email_date_header:
        return None
    try:
        dt = parsedate_to_datetime(email_date_header)
        return dt.strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def distill_instamart_text(text, email_date_header=None):
    """
    Parse a redacted, HTML-stripped Instamart order email down to just:
    order date (from Gmail's header, not the body), item lines, grand
    total. Returns None if the expected section markers aren't found -
    safer to skip an unrecognized format than guess.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    idx_items = _find_line_index(lines, "Order Items")
    idx_summary = _find_line_index(lines, "Order Summary")

    if idx_items is None or idx_summary is None:
        return None

    # --- Items: "N x Item Name" then price on the next line ---
    item_lines = lines[idx_items + 1 : idx_summary]
    items = []
    i = 0
    while i < len(item_lines):
        line = item_lines[i]
        match = _ITEM_LINE_PATTERN.match(line)
        if match and i + 1 < len(item_lines) and _PRICE_PATTERN.match(item_lines[i + 1]):
            quantity, name = match.group(1), match.group(2)
            price_str = item_lines[i + 1]
            # Skip promotional zero-price inserts (flyers/ads bundled into
            # the order) - not a real purchase
            if price_str.strip() not in _ZERO_PRICES:
                # Normalize to the food distiller's "Name xN" convention
                items.append((f"{name} x{quantity}", price_str))
            i += 2
        else:
            i += 1

    # --- Grand Total ---
    summary_lines = lines[idx_summary + 1 :]
    idx_grand_total = _find_line_index(summary_lines, "Grand Total")
    total_paid = ""
    if idx_grand_total is not None and idx_grand_total + 1 < len(summary_lines):
        total_paid = summary_lines[idx_grand_total + 1]

    if not items or not total_paid:
        return None  # didn't find the shape we expected - skip, don't guess

    order_date = _resolve_order_date(email_date_header)

    result = ["Restaurant: Instamart"]
    if order_date:
        result.append(f"Order Date: {order_date}")
    result.append("Items:")
    for name, price in items:
        result.append(f"  {name} - {price}")
    result.append(f"Total Paid: {total_paid}")

    return "\n".join(result)


if __name__ == "__main__":
    sample = """Greetings from Swiggy\U0001F44B
Your Instamart order id:
234442537689535
was successfully delivered.
Deliver To:
[address redacted]
Order Items
1 x Baby Yelakki Banana (Yelakki baalehannu)
₹49.00
1 x Sugar Free Green 100% Natural Made From Stevia
₹266.00
1 x Storia Tender Coconut Water- No Added Sugar Pet bottle
₹98.00
1 x Flyer - Shriram properties 3
₹0.00
1 x Bisleri Water Can
₹120.00
Order Summary
Item Bill
₹533.00
Handling Fee
₹7.08
Delivery Partner Fee
₹0.00
Grand Total
₹540.00
Get the App:
Follow us:"""

    print(distill_instamart_text(sample, email_date_header="Fri, 26 Jun 2026 14:12:57 +0000"))
