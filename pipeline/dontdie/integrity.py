"""Retraction Watch integrity pass — corpus flags, not a source.

The Retraction Watch Database (maintained by Crossref since 2023) is one
CC0 CSV, updated every working day, recording every known retraction,
expression of concern and reinstatement with the original paper's DOI and
PubMed id. Nothing lands in the landing zone and no new corpus items are
created: the CSV is matched against the existing corpus by DOI and PMID,
and matching items get flag columns on items (migration 0004).

The pass is a full recompute: existing flags are cleared before the new
matches are written, so a reinstatement or a corrected record updates the
flag rather than stacking on it. Run after every load — a paper can be
retracted years after it landed, and "we ingested it before it was
retracted" is not an honest state to leave visible.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from . import config
from .store import connect

CSV_URL = ("https://gitlab.com/crossref/retraction-watch-data/-/raw/main/"
           "retraction_watch.csv")
USER_AGENT = "dont-die-research/0.1"

# Downloaded fresh each run (gitignored with the rest of state/).
LOCAL_CSV = config.PIPELINE_ROOT / "state" / "retraction_watch.csv"

# DOI prefixes as they appear in the CSV (records come from many publishers).
_DOI_PREFIXES = (
    "https://doi.org/", "http://doi.org/", "https://dx.doi.org/",
    "http://dx.doi.org/", "doi.org/", "dx.doi.org/", "doi:", "DOI:",
)


def normalize_doi(value: Any) -> str:
    """Lowercase, strip prefixes/whitespace → '' if not usable."""
    doi = (str(value) if value is not None else "").strip().lower()
    for prefix in _DOI_PREFIXES:
        if doi.startswith(prefix):
            doi = doi[len(prefix):].strip()
    return doi.rstrip(".").strip()


def normalize_pmid(value: Any) -> str:
    """'27634749' → '27634749'; 0/''/'unavailable' → ''."""
    text = (str(value) if value is not None else "").strip()
    if not text.isdigit():
        return ""
    pmid = str(int(text))  # no leading zeros
    return "" if pmid == "0" else pmid


def normalize_date(value: str) -> str:
    """The CSV's '7/15/2026 0:00' stamps → YYYY-MM-DD, or ''."""
    stamp = (value or "").split()[0] if (value or "").strip() else ""
    parts = stamp.split("/")
    if len(parts) != 3:
        return ""
    month, day, year = parts
    if not (month.isdigit() and day.isdigit() and year.isdigit()):
        return ""
    if len(year) < 4:
        return ""
    return f"{year[:4]}-{int(month):02d}-{int(day):02d}"


def parse_retractions(csv_text: str) -> Dict[str, Dict[str, str]]:
    """The full CSV → lookup keyed by 'doi:<doi>' and 'pmid:<pmid>'.

    One retraction can surface under both keys of the same original paper;
    later rows win, which matches the upstream file being append-updated.
    """
    lookup: Dict[str, Dict[str, str]] = {}
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        record = {
            "title": (row.get("Title") or "").strip()[:300],
            "nature": (row.get("RetractionNature") or "").strip(),
            "reason": (row.get("Reason") or "").strip().strip(";"),
            "date": normalize_date(row.get("RetractionDate") or ""),
            "url": "",
        }
        notice_doi = normalize_doi(row.get("RetractionDOI"))
        if notice_doi:
            record["url"] = f"https://doi.org/{notice_doi}"
        elif (row.get("URLS") or "").strip():
            record["url"] = (row.get("URLS") or "").strip().split(";")[0]

        for key in (
            "doi:" + normalize_doi(row.get("OriginalPaperDOI")),
            "pmid:" + normalize_pmid(row.get("OriginalPaperPubMedID")),
        ):
            if key not in ("doi:", "pmid:"):
                lookup[key] = record
    return lookup


def _item_keys(source: str, source_id: str, raw: Dict[str, Any]
               ) -> List[str]:
    """Every lookup key a landed item can match on."""
    keys = []
    doi = normalize_doi(raw.get("doi"))
    if doi:
        keys.append("doi:" + doi)
    pmid = normalize_pmid(raw.get("pubmed_id")) or (
        normalize_pmid(source_id) if source == "pubmed" else "")
    if pmid:
        keys.append("pmid:" + pmid)
    return keys


def download_csv() -> Path:
    """Fetch the Retraction Watch CSV into state/ (~70 MB, fresh each run)."""
    LOCAL_CSV.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(CSV_URL, timeout=300,
                        headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    LOCAL_CSV.write_bytes(resp.content)
    return LOCAL_CSV


def refresh(dsn: Optional[str] = None) -> Dict[str, int]:
    """Recompute every item's retraction flags. The entrypoint."""
    download_csv()
    lookup = parse_retractions(LOCAL_CSV.read_text(encoding="utf-8",
                                                   errors="replace"))

    conn = connect(dsn)
    stats = {"retraction_records": len(lookup), "checked": 0,
             "flagged": 0}
    try:
        with conn, conn.cursor() as cur:
            # Full recompute: clear yesterday's flags, then set today's.
            cur.execute(
                "UPDATE items SET is_retracted = false, retraction_nature ="
                " NULL, retraction_reason = NULL, retraction_date = NULL,"
                " retraction_url = NULL WHERE is_retracted"
            )
            cur.execute(
                "SELECT id, source, source_id, raw FROM items"
            )
            matches: List[Tuple[Any, Dict[str, str]]] = []
            for item_id, source, source_id, raw in cur.fetchall():
                stats["checked"] += 1
                if not isinstance(raw, dict):
                    continue
                for key in _item_keys(source, source_id, raw):
                    if key in lookup:
                        matches.append((item_id, lookup[key]))
                        break
            for item_id, record in matches:
                cur.execute(
                    """
                    UPDATE items
                    SET is_retracted = true,
                        retraction_nature = %s, retraction_reason = %s,
                        retraction_date = %s, retraction_url = %s
                    WHERE id = %s
                    """,
                    (record["nature"], record["reason"], record["date"],
                     record["url"], item_id),
                )
                stats["flagged"] += 1
    finally:
        conn.close()
    return stats
