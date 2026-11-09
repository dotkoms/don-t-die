"""EU CORDIS adapter — keyless project search, data reused under CC BY 4.0.

CORDIS (the European Commission's research project database) is the EU's
RePORTER: funded projects with objective, cost, and EC contribution. Its
legacy REST API retired in 2026; the live surface is the search endpoint the
portal itself uses:

    GET https://cordis.europa.eu/search/en?format=json
         &q=contenttype=project AND (/project/objective="aging" OR ...)
         &num=50&p=N

Queries search inside /project/objective with quoted OR clauses. Like
DrugAge, this is a bounded full-snapshot re-land: the search endpoint has no
reliable date filter, so every run re-lands the matched projects and landing
idempotence absorbs it. Known quirk: a single-result query returns `hit` as a
dict, not a list — normalized in parse_hits().
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..landing import land_item, utc_now_iso

SOURCE = "cordis"

SEARCH_URL = "https://cordis.europa.eu/search/en"
USER_AGENT = "dont-die-research/0.1"
REQUEST_INTERVAL = 0.5
PAGE_SIZE = 50  # practical num cap; larger values return the same


def build_query(terms: List[str]) -> str:
    """['aging', 'geroscience'] → one CORDIS objective query string."""
    clauses = " OR ".join(f'/project/objective="{t}"' for t in terms)
    return f"contenttype=project AND ({clauses})"


def _hits(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract the hit list, normalizing the single-result dict anomaly.

    {result: {header: {totalHits}}, hits: {hit: [...] | {...}}}
    """
    hit = (payload.get("hits") or {}).get("hit")
    if hit is None:
        return []
    if isinstance(hit, dict):
        return [hit]
    return list(hit)


def parse_project(wrapper: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One {project: {...}} hit → a landing-zone record."""
    hit = wrapper.get("project") or {}
    project_id = hit.get("id")
    title = (hit.get("title") or "").strip()
    if not project_id or not title:
        return None

    # The search endpoint truncates objective to ~2,000 chars; teaser is a
    # shorter prose summary. Both are enough for the relevance gate and the
    # item page, which links to the full record.
    objective = (hit.get("objective") or "").strip()
    teaser = (hit.get("teaser") or "").strip()
    abstract = "\n\n".join(p for p in (objective, teaser) if p)

    return {
        "source": SOURCE,
        "item_id": str(project_id),
        "title": title,
        "url": f"https://cordis.europa.eu/project/id/{project_id}",
        "published": (hit.get("startDate") or "")[:10],
        "authors": [],
        "abstract": abstract[:16000],
        # Grant/funding facts, like the RePORTER item pages.
        "acronym": (hit.get("acronym") or "").strip(),
        "status": (hit.get("status") or "").strip(),
        "start_date": (hit.get("startDate") or "")[:10],
        "end_date": (hit.get("endDate") or "")[:10],
        "total_cost": hit.get("totalCost"),
        "ec_contribution": hit.get("ecMaxContribution"),
        "last_update": (hit.get("lastUpdateDate") or "")[:10],
    }


def fetch(
    days: int = 7,  # unused — full-snapshot re-land (see module docstring)
    limit: int = 500,
    queries: Optional[List[Tuple[str, List[str]]]] = None,
) -> Dict[str, Any]:
    """Land every matched project for each domain's objective terms."""
    from .. import config, queries as domain_queries

    if queries is None:
        queries = domain_queries.CORDIS_QUERIES

    summary: Dict[str, Any] = {"new": 0, "total": 0, "per_query": {}, "errors": []}
    for domain, terms in queries:
        count = 0
        page = 1
        q = build_query(terms)
        try:
            while count < limit:
                time.sleep(REQUEST_INTERVAL)
                resp = requests.get(
                    SEARCH_URL,
                    params={"format": "json", "q": q,
                            "num": PAGE_SIZE, "p": page},
                    timeout=60,
                    headers={"User-Agent": USER_AGENT},
                )
                resp.raise_for_status()
                payload = resp.json()
                wrappers = _hits(payload)
                for wrapper in wrappers:
                    if count >= limit:
                        break
                    record = parse_project(wrapper)
                    if record is None:
                        continue
                    path = config.LANDING_DIR / SOURCE / f"{record['item_id']}.json"
                    is_new = not path.exists()
                    record["domain_query"] = domain
                    land_item(SOURCE, record["item_id"], record)
                    count += 1
                    if is_new:
                        summary["new"] += 1
                header = (payload.get("result") or {}).get("header") or {}
                total_hits = int(header.get("totalHits") or 0)
                if not wrappers or count >= total_hits:
                    break
                page += 1
        except Exception as exc:  # noqa: BLE001 — log and continue to next query
            summary["errors"].append({"domain": domain, "error": str(exc)})
        summary["total"] += count
        summary["per_query"][domain] = count
    summary["fetched_at"] = utc_now_iso()
    return summary
