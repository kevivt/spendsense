"""
End-to-end pipeline: Gmail -> distilled text -> LLM extraction -> SQLite.

This is the script you'll eventually call from a scheduled/background sync
(api/sync_job.py, built later). For now it's runnable standalone so we can
verify the full chain works against your real inbox before wiring in
FastAPI.
"""

from datetime import datetime

from config import PLATFORM_QUERIES
from ingestion.fetch_orders import fetch_order_emails
from extraction.extractor import extract_order
from storage.db import init_db, insert_order


def _parse_order_date_from_email_date(email_date_header):
    """
    Fallback reference year source: Gmail's Date header (RFC 2822 format,
    e.g. 'Fri, 26 Jun 2026 14:12:57 +0000') is reliable even when the
    email body's own timestamp is ambiguous about year.
    """
    try:
        # crude parse: grab the 4-digit year token
        for token in email_date_header.replace(",", " ").split():
            if token.isdigit() and len(token) == 4:
                return int(token)
    except Exception:
        pass
    return datetime.now().year


def sync_orders(platform="swiggy", max_results=20, verbose=True):
    """
    Fetch, extract, and store orders for a platform. Returns a summary dict
    with counts - how many were fetched, skipped (dupes), extracted
    successfully, and failed extraction.
    """
    init_db()

    emails = fetch_order_emails(platform, max_results=max_results)
    summary = {"fetched": len(emails), "inserted": 0, "duplicate": 0, "extraction_failed": 0}

    for email in emails:
        reference_year = _parse_order_date_from_email_date(email["date"])
        parsed, error = extract_order(email["clean_body"], reference_year=reference_year)

        if error:
            summary["extraction_failed"] += 1
            if verbose:
                print(f"[FAILED] {email['subject']!r}: {error}")
            continue

        order_id = insert_order(
            gmail_message_id=email["id"],
            platform=platform,
            restaurant=parsed["restaurant"],
            order_date=parsed["order_date"],
            total_amount=float(parsed["total_amount"]),
            items=parsed["items"],
            raw_subject=email["subject"],
        )

        if order_id is None:
            summary["duplicate"] += 1
            if verbose:
                print(f"[SKIP] Already in DB: {email['subject']!r}")
        else:
            summary["inserted"] += 1
            if verbose:
                print(f"[OK] {parsed['restaurant']} - {parsed['order_date']} - "
                      f"₹{parsed['total_amount']} (order_id={order_id})")

    return summary


if __name__ == "__main__":
    for platform in PLATFORM_QUERIES:
        print(f"\n===== Syncing {platform.upper()} =====")
        result = sync_orders(platform=platform, max_results=20)
        print(f"\nSummary: {result}")
