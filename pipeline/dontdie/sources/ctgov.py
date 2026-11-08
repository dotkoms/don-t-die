"""ClinicalTrials.gov source adapter — API v2, no key needed.

Studies are paged with pageToken; we sort by LastUpdatePostDate so a daily run
sees recently-updated trials first, capped at `limit` per domain query.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

from .. import config
from ..landing import land_item, utc_now_iso

SOURCE = "ctgov"


def _date_value(struct: Any) -> str:
    """v2 date structs are {'date': 'YYYY-MM-01', ...} or absent."""
    return struct.get("date", "") if isinstance(struct, dict) else ""


def parse_studies(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse a v2 studies JSON response into normalized front-matter records.

    The payload (verbatim study JSON) is attached by the caller — this
    function is pure so tests run offline against fixtures.
    """
    records = []
    for study in payload.get("studies", []):
        proto = study.get("protocolSection", {})
        ident = proto.get("identificationModule", {})
        status = proto.get("statusModule", {})
        sponsor = proto.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {})
        design = proto.get("designModule", {})
        conditions = proto.get("conditionsModule", {}).get("conditions", [])
        arms = proto.get("armsInterventionsModule", {}).get("interventions", [])
        desc = proto.get("descriptionModule", {})

        nct_id = ident.get("nctId", "")
        if not nct_id:
            continue

        records.append(
            {
                "source": SOURCE,
                "item_id": nct_id,
                "title": ident.get("briefTitle", ""),
                "official_title": ident.get("officialTitle", ""),
                "url": f"https://clinicaltrials.gov/study/{nct_id}",
                "status": status.get("overallStatus", ""),
                "phases": design.get("phases", []),
                "enrollment": design.get("enrollmentInfo", {}).get("count"),
                "sponsor": sponsor.get("name", ""),
                "conditions": conditions,
                "interventions": [a.get("name", "") for a in arms if a.get("name")],
                "start_date": _date_value(status.get("startDateStruct")),
                "completion_date": _date_value(
                    status.get("primaryCompletionDateStruct")
                ),
                "last_update": _date_value(status.get("lastUpdatePostDateStruct")),
                "brief_summary": desc.get("briefSummary", ""),
            }
        )
    return records


def fetch(
    days: int = 7,
    limit: int = 100,
    queries: Optional[List] = None,
) -> Dict[str, Any]:
    """Run all ClinicalTrials.gov domain queries, landing each study.

    `days` is unused by this source in M0 (the updated-in-window filter is an
    M1 refinement); the LastUpdatePostDate sort makes daily runs incremental.
    """
    from .. import queries as domain_queries

    if queries is None:
        queries = domain_queries.CTGOV_QUERIES

    summary = {"new": 0, "total": 0, "per_query": {}, "errors": []}
    session = requests.Session()
    for domain, term in queries:
        page_token: Optional[str] = None
        count = 0
        try:
            while count < limit:
                params: Dict[str, Any] = {
                    "query.term": term,
                    "pageSize": min(100, limit - count),
                    "sort": "LastUpdatePostDate:desc",
                }
                if page_token:
                    params["pageToken"] = page_token
                resp = session.get(
                    f"{config.CTGOV_BASE_URL}/studies", params=params, timeout=60
                )
                resp.raise_for_status()
                payload = resp.json()
                for record in parse_studies(payload):
                    path = config.LANDING_DIR / SOURCE / f"{record['item_id']}.json"
                    is_new = not path.exists()
                    record["domain_query"] = domain
                    record["payload"] = payload.get("studies", [])
                    land_item(SOURCE, record["item_id"], record)
                    count += 1
                    if is_new:
                        summary["new"] += 1
                next_token = payload.get("nextPageToken")
                if not next_token or not payload.get("studies"):
                    break
                page_token = next_token
        except Exception as exc:  # noqa: BLE001 — log and continue to next query
            summary["errors"].append({"domain": domain, "error": str(exc)})
        summary["total"] += count
        summary["per_query"][domain] = count
    summary["fetched_at"] = utc_now_iso()
    return summary
