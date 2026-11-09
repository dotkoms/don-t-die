"""EU Clinical Trials Information System (CTIS) adapter — keyless JSON API.

The public portal at euclinicaltrials.eu exposes an undocumented but stable
JSON API (search is POST-only; no auth). We search one term per request (its
full-text search does not support boolean OR), sort by lastUpdated and
window-filter client-side — the sort is not strictly monotonic, so no
early-exit: every page is filtered, never trusted. Dates are day-first
DD/MM/YYYY. Status codes map to the portal's public labels; an unknown code
is stored as "code N" rather than guessed.
"""
from __future__ import annotations

import datetime
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..landing import land_item, utc_now_iso

SOURCE = "ctis"

SEARCH_URL = "https://euclinicaltrials.eu/ctis-public-api/search"
USER_AGENT = "dont-die-research/0.1"
REQUEST_INTERVAL = 0.4

# The portal's public status labels (ctPublicStatusCode).
STATUS_CODES = {
    1: "Under evaluation",
    2: "Authorised, recruitment pending",
    3: "Authorised, recruiting",
    4: "Ongoing, recruiting",
    5: "Ongoing, recruitment ended",
    6: "Temporarily halted",
    7: "Suspended",
    8: "Ended",
    9: "Expired",
    10: "Revoked",
    11: "Not authorised",
    12: "Cancelled",
}


def _ddmmyyyy_to_iso(value: str) -> str:
    """'20/08/2026' → '2026-08-20', or ''."""
    try:
        parsed = datetime.datetime.strptime((value or "").strip(), "%d/%m/%Y")
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        return ""


def _status(code: Any) -> str:
    if isinstance(code, bool):  # keep bools out of the int branch
        return ""
    try:
        code = int(code)
    except (TypeError, ValueError):
        return ""
    return STATUS_CODES.get(code, f"code {code}")


def _countries(values: List[str]) -> List[str]:
    """['France:2'] → ['France'] — the count suffix is per-country sites."""
    return [v.split(":", 1)[0].strip() for v in values or [] if v]


def parse_search(payload: Dict[str, Any], cutoff: str) -> List[Dict[str, Any]]:
    """Parse one search response into landing-zone records, window-filtered."""
    records = []
    for hit in payload.get("data") or []:
        ct_number = (hit.get("ctNumber") or "").strip()
        title = (hit.get("ctTitle") or "").strip()
        if not ct_number or not title:
            continue
        last_update = _ddmmyyyy_to_iso(hit.get("lastUpdated", ""))
        if last_update and last_update < cutoff:
            continue

        conditions = (hit.get("conditions") or "").strip()
        primary_endpoint = (hit.get("primaryEndPoint") or "").strip()
        # Real descriptive text for the relevance gate and search; the item
        # page renders the structured registry fields.
        abstract = " ".join(p for p in (conditions, primary_endpoint) if p)

        records.append(
            {
                "source": SOURCE,
                "item_id": ct_number,
                "title": title,
                "url": f"https://euclinicaltrials.eu/trial/{ct_number}",
                "published": "",
                "authors": [],
                "status": _status(hit.get("ctStatus")),
                "phases": [hit.get("trialPhase", "")] if hit.get("trialPhase") else [],
                "enrollment": hit.get("totalNumberEnrolled"),
                "sponsor": (hit.get("sponsor") or "").strip(),
                "sponsor_type": (hit.get("sponsorType") or "").strip(),
                "conditions": conditions,
                "countries": _countries(hit.get("trialCountries") or []),
                "age_group": (hit.get("ageGroup") or "").strip(),
                "gender": (hit.get("gender") or "").strip(),
                "decision_date": _ddmmyyyy_to_iso(
                    hit.get("decisionDateOverall", "")),
                "last_update": last_update,
                "abstract": abstract[:8000],
            }
        )
    return records


def fetch(
    days: int = 7,
    limit: int = 100,
    queries: Optional[List[Tuple[str, str]]] = None,
) -> Dict[str, Any]:
    """Run every CTIS term query, landing trials updated in the window."""
    from .. import config, queries as domain_queries

    if queries is None:
        queries = domain_queries.CTIS_QUERIES

    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    summary: Dict[str, Any] = {"new": 0, "total": 0, "per_query": {}, "errors": []}
    page_size = min(100, max(limit, 1))
    for domain, term in queries:
        count = 0
        page = 1
        try:
            while count < limit:
                time.sleep(REQUEST_INTERVAL)
                body = {
                    "searchCriteria": {"containAll": term},
                    "pagination": {"page": page, "size": page_size},
                    "sort": {"property": "lastUpdated", "direction": "DESC"},
                }
                resp = requests.post(
                    SEARCH_URL, json=body, timeout=60,
                    headers={"User-Agent": USER_AGENT},
                )
                resp.raise_for_status()
                payload = resp.json()
                records = parse_search(payload, cutoff)
                for record in records:
                    path = config.LANDING_DIR / SOURCE / f"{record['item_id']}.json"
                    is_new = not path.exists()
                    record["domain_query"] = domain
                    land_item(SOURCE, record["item_id"], record)
                    count += 1
                    if is_new:
                        summary["new"] += 1
                paging = payload.get("pagination", {})
                page += 1
                if not records or page > paging.get("totalPages", 1):
                    break
        except Exception as exc:  # noqa: BLE001 — log and continue to next query
            summary["errors"].append({"domain": domain, "term": term,
                                      "error": str(exc)})
        summary["total"] += count
        summary["per_query"][domain] = count
    summary["fetched_at"] = utc_now_iso()
    return summary
