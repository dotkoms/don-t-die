"""CellAge source adapter — curated cellular-senescence genes (part of HAGR).

CellAge is the de Magalhães group's database of genes whose manipulation
induces or inhibits cellular senescence — the genetics behind the
senolytics domain, with each row citing its PubMed study. Same family,
tier and CC BY 3.0 terms as DrugAge and GenAge. The companion
cellSignatures.zip (expression signatures of senescent cells) is deferred:
those rows are per-gene statistics for enrichment, not corpus items.

Full snapshot, one JSON per gene, landing idempotence absorbs the re-land.
"""
from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from typing import Any, Dict, List, Optional

import requests

from ..landing import land_item, utc_now_iso

SOURCE = "cellage"

DATASET_URL = "https://genomics.senescence.info/cells/cellAge.zip"
SITE_URL = "https://genomics.senescence.info/cells/"
USER_AGENT = "dont-die-research/0.1"


def item_id(entrez_id: str, symbol: str) -> str:
    """Stable id: identifying fields only, so an effect change re-lands."""
    return hashlib.sha1(f"{entrez_id}|{symbol}".encode()).hexdigest()[:16]


def parse_rows(tsv_text: str) -> List[Dict[str, Any]]:
    """cellage3.tsv → one record per senescence gene (pure).

    Titles carry "senescence" so the gate classifies them honestly.
    """
    records = []
    reader = csv.DictReader(io.StringIO(tsv_text), delimiter="\t")
    for row in reader:
        symbol = (row.get("Gene symbol") or "").strip()
        entrez = (row.get("Entrez ID") or "").strip()
        if not symbol or not entrez:
            continue
        name = (row.get("Gene name") or "").strip()
        effect = (row.get("Senescence Effect") or "").strip()
        stype = (row.get("Type of senescence") or "").strip()
        cancer = (row.get("Cancer Cell") or "").strip()
        pubmed_id = (row.get("Reference") or "").strip()

        verb = effect.lower() if effect else "affects"
        records.append(
            {
                "source": SOURCE,
                "item_id": item_id(entrez, symbol),
                "title": f"{symbol} — {verb} cellular senescence (CellAge)",
                "url": f"https://www.ncbi.nlm.nih.gov/gene/{entrez}",
                "published": "",
                "authors": [],
                "summary": (
                    f"CellAge-curated senescence gene: {symbol} ({name}) "
                    f"{verb} cellular senescence. "
                    f"Type of senescence: {stype or '—'}; "
                    f"cancer cell evidence: {cancer or '—'}. "
                    + (f"Underlying study: PubMed {pubmed_id}. "
                       if pubmed_id else "")
                    + "Data from CellAge (Human Ageing Genomic Resources), "
                    "reused under CC BY 3.0."
                ),
                "gene_symbol": symbol,
                "gene_name": name,
                "entrez_id": entrez,
                "senescence_effect": effect,
                "senescence_type": stype,
                "cancer_cell": cancer,
                "pubmed_id": pubmed_id,
                "domain_query": "genetics-data",
            }
        )
    return records


def fetch(
    days: int = 7,
    limit: int = 0,
    queries: Optional[List] = None,
) -> Dict[str, Any]:
    """Download the CellAge snapshot and re-land every gene row."""
    from .. import config

    summary: Dict[str, Any] = {"new": 0, "total": 0, "per_query": {},
                               "errors": []}
    try:
        resp = requests.get(DATASET_URL, timeout=120,
                            headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as bundle:
            tsv_name = next(n for n in bundle.namelist()
                            if n.endswith(".tsv") or n.endswith(".csv"))
            tsv_text = bundle.read(tsv_name).decode("utf-8")
        for record in parse_rows(tsv_text):
            path = config.LANDING_DIR / SOURCE / f"{record['item_id']}.json"
            is_new = not path.exists()
            land_item(SOURCE, record["item_id"], record)
            summary["total"] += 1
            if is_new:
                summary["new"] += 1
    except Exception as exc:  # noqa: BLE001
        summary["errors"].append({"source": SOURCE, "error": str(exc)})
    summary["per_query"] = {"genetics-data": summary["total"]}
    summary["fetched_at"] = utc_now_iso()
    return summary
