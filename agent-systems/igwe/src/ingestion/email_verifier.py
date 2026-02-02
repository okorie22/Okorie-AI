"""
Rapid Email Validator client for deliverability checks.
No API key required; public API at https://rapid-email-verifier.fly.dev
"""
import os
from typing import List, Dict, Any

import requests
from loguru import logger

# Configurable base URL for testing or self-hosted
DEFAULT_BASE_URL = "https://rapid-email-verifier.fly.dev"
BATCH_SIZE = 100

# Only VALID is safe to email (PROBABLY_VALID = role addresses, bounce more)
DELIVERABLE_STATUSES = frozenset({"VALID"})

# Role/generic local parts: never treat as deliverable (high bounce)
ROLE_LOCAL_PARTS = frozenset({
    "info", "sales", "support", "admin", "contact", "hello", "office", "team",
    "hr", "noreply", "no-reply", "mail", "enquiries", "inquiry", "enquiry",
    "help", "feedback", "webmaster", "postmaster", "abuse", "billing",
})


def validate_batch(emails: List[str], base_url: str | None = None) -> List[Dict[str, Any]]:
    """
    Validate a list of emails via Rapid Email Validator batch API (max 100 per request).

    Returns a list of dicts, one per email, with keys:
      - email: str
      - status: str | None (e.g. VALID, INVALID_FORMAT, DISPOSABLE; None on API error)
      - deliverable: bool (True only for VALID; role addresses blocked)
    On API failure for the batch, returns entries with status=None and deliverable=False.
    """
    base_url = (base_url or os.getenv("EMAIL_VERIFIER_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    results: List[Dict[str, Any]] = []

    if not emails:
        return results

    # API allows max 100 per batch
    for i in range(0, len(emails), BATCH_SIZE):
        chunk = emails[i : i + BATCH_SIZE]
        url = f"{base_url}/api/validate/batch"
        try:
            resp = requests.post(url, json={"emails": chunk}, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.warning(f"Email verifier API error for batch: {e}")
            for email in chunk:
                results.append({"email": email, "status": None, "deliverable": False})
            continue

        raw_results = data.get("results") or []
        for item in raw_results:
            email = item.get("email", "")
            status = item.get("status")
            deliverable = status in DELIVERABLE_STATUSES
            # Block role/generic addresses even if validator says VALID
            if deliverable and "@" in email:
                local = email.split("@", 1)[0].strip().lower()
                if local in ROLE_LOCAL_PARTS:
                    deliverable = False
            results.append({"email": email, "status": status, "deliverable": deliverable})

    return results


def build_email_to_result_map(emails: List[str], base_url: str | None = None) -> Dict[str, Dict[str, Any]]:
    """
    Validate emails in batches and return a map: email -> {status, deliverable}.
    Convenience for import flow; duplicates in input are deduplicated before calling API.
    """
    seen = set()
    unique = []
    for e in emails:
        if not e or not isinstance(e, str):
            continue
        e = e.strip().lower()
        if e and e not in seen:
            seen.add(e)
            unique.append(e)

    if not unique:
        return {}

    results = validate_batch(unique, base_url=base_url)
    return {r["email"]: {"status": r["status"], "deliverable": r["deliverable"]} for r in results}
