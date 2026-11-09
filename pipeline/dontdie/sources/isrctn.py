"""ISRCTN registry adapter — keyless XML API, tier 1 (primary registry).

Two-stage fetch: the search endpoint (default format) returns per-trial
lastUpdated timestamps, which we window-filter client-side; each in-window
trial is then fetched in WHO ICTRP format for the standard fields
(recruitment status, sponsor, target size). In-window trials are re-fetched
every run so statuses refresh — daily runs only see trials updated in the
last `days`, which keeps this polite. ISRCTN asks for single-threaded use; we
throttle detail requests to one per 0.5 s.
"""
from __future__ import annotations

import datetime
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..landing import land_item, utc_now_iso

SOURCE = "isrctn"

SEARCH_URL = "https://www.isrctn.com/api/query/format/default"
TRIAL_URL = "https://www.isrctn.com/api/trial/{id}/format/who"
USER_AGENT = "dont-die-research/0.1"
REQUEST_INTERVAL = 0.5  # ISRCTN asks for gentle, single-threaded use


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(node: Optional[ET.Element]) -> str:
    return "".join(node.itertext()).strip() if node is not None else ""


def _find(parent: ET.Element, name: str) -> Optional[ET.Element]:
    for node in parent.iter():
        if _local(node.tag) == name:
            return node
    return None


def _ddmmyyyy_to_iso(value: str) -> str:
    """ISRCTN WHO-format dates are day-first: '04/11/2026' → '2026-11-04'."""
    try:
        parsed = datetime.datetime.strptime((value or "").strip(), "%d/%m/%Y")
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        return ""


def parse_search(xml_text: str) -> Tuple[int, List[Dict[str, str]]]:
    """Parse a default-format search response.

    Returns (totalCount, entries) where each entry is
    {"id": "12345678", "last_updated": "2026-11-04T09:25:11.918Z"}.
    """
    root = ET.fromstring(xml_text)
    total = int(root.get("totalCount", "0"))
    entries = []
    for trial in root.iter():
        if _local(trial.tag) != "trial":
            continue
        isrctn_node = _find(trial, "isrctn")
        isrctn_id = _text(isrctn_node)
        if isrctn_id:
            entries.append({"id": isrctn_id,
                            "last_updated": trial.get("lastUpdated", "")})
    return total, entries


def in_window(entry: Dict[str, str], cutoff: str) -> bool:
    """True if the trial was updated on/after the cutoff date (or is undated)."""
    updated = (entry.get("last_updated") or "")[:10]
    return not updated or updated >= cutoff


def parse_who_trial(xml_text: str) -> Optional[Dict[str, Any]]:
    """Parse a WHO-format trial record into a landing-zone record (pure)."""
    root = ET.fromstring(xml_text)
    main = _find(root, "main")
    if main is None:
        return None

    def field(name: str) -> str:
        return _text(_find(main, name))

    trial_id = field("trial_id") or f"ISRCTN{field('isrctn')}"
    if not trial_id:
        return None

    title = field("public_title") or field("scientific_title")
    if not title:
        return None

    phase = field("phase")
    conditions = field("hc_freetext")
    interventions = field("i_freetext")
    # Real descriptive text for the relevance gate and search; the item page
    # renders the structured registry fields.
    abstract = " ".join(part for part in (conditions, interventions) if part)

    return {
        "source": SOURCE,
        "item_id": trial_id,
        "title": title,
        "official_title": field("scientific_title") or title,
        "url": field("url") or f"https://www.isrctn.com/{trial_id}",
        "published": _ddmmyyyy_to_iso(field("date_registration")),
        "authors": [],
        "status": field("recruitment_status"),
        "phases": [] if phase in ("", "Not Applicable") else [phase],
        "enrollment": field("target_size"),
        "sponsor": field("primary_sponsor"),
        "study_type": field("study_type"),
        "study_design": field("study_design"),
        "conditions": conditions,
        "interventions": interventions,
        "start_date": _ddmmyyyy_to_iso(field("date_enrolment")),
        "registration_date": _ddmmyyyy_to_iso(field("date_registration")),
        "abstract": abstract[:8000],
        "domain_query": "",  # set by the caller (the query's domain)
    }


def fetch(
    days: int = 7,
    limit: int = 100,
    queries: Optional[List[Tuple[str, str]]] = None,
) -> Dict[str, Any]:
    """Run all ISRCTN domain queries, refreshing in-window trials."""
    from .. import config, queries as domain_queries

    if queries is None:
        queries = domain_queries.ISRCTN_QUERIES

    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    summary: Dict[str, Any] = {"new": 0, "total": 0, "per_query": {}, "errors": []}
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    for domain, term in queries:
        count = 0
        try:
            resp = session.get(SEARCH_URL, params={"q": term, "limit": limit},
                               timeout=60)
            resp.raise_for_status()
            _total, entries = parse_search(resp.text)
            for entry in entries[:limit]:
                if not in_window(entry, cutoff):
                    continue
                time.sleep(REQUEST_INTERVAL)
                detail = session.get(TRIAL_URL.format(id=entry["id"]),
                                     timeout=60)
                detail.raise_for_status()
                record = parse_who_trial(detail.text)
                if record is None:
                    continue
                path = (config.LANDING_DIR / SOURCE
                        / f"{record['item_id']}.json")
                is_new = not path.exists()
                record["domain_query"] = domain
                land_item(SOURCE, record["item_id"], record)
                count += 1
                if is_new:
                    summary["new"] += 1
        except Exception as exc:  # noqa: BLE001 — log and continue to next query
            summary["errors"].append({"domain": domain, "error": str(exc)})
        summary["total"] += count
        summary["per_query"][domain] = count
    summary["fetched_at"] = utc_now_iso()
    return summary
