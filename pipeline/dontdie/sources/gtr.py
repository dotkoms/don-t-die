"""UKRI Gateway to Research adapter — keyless project search (tier 1 grants).

GtR is the UK's RePORTER/CORDIS: every project UKRI (BBSRC, MRC, AHRC and the
other councils) has funded. UKRI launched a keyless JSON search API in
November 2026; no auth, ~10 req/s, refreshed monthly.

The fetch is two-phase because the search endpoint truncates: /api/search/
project returns a projectComposition but with abstractText null (only an
abstractSnippet, itself often null), while the per-project endpoint
/api/projects?ref=<grant reference> returns the full record — abstract,
technical summary, status, fund. So each term is searched to collect grant
references, then every unique project is fetched in detail. Like CORDIS this
is a bounded full-snapshot re-land (no date filter exists), absorbed by
landing idempotence.
"""
from __future__ import annotations

import datetime
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import requests

from ..landing import land_item, utc_now_iso

SOURCE = "gtr"

SEARCH_URL = "https://gtr.ukri.org/api/search/project"
DETAIL_URL = "https://gtr.ukri.org/api/projects"
PUBLIC_URL = "https://gtr.ukri.org/projects"  # the human-facing page
USER_AGENT = "dont-die-research/0.1"
REQUEST_INTERVAL = 0.4
PAGE_SIZE = 100


def _get(url: str, params: Dict[str, Any]) -> requests.Response:
    """GET with the politeness interval and one retry on a transient 5xx.

    GtR occasionally answers a burst with 503; one backed-off retry has been
    enough in practice.
    """
    for attempt in (1, 2):
        time.sleep(REQUEST_INTERVAL)
        resp = requests.get(url, params=params, timeout=60,
                            headers={"User-Agent": USER_AGENT,
                                     "Accept": "application/json"})
        if resp.status_code not in (502, 503) or attempt == 2:
            return resp
        time.sleep(2)
    return resp  # unreachable, but the loop must return


def _ms_to_date(value: Any) -> str:
    """GtR dates are epoch milliseconds → YYYY-MM-DD, or ''."""
    try:
        ms = int(value)
    except (TypeError, ValueError):
        return ""
    return datetime.datetime.fromtimestamp(
        ms / 1000, tz=datetime.timezone.utc).strftime("%Y-%m-%d")


def _text(value: Any) -> str:
    return (str(value).strip() if value not in (None, "") else "")


def parse_project(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One /api/projects?ref=... payload → a landing-zone record (pure)."""
    composition = (payload.get("projectOverview") or {}).get(
        "projectComposition") or {}
    project = composition.get("project") or {}
    project_id = project.get("id")
    title = _text(project.get("title"))
    if not project_id or not title:
        return None

    fund = project.get("fund") or {}
    lead = composition.get("leadResearchOrganisation") or {}
    pis = [
        _text(pi.get("fullName"))
        for pi in (composition.get("principalInvestigators") or [])
        if pi and _text(pi.get("fullName"))
    ]
    grant_ref = _text(project.get("grantReference"))

    abstract = "\n\n".join(
        p for p in (_text(project.get("abstractText")),
                    _text(project.get("technicalSummary"))) if p)

    return {
        "source": SOURCE,
        "item_id": project_id,
        "title": title,
        "url": f"{PUBLIC_URL}?ref={quote(grant_ref)}" if grant_ref
               else "https://gtr.ukri.org/",
        "published": _ms_to_date(fund.get("start")),
        "authors": pis,
        "abstract": abstract[:16000],
        # Grant/funding facts, like the RePORTER/CORDIS item pages. The
        # award value is GBP — the site formats it as £.
        "agency": _text((fund.get("funder") or {}).get("name")),
        "award_amount": fund.get("valuePounds"),
        "status": _text(project.get("status")),
        "grant_reference": grant_ref,
        "grant_category": _text(project.get("grantCategory")),
        "institution": _text(lead.get("name")),
        "pi_names": pis,
        "project_start_date": _ms_to_date(fund.get("start")),
        "project_end_date": _ms_to_date(fund.get("end")),
        "is_active": _text(project.get("status")).lower() == "active",
        "research_topics": [
            _text(t.get("text"))
            for t in (project.get("researchTopics") or [])
            if _text(t.get("text"))
        ][:8],
    }


def search_hits(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The results list from /api/search/project, tolerating odd shapes."""
    return (payload.get("facetedSearchResultBean") or {}).get("results") or []


def search_total(payload: Dict[str, Any]) -> int:
    return int((payload.get("facetedSearchResultBean") or {}).get(
        "totalResults") or 0)


def fetch(
    days: int = 7,  # unused — full-snapshot re-land (see module docstring)
    limit: int = 100,
    queries: Optional[List[Tuple[str, str]]] = None,
) -> Dict[str, Any]:
    """Search every term, then land the detail of each unique project."""
    from .. import config, queries as domain_queries

    if queries is None:
        queries = domain_queries.GTR_QUERIES

    summary: Dict[str, Any] = {
        "new": 0, "total": 0, "per_query": {}, "errors": [],
        "matched": 0,
    }

    # Phase 1: term searches collect unique projects (id → domain + grant ref).
    matched: Dict[str, Tuple[str, str]] = {}
    for domain, term in queries:
        count = 0
        page = 1
        try:
            while count < limit:
                payload = _get(SEARCH_URL, {
                    "term": term, "fetchSize": PAGE_SIZE, "page": page,
                }).json()
                hits = search_hits(payload)
                for hit in hits:
                    project = (hit.get("projectComposition") or {}).get(
                        "project") or {}
                    pid = project.get("id")
                    if not pid:
                        continue
                    if pid not in matched:
                        matched[pid] = (
                            domain, _text(project.get("grantReference")))
                    count += 1
                if not hits or count >= search_total(payload):
                    break
                page += 1
        except Exception as exc:  # noqa: BLE001 — log and continue to next term
            summary["errors"].append({"domain": domain, "term": term,
                                      "error": str(exc)})
        summary["per_query"][domain] = count

    # Phase 2: per-project detail — the full record the search page omits.
    summary["matched"] = len(matched)
    for project_id, (domain, grant_ref) in sorted(matched.items()):
        if not grant_ref:
            continue  # no reference → no detail endpoint; nothing to land
        try:
            payload = _get(DETAIL_URL, {"ref": grant_ref}).json()
            record = parse_project(payload)
            if record is None:
                continue
            path = config.LANDING_DIR / SOURCE / f"{record['item_id']}.json"
            is_new = not path.exists()
            record["domain_query"] = domain
            land_item(SOURCE, record["item_id"], record)
            summary["total"] += 1
            if is_new:
                summary["new"] += 1
        except Exception as exc:  # noqa: BLE001
            summary["errors"].append({"domain": domain, "ref": grant_ref,
                                      "error": str(exc)})
    summary["fetched_at"] = utc_now_iso()
    return summary
