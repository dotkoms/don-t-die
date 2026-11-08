"""PubMed source adapter — NCBI E-utilities (esearch + efetch), no API key needed.

Unauthenticated limit is 3 req/s; we throttle to NCBI_MIN_INTERVAL regardless.
"""
from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

import requests

from .. import config
from ..landing import land_item, utc_now_iso

SOURCE = "pubmed"


def _ncbi_params() -> Dict[str, str]:
    params = {"tool": config.NCBI_TOOL}
    if config.NCBI_EMAIL:
        params["email"] = config.NCBI_EMAIL
    if config.NCBI_API_KEY:
        params["api_key"] = config.NCBI_API_KEY
    return params


def _get(url: str, params: Dict[str, Any]) -> Any:
    """GET with the NCBI politeness interval; returns parsed JSON or text."""
    time.sleep(config.NCBI_MIN_INTERVAL)
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    return resp


def parse_esearch(payload: Dict[str, Any]) -> List[str]:
    """Return the PMID list from an esearch JSON response."""
    return [str(id_) for id_ in payload.get("esearchresult", {}).get("idlist", [])]


def _text(node: Optional[ET.Element]) -> str:
    return (node.text or "").strip() if node is not None else ""


def _pub_date(article: ET.Element) -> str:
    """ISO-ish publication date (YYYY-MM-DD as far as the record allows)."""
    date = article.find("./Journal/JournalIssue/PubDate")
    if date is None:
        return ""
    year = _text(date.find("Year"))
    month = _text(date.find("Month")) or "01"
    day = _text(date.find("Day")) or "01"
    months = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05",
        "jun": "06", "jul": "07", "aug": "08", "sep": "09", "oct": "10",
        "nov": "11", "dec": "12",
    }
    month = months.get(month[:3].lower(), month)
    if not year.isdigit():
        return " ".join(x for x in (_text(date.find("MedlineDate")),) if x)
    if not month.isdigit() or not day.isdigit():
        return year
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def parse_efetch_xml(xml_text: str) -> List[Dict[str, Any]]:
    """Parse an efetch (db=pubmed) XML body into normalized front-matter records.

    The payload (verbatim XML) is attached by the caller — this function is
    pure so tests run offline against fixtures.
    """
    records = []
    root = ET.fromstring(xml_text)
    for article in root.iter("PubmedArticle"):
        medline = article.find("./MedlineCitation")
        art = medline.find("./Article") if medline is not None else None
        if art is None:
            continue
        pmid = _text(medline.find("./PMID"))
        if not pmid:
            continue

        authors = []
        for author in art.findall("./AuthorList/Author"):
            last = _text(author.find("LastName"))
            fore = _text(author.find("ForeName"))
            collective = _text(author.find("CollectiveName"))
            if collective:
                authors.append(collective)
            elif last:
                authors.append((fore + " " + last).strip() if fore else last)

        doi_node = next(
            (a for a in art.findall("./ELocationID") if a.get("EIdType") == "doi"),
            None,
        )
        abstract_parts = []
        for section in art.findall("./Abstract/AbstractText"):
            label = section.get("Label")
            chunk = "".join(section.itertext()).strip()
            if chunk:
                abstract_parts.append(f"{label}: {chunk}" if label else chunk)

        records.append(
            {
                "source": SOURCE,
                "item_id": pmid,
                "title": "".join(art.findtext("./ArticleTitle", default="") or "").strip(),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "published": _pub_date(art),
                "authors": authors,
                "journal": _text(art.find("./Journal/ISOAbbrevation"))  # NLM's real (misspelled) element
                or _text(art.find("./Journal/ISOAbbreviation"))
                or _text(art.find("./Journal/Title")),
                "doi": _text(doi_node),
                "abstract": "\n".join(abstract_parts),
            }
        )
    return records


def fetch(
    days: int = 7,
    limit: int = 100,
    queries: Optional[List[Tuple[str, str]]] = None,
) -> Dict[str, Any]:
    """Run all PubMed domain queries for the trailing `days`, landing each item.

    Returns a run summary: {"new": n, "total": n, "per_query": {...}} where
    "new" counts items whose landing file did not exist before this run
    (the dedupe view).
    """
    from .. import queries as domain_queries

    if queries is None:
        queries = domain_queries.PUBMED_QUERIES

    summary = {"new": 0, "total": 0, "per_query": {}, "errors": []}
    for domain, term in queries:
        params = {
            "db": "pubmed",
            "term": term,
            "retmode": "json",
            "retmax": limit,
            "sort": "pub_date",
            "datetype": "edat",
            "reldate": days,
            **_ncbi_params(),
        }
        try:
            resp = _get(f"{config.NCBI_EUTILS_BASE_URL}/esearch.fcgi", params)
            pmids = parse_esearch(resp.json())
        except Exception as exc:  # noqa: BLE001 — log and continue to next query
            summary["errors"].append({"domain": domain, "stage": "esearch", "error": str(exc)})
            summary["per_query"][domain] = 0
            continue

        count = 0
        for chunk_start in range(0, len(pmids), 100):
            chunk = pmids[chunk_start : chunk_start + 100]
            efetch_params = {
                "db": "pubmed",
                "id": ",".join(chunk),
                "retmode": "xml",
                **_ncbi_params(),
            }
            try:
                resp = _get(f"{config.NCBI_EUTILS_BASE_URL}/efetch.fcgi", efetch_params)
                xml_text = resp.text
                for record in parse_efetch_xml(xml_text):
                    path = config.LANDING_DIR / SOURCE / f"{record['item_id']}.json"
                    is_new = not path.exists()
                    record["domain_query"] = domain
                    record["payload"] = {"efetch_xml": xml_text}
                    land_item(SOURCE, record["item_id"], record)
                    count += 1
                    if is_new:
                        summary["new"] += 1
            except Exception as exc:  # noqa: BLE001
                summary["errors"].append({"domain": domain, "stage": "efetch", "error": str(exc)})
        summary["total"] += count
        summary["per_query"][domain] = count
    summary["fetched_at"] = utc_now_iso()
    return summary
