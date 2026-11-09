"""AnAge source adapter — curated animal-longevity records (part of HAGR).

AnAge is the de Magalhães group's database of animal longevity and life
history: 4,600+ species from the two-day-lived mayfly to the 200+ year
bowhead whale, each with its maximum longevity and data-quality grade.
Comparative-biology context for the field (the extremes tell you what
biology permits), same family, tier and CC BY 3.0 terms as DrugAge.

Only rows with a reported maximum longevity become items — the rest of the
table is life-history anatomy (gestation, weaning weights) without the
number the corpus exists to carry. Full snapshot, one JSON per species,
landing idempotence absorbs the re-land.
"""
from __future__ import annotations

import csv
import io
import zipfile
from typing import Any, Dict, List, Optional

import requests

from ..landing import land_item, utc_now_iso

SOURCE = "anage"

DATASET_URL = "https://genomics.senescence.info/species/dataset.zip"
SITE_URL = "https://genomics.senescence.info/species/"
USER_AGENT = "dont-die-research/0.1"


def parse_rows(tsv_text: str) -> List[Dict[str, Any]]:
    """anage_data.txt → one record per species with longevity data (pure).

    Titles carry "longevity" so the gate classifies them honestly.
    """
    records = []
    reader = csv.DictReader(io.StringIO(tsv_text), delimiter="\t")
    for row in reader:
        hagrid = (row.get("HAGRID") or "").strip()
        years = (row.get("Maximum longevity (yrs)") or "").strip()
        if not hagrid or not years:
            continue
        genus = (row.get("Genus") or "").strip()
        species = (row.get("Species") or "").strip()
        scientific = f"{genus} {species}".strip()
        common = (row.get("Common name") or "").strip() or scientific

        records.append(
            {
                "source": SOURCE,
                "item_id": hagrid,
                "title": f"{common} — maximum longevity {years} years (AnAge)",
                "url": SITE_URL,
                "published": "",
                "authors": [],
                "summary": (
                    f"AnAge-curated species record: {scientific}"
                    + (f" ({common})" if common != scientific else "")
                    + f" has a maximum recorded longevity of {years} years. "
                    f"Class: {row.get('Class') or '—'}; "
                    f"order: {row.get('Order') or '—'}; "
                    f"family: {row.get('Family') or '—'}. "
                    f"Adult weight: {row.get('Adult weight (g)') or '—'} g. "
                    f"Specimen origin: "
                    f"{row.get('Specimen origin') or '—'}; "
                    f"data quality: {row.get('Data quality') or '—'}; "
                    f"sample size: {row.get('Sample size') or '—'}. "
                    "Data from AnAge (Human Ageing Genomic Resources), "
                    "reused under CC BY 3.0."
                ),
                "species": scientific,
                "common_name": common,
                "taxon_class": (row.get("Class") or "").strip(),
                "taxon_order": (row.get("Order") or "").strip(),
                "taxon_family": (row.get("Family") or "").strip(),
                "max_longevity_years": years,
                "adult_weight_g": (row.get("Adult weight (g)") or "").strip(),
                "specimen_origin": (row.get("Specimen origin") or "").strip(),
                "data_quality": (row.get("Data quality") or "").strip(),
                "domain_query": "lifespan-data",
            }
        )
    return records


def fetch(
    days: int = 7,
    limit: int = 0,
    queries: Optional[List] = None,
) -> Dict[str, Any]:
    """Download the AnAge snapshot and re-land every longevity row."""
    from .. import config

    summary: Dict[str, Any] = {"new": 0, "total": 0, "per_query": {},
                               "errors": []}
    try:
        resp = requests.get(DATASET_URL, timeout=120,
                            headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as bundle:
            tsv_name = next(n for n in bundle.namelist()
                            if n.endswith(".txt") or n.endswith(".csv"))
            tsv_text = bundle.read(tsv_name).decode("utf-8", errors="replace")
        for record in parse_rows(tsv_text):
            path = config.LANDING_DIR / SOURCE / f"{record['item_id']}.json"
            is_new = not path.exists()
            land_item(SOURCE, record["item_id"], record)
            summary["total"] += 1
            if is_new:
                summary["new"] += 1
    except Exception as exc:  # noqa: BLE001
        summary["errors"].append({"source": SOURCE, "error": str(exc)})
    summary["per_query"] = {"lifespan-data": summary["total"]}
    summary["fetched_at"] = utc_now_iso()
    return summary
