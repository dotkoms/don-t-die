"""Europe PMC source adapter — preprints + non-Medline open access, keyless.

Two surfaces PubMed misses:
  * SRC:PPR — author preprints (bioRxiv/medRxiv share the 10.1101 prefix,
    plus Research Square, Preprints.org and peers): earliest signal,
    no peer review yet, and the site says so on the item page.
  * SRC:PMC AND NOT PMID:* — open-access articles from journals Medline does
    not index (relevant: plenty of peptide/longevity work sits there).

Medline-indexed records are PubMed's job — fetching them here would
double-count. Search is GET-only (POST answers 405); pagination is
cursorMark-based via nextPageUrl. No key needed.
"""
from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..landing import land_item, utc_now_iso
from .rss import strip_html

SOURCE = "europemc"

SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
# Both preprint surfaces and non-Medline PMC, under one query.
SOURCE_FILTER = '((SRC:PPR) OR (SRC:PMC AND NOT (PMID:*)))'
USER_AGENT = "dont-die-research/0.1"

# DOI prefix → preprint server label (bioRxiv and medRxiv share 10.1101,
# which the API does not distinguish either).
_PREPRINT_SERVERS = {
    "10.1101": "bioRxiv/medRxiv",
    "10.21203": "Research Square",
    "10.20944": "Preprints.org",
}


def _preprint_server(doi: str) -> str:
    prefix = doi.split("/", 1)[0]
    return _PREPRINT_SERVERS.get(prefix, "a preprint server")


def _authors(author_string: str) -> List[str]:
    """'Wei X, Cao F, Zhang L.' → ['Wei X', 'Cao F', 'Zhang L']."""
    author_string = (author_string or "").strip().rstrip(".")
    return [a.strip() for a in author_string.split(",") if a.strip()]


def build_query(term: str, days: int) -> str:
    """One domain query: source filter AND (terms) AND publication window."""
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    today = datetime.date.today().isoformat()
    window = f"FIRST_PDATE:[{cutoff} TO {today}]"
    return f"{SOURCE_FILTER} AND ({term}) AND ({window})"


def parse_records(payload: Dict[str, Any], cutoff: str) -> List[Dict[str, Any]]:
    """Parse a search response into landing-zone records (pure).

    `cutoff` (YYYY-MM-DD) is applied to firstPublicationDate client-side so a
    re-fetch cannot drift past the window; undated records are kept — refusing
    to guess a date is more honest than dropping coverage.
    """
    records = []
    for hit in payload.get("resultList", {}).get("result", []):
        src = hit.get("source", "")
        external_id = str(hit.get("id", ""))
        if not src or not external_id:
            continue
        published = (hit.get("firstPublicationDate") or "")[:10]
        if published and published < cutoff:
            continue

        doi = (hit.get("doi") or "").strip()
        is_preprint = src == "PPR"
        journal = hit.get("journalTitle") or ""
        if is_preprint:
            journal = journal or _preprint_server(doi)

        records.append(
            {
                "source": SOURCE,
                "item_id": f"{src}-{external_id}",
                "title": (hit.get("title") or "").strip(),
                "url": f"https://doi.org/{doi}" if doi
                       else f"https://europepmc.org/article/{src}/{external_id}",
                "published": published,
                "authors": _authors(hit.get("authorString", "")),
                "journal": journal,
                "doi": doi,
                "abstract": strip_html(hit.get("abstractText") or "")[:8000],
                "preprint": is_preprint,
                "preprint_server": _preprint_server(doi) if is_preprint else "",
            }
        )
    return records


def fetch(
    days: int = 7,
    limit: int = 100,
    queries: Optional[List[Tuple[str, str]]] = None,
) -> Dict[str, Any]:
    """Run all Europe PMC domain queries for the trailing `days`, landing items."""
    from .. import config, queries as domain_queries

    if queries is None:
        queries = domain_queries.EPMC_QUERIES

    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    summary: Dict[str, Any] = {"new": 0, "total": 0, "per_query": {}, "errors": []}
    for domain, term in queries:
        count = 0
        # First request carries the params; every follow-up uses the API's
        # own nextPageUrl verbatim (it embeds query + cursorMark).
        url: Optional[str] = None
        params = {
            "query": build_query(term, days),
            "format": "json",
            "resultType": "core",
            "pageSize": min(100, limit),
        }
        try:
            while count < limit:
                resp = requests.get(
                    url or SEARCH_URL, params=None if url else params,
                    timeout=60, headers={"User-Agent": USER_AGENT},
                )
                resp.raise_for_status()
                payload = resp.json()
                for record in parse_records(payload, cutoff):
                    path = config.LANDING_DIR / SOURCE / f"{record['item_id']}.json"
                    is_new = not path.exists()
                    record["domain_query"] = domain
                    land_item(SOURCE, record["item_id"], record)
                    count += 1
                    if is_new:
                        summary["new"] += 1
                url = payload.get("nextPageUrl") or None
                if not url or not payload.get("hitCount"):
                    break
        except Exception as exc:  # noqa: BLE001 — log and continue to next query
            summary["errors"].append({"domain": domain, "error": str(exc)})
        summary["total"] += count
        summary["per_query"][domain] = count
    summary["fetched_at"] = utc_now_iso()
    return summary
