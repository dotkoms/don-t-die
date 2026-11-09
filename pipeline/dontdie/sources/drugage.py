"""DrugAge source adapter — curated lifespan-assay dataset (part of HAGR).

One row = one lifespan experiment (compound × species × strain × dose), taken
from the manually curated DrugAge database maintained by the de Magalhães
group (Human Ageing Genomic Resources, CC BY 3.0). DrugAge is derived from
primary papers — every row cites its PubMed source — so we ingest it as tier 2
and every item page links the underlying study.

`days` and `limit` are deliberately ignored: the dataset is a full snapshot
and landing is idempotent (one JSON per assay, keyed by a stable composite
hash), so every run re-lands the whole table and refreshes changed values.
"""
from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from typing import Any, Dict, List, Optional

import requests

from ..landing import land_item, utc_now_iso

SOURCE = "drugage"

DATASET_URL = "https://genomics.senescence.info/drugs/dataset.zip"
USER_AGENT = "dont-die-research/0.1"
SITE_URL = "https://genomics.senescence.info/drugs/"

# The id key: every field that identifies the assay, so a dose or percent
# change updates the same landing file instead of duplicating it.
_ID_FIELDS = (
    "compound_name", "species", "strain", "dosage", "gender", "pubmed_id",
    "avg_lifespan_change_percent", "max_lifespan_change_percent",
)


def _signed_percent(value: str) -> str:
    """'81.29' → '+81.3%', '-12.0' → '−12.0%', '' → ''."""
    value = (value or "").strip()
    if not value:
        return ""
    try:
        number = float(value)
    except ValueError:
        return ""
    sign = "+" if number > 0 else ""
    return f"{sign}{number:.1f}%"


def item_id(row: Dict[str, str]) -> str:
    key = "|".join(row.get(f, "") for f in _ID_FIELDS)
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def parse_rows(csv_text: str) -> List[Dict[str, Any]]:
    """Parse the DrugAge CSV into landing-zone records (pure).

    Titles are constructed to carry "lifespan" (and the compound) so the
    relevance gate classifies these honestly: each item IS a lifespan assay.
    """
    records = []
    for row in csv.DictReader(io.StringIO(csv_text)):
        compound = (row.get("compound_name") or "").strip()
        species = (row.get("species") or "").strip()
        if not compound or not species:
            continue

        avg_pct = _signed_percent(row.get("avg_lifespan_change_percent"))
        max_pct = _signed_percent(row.get("max_lifespan_change_percent"))
        effect = avg_pct or max_pct
        strain = (row.get("strain") or "").strip()
        pubmed_id = (row.get("pubmed_id") or "").strip()

        title = f"{compound}: {effect or 'reported'} lifespan change in {species}"
        if strain:
            title += f" ({strain})"
        summary = (
            f"DrugAge-curated lifespan assay. Compound: {compound}. "
            f"Species: {species}{f' (strain {strain})' if strain else ''}. "
            f"Dosage: {row.get('dosage') or '—'}. Gender: {row.get('gender') or '—'}. "
            f"Average lifespan change: {avg_pct or '—'} "
            f"(significance {row.get('avg_lifespan_significance') or '—'}); "
            f"maximum lifespan change: {max_pct or '—'} "
            f"(significance {row.get('max_lifespan_significance') or '—'}). "
            f"Interventional Testing Program: {row.get('ITP') or '—'}. "
            + (f"Underlying study: PubMed {pubmed_id}. " if pubmed_id else "")
            + "Data from DrugAge (Human Ageing Genomic Resources), reused under CC BY 3.0."
        )

        records.append(
            {
                "source": SOURCE,
                "item_id": item_id(row),
                "title": title,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/" if pubmed_id
                       else SITE_URL,
                "published": "",  # assays carry no date of their own — honest beat
                "authors": [],
                "summary": summary,
                "compound": compound,
                "species": species,
                "strain": strain,
                "dosage": (row.get("dosage") or "").strip(),
                "gender": (row.get("gender") or "").strip(),
                "itp": (row.get("ITP") or "").strip(),
                "avg_lifespan_change_percent": avg_pct,
                "avg_lifespan_significance": row.get("avg_lifespan_significance", ""),
                "max_lifespan_change_percent": max_pct,
                "max_lifespan_significance": row.get("max_lifespan_significance", ""),
                "pubmed_id": pubmed_id,
                "domain_query": "lifespan-data",
            }
        )
    return records


def fetch(
    days: int = 7,
    limit: int = 0,
    queries: Optional[List] = None,
) -> Dict[str, Any]:
    """Download the DrugAge snapshot and re-land every assay row."""
    from .. import config

    summary: Dict[str, Any] = {"new": 0, "total": 0, "per_query": {}, "errors": []}
    try:
        resp = requests.get(DATASET_URL, timeout=120,
                            headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as bundle:
            csv_name = next(
                n for n in bundle.namelist() if n.endswith(".csv"))
            csv_text = bundle.read(csv_name).decode("utf-8")
        for record in parse_rows(csv_text):
            path = config.LANDING_DIR / SOURCE / f"{record['item_id']}.json"
            is_new = not path.exists()
            land_item(SOURCE, record["item_id"], record)
            summary["total"] += 1
            if is_new:
                summary["new"] += 1
    except Exception as exc:  # noqa: BLE001
        summary["errors"].append({"source": "drugage", "error": str(exc)})
    summary["per_query"] = {"lifespan-data": summary["total"]}
    summary["fetched_at"] = utc_now_iso()
    return summary
