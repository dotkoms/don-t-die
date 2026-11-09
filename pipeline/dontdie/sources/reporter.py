"""NIH RePORTER v2 adapter — keyless grant data, US-government public domain.

The v2 API (https://api.reporter.nih.gov/v2/projects/search) answers "who is
getting funded to study what": each result is a funded project-year with its
institution, award amount, PI, and abstract. The old api.reporter.research.gov
host is DNS-dead; this is the canonical host.

Two API quirks drive the design (both verified live):
- `date_added_start/end` criteria are silently ignored, so there is no
  window query — the adapter re-lands the current + previous fiscal year per
  query every run. Landing-zone idempotence makes that cheap: a re-fetch
  overwrites the same file, never duplicates.
- the response total lives at `meta.total` (no `totalCount`), with
  offset/limit pagination.
"""
from __future__ import annotations

import datetime
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..landing import land_item, utc_now_iso

SOURCE = "reporter"

SEARCH_URL = "https://api.reporter.nih.gov/v2/projects/search"
USER_AGENT = "dont-die-research/0.1"
REQUEST_INTERVAL = 0.5  # be polite; the API is shared and keyless
PAGE_SIZE = 500  # the v2 API's maximum limit


def fiscal_years() -> List[int]:
    """The NIH fiscal years to land: the current and the previous one.

    NIH FY N runs Oct (N-1) through Sep N, so October lands in the next FY.
    """
    today = datetime.date.today()
    fy = today.year + 1 if today.month >= 10 else today.year
    return [fy, fy - 1]


def _pis(people: List[Dict[str, Any]]) -> List[str]:
    """[{first_name, last_name, ...}] → ['First Last', ...]."""
    names = []
    for p in people or []:
        first = (p.get("first_name") or "").strip()
        last = (p.get("last_name") or "").strip()
        name = f"{first} {last}".strip()
        if name:
            names.append(name)
    return names


def _agency(value: Any) -> str:
    """agency_ic_admin is a dict: {abbreviation: 'NCI', name: 'National
    Cancer Institute'} — prefer the short abbreviation."""
    if isinstance(value, dict):
        return (value.get("abbreviation") or value.get("name") or "").strip()
    return (str(value) if value else "").strip()


def _date(value: Any) -> str:
    """RePORTER dates arrive as 'YYYY-MM-DD' strings (sometimes None)."""
    if not value:
        return ""
    return str(value)[:10]


def _money(value: Any) -> Optional[int]:
    """Award amounts arrive as strings ('1,234,567') or ints or None."""
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).replace(",", "").split(".")[0])
    except ValueError:
        return None


def parse_project(hit: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One RePORTER result row → a landing-zone record."""
    appl_id = hit.get("appl_id")
    title = (hit.get("project_title") or "").strip()
    if not appl_id or not title:
        return None

    org = hit.get("organization") or {}
    abstract = (hit.get("abstract_text") or "").strip()
    narrative = (hit.get("phr_text") or "").strip()  # public health relevance
    full_abstract = "\n\n".join(p for p in (abstract, narrative) if p)

    start = _date(hit.get("project_start_date"))
    return {
        "source": SOURCE,
        "item_id": str(appl_id),
        "title": title,
        "url": (hit.get("project_detail_url") or
                f"https://reporter.nih.gov/project-details/{appl_id}"),
        "published": start,
        "authors": _pis(hit.get("principal_investigators") or []),
        "abstract": full_abstract[:16000],
        # Grant/funding facts — the item page renders these as a funding
        # record rather than a paper.
        "agency": _agency(hit.get("agency_ic_admin")),
        "award_amount": _money(hit.get("award_amount")),
        "award_type": (hit.get("award_type") or "").strip(),
        "fiscal_year": hit.get("fiscal_year"),
        "project_num": (hit.get("project_num") or "").strip(),
        "core_project_num": (hit.get("core_project_num") or "").strip(),
        "institution": (org.get("org_name") or "").strip(),
        "org_city": (org.get("org_city") or "").strip(),
        "org_state": (org.get("org_state") or "").strip(),
        "pi_names": _pis(hit.get("principal_investigators") or []),
        "project_start_date": start,
        "project_end_date": _date(hit.get("project_end_date")),
        "is_active": bool(hit.get("is_active")),
    }


def _request(text: str, years: List[int], offset: int) -> Dict[str, Any]:
    """One POST to the search endpoint; returns the parsed payload."""
    body = {
        "criteria": {
            "advanced_text_search": {
                "search_field": "all",
                "search_text": text,
                "operator": "or",
            },
            "fiscal_years": years,
        },
        "offset": offset,
        "limit": PAGE_SIZE,
    }
    resp = requests.post(
        SEARCH_URL, json=body, timeout=60,
        headers={"User-Agent": USER_AGENT},
    )
    resp.raise_for_status()
    return resp.json()


def fetch(
    days: int = 7,  # unused — RePORTER has no window (see module docstring)
    limit: int = 500,
    queries: Optional[List[Tuple[str, str]]] = None,
) -> Dict[str, Any]:
    """Land the current + previous fiscal year of funded projects per domain."""
    from .. import config, queries as domain_queries

    if queries is None:
        queries = domain_queries.REPORTER_QUERIES

    years = fiscal_years()
    summary: Dict[str, Any] = {
        "new": 0, "total": 0, "per_query": {},
        "fiscal_years": years, "errors": [],
    }
    for domain, text in queries:
        count = 0
        offset = 0
        try:
            while count < limit:
                time.sleep(REQUEST_INTERVAL)
                payload = _request(text, years, offset)
                total = int((payload.get("meta") or {}).get("total") or 0)
                hits = payload.get("results") or []
                for hit in hits:
                    if count >= limit:
                        break
                    record = parse_project(hit)
                    if record is None:
                        continue
                    path = config.LANDING_DIR / SOURCE / f"{record['item_id']}.json"
                    is_new = not path.exists()
                    record["domain_query"] = domain
                    land_item(SOURCE, record["item_id"], record)
                    count += 1
                    if is_new:
                        summary["new"] += 1
                offset += len(hits)
                if offset >= total or not hits:
                    break
        except Exception as exc:  # noqa: BLE001 — log and continue to next query
            summary["errors"].append({"domain": domain, "term": text,
                                      "error": str(exc)})
        summary["total"] += count
        summary["per_query"][domain] = count
    summary["fetched_at"] = utc_now_iso()
    return summary
