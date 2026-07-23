"""
Pulls order-confirmation emails from Gmail (Swiggy food delivery, Swiggy
Instamart, Zomato) with FULL body content (unlike the Mail Agent's
fetch_mails.py, which only pulled metadata/snippet - we need the actual
order details here). Each platform has its own distiller in _DISTILLERS
since email templates differ structurally between platforms.
"""

import base64

from config import PLATFORM_QUERIES
from ingestion.auth import get_gmail_service
from ingestion.html_clean import html_to_text, truncate_for_llm, redact_addresses, distill_order_text
from ingestion.instamart_clean import distill_instamart_text

# Marketing/retention emails ("Tell us if you liked us", win-back offers,
# etc.) come from the same sender as real order confirmations, so the Gmail
# query alone can't separate them. Real order confirmations reliably contain
# these markers; promo emails don't.
_ORDER_MARKERS = ["order id", "bill details", "order journey", "order items"]

# Each platform gets its own distiller since email templates differ
# structurally. All distillers share the signature (text, email_date_header)
# -> distilled_text | None, even if a given distiller ignores the date
# header (food orders have their own timestamp in the body; Instamart
# doesn't, so it needs the header).
_DISTILLERS = {
    "swiggy": lambda text, date_header: distill_order_text(text),
    "instamart": distill_instamart_text,
}


def _is_order_confirmation(clean_body):
    body_lower = clean_body.lower()
    return any(marker in body_lower for marker in _ORDER_MARKERS)


def _get_body(payload):
    """
    Extract the email body from a Gmail message payload.
    Prefers HTML (order emails are almost always HTML-formatted tables);
    falls back to plain text if that's all that's available.
    """
    html_body = None
    plain_body = None

    if "parts" in payload:
        for part in payload["parts"]:
            mime = part.get("mimeType")
            data = part.get("body", {}).get("data")
            if mime == "text/html" and data:
                html_body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            elif mime == "text/plain" and data:
                plain_body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            # handle nested multipart (e.g. multipart/alternative inside multipart/mixed)
            elif "parts" in part:
                nested_html, nested_plain = _get_body(part)
                html_body = html_body or nested_html
                plain_body = plain_body or nested_plain
    else:
        data = payload.get("body", {}).get("data")
        if data:
            decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            if payload.get("mimeType") == "text/html":
                html_body = decoded
            else:
                plain_body = decoded

    return html_body, plain_body


def fetch_order_emails(platform, max_results=20, query_suffix=""):
    """
    Fetch order-confirmation emails for a given platform ('zomato' or 'swiggy').
    Returns list of dicts: {id, thread_id, subject, date, clean_body}
    clean_body is plain text, HTML-stripped and truncated - ready for the
    extraction prompt.

    max_results is a TARGET number of matching emails to collect, not a
    single-page cap - this function pages through Gmail's results (via
    nextPageToken) until it collects max_results or runs out of messages.
    Without pagination, re-running with the same max_results just re-fetches
    the same most-recent batch forever.
    """
    if platform not in PLATFORM_QUERIES:
        raise ValueError(f"Unknown platform '{platform}'. Expected one of {list(PLATFORM_QUERIES)}")

    service = get_gmail_service()
    query = PLATFORM_QUERIES[platform] + (f" {query_suffix}" if query_suffix else "")

    emails = []
    page_token = None

    while len(emails) < max_results:
        list_kwargs = {"userId": "me", "maxResults": min(50, max_results - len(emails)), "q": query}
        if page_token:
            list_kwargs["pageToken"] = page_token

        results = service.users().messages().list(**list_kwargs).execute()
        messages = results.get("messages", [])
        page_token = results.get("nextPageToken")

        if not messages:
            break  # no more messages match the query at all

        for msg in messages:
            msg_data = service.users().messages().get(
                userId="me", id=msg["id"], format="full"
            ).execute()

            headers = msg_data["payload"].get("headers", [])
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "")
            date = next((h["value"] for h in headers if h["name"] == "Date"), "")

            html_body, plain_body = _get_body(msg_data["payload"])
            if html_body:
                clean_body = html_to_text(html_body)
            else:
                clean_body = plain_body or ""

            # Drop marketing/retention emails - only keep real order confirmations
            if not _is_order_confirmation(clean_body):
                continue

            # Strip delivery/home address before this ever gets stored, printed,
            # or sent to the LLM
            clean_body = redact_addresses(clean_body)

            # Reduce to just restaurant, items, total paid - using this
            # platform's specific distiller
            distiller = _DISTILLERS.get(platform)
            clean_body = distiller(clean_body, date) if distiller else None

            # None means this platform has no distiller yet, or the email
            # didn't match the expected structure - skip rather than
            # feeding unparsed noise to the LLM
            if clean_body is None:
                continue

            clean_body = truncate_for_llm(clean_body)

            emails.append({
                "id": msg["id"],
                "thread_id": msg_data.get("threadId", msg["id"]),
                "platform": platform,
                "subject": subject,
                "date": date,
                "clean_body": clean_body,
            })

        if not page_token:
            break  # exhausted all pages Gmail has for this query

    return emails


def fetch_all_order_emails(max_results_per_platform=20):
    """Convenience: fetch from every configured platform in one call."""
    all_emails = []
    for platform in PLATFORM_QUERIES:
        all_emails.extend(fetch_order_emails(platform, max_results=max_results_per_platform))
    return all_emails


if __name__ == "__main__":
    for platform in PLATFORM_QUERIES:
        print(f"\n===== {platform.upper()} =====")
        emails = fetch_order_emails(platform, max_results=3)
        print(f"Found {len(emails)} emails")
        for e in emails:
            print(f"\n--- {e['subject']} ({e['date']}) ---")
            print(e["clean_body"][:800])
            print("...")
