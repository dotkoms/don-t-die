"""GenAge source adapter — curated aging-gene datasets (part of HAGR).

GenAge is the de Magalhães group's database of genes related to aging, the
genetics sibling of DrugAge (same site, same CC BY 3.0 terms, same tier-2
treatment: curated secondary data derived from primary papers). Two
datasets:

  * human genes — the curated candidate genes of human aging, each with its
    evidence categories (what kind of evidence got it included);
  * model-organism genes — gene manipulations whose effect on lifespan was
    measured in C. elegans, D. melanogaster, M. musculus and peers, with the
    direction of the effect and the pro/anti-longevity verdict.

Like DrugAge, `days`/`limit` are ignored: full snapshot, one JSON per gene,
landing idempotence absorbs the re-land.
"""
from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from typing import Any, Dict, List, Optional

import requests

from ..landing import land_item, utc_now_iso

SOURCE = "genage"

HUMAN_URL = "https://genomics.senescence.info/genes/human_genes.zip"
MODELS_URL = "https://genomics.senescence.info/genes/models_genes.zip"
SITE_URL = "https://genomics.senescence.info/genes/"
USER_AGENT = "dont-die-research/0.1"


def _gene_url(entrez_id: str) -> str:
    return (f"https://www.ncbi.nlm.nih.gov/gene/{entrez_id}" if entrez_id
            else SITE_URL)


def parse_human_rows(csv_text: str) -> List[Dict[str, Any]]:
    """genage_human.csv → one record per curated human aging gene (pure).

    Titles carry "aging" so the gate classifies these honestly: each row IS
    a curated aging gene, the same way DrugAge titles carry "lifespan".
    """
    records = []
    for row in csv.DictReader(io.StringIO(csv_text)):
        symbol = (row.get("symbol") or "").strip()
        name = (row.get("name") or "").strip()
        genage_id = (row.get("GenAge ID") or "").strip()
        if not symbol or not genage_id:
            continue
        entrez = (row.get("entrez gene id") or "").strip()
        why = (row.get("why") or "").strip()

        records.append(
            {
                "source": SOURCE,
                "item_id": f"human-{genage_id}",
                "title": f"{symbol} ({name}) — human aging gene (GenAge)",
                "url": _gene_url(entrez),
                "published": "",  # curated entries carry no date
                "authors": [],
                "summary": (
                    f"GenAge-curated candidate gene of human aging: {symbol} "
                    f"({name}). Included on {why or 'unspecified'} evidence. "
                    f"Entrez gene: {entrez or '—'}. "
                    f"Data from GenAge (Human Ageing Genomic Resources), "
                    "reused under CC BY 3.0."
                ),
                "gene_symbol": symbol,
                "gene_name": name,
                "entrez_id": entrez,
                "uniprot": (row.get("uniprot") or "").strip(),
                "evidence": why,
                "dataset": "human",
                "domain_query": "genetics-data",
            }
        )
    return records


def parse_models_rows(csv_text: str) -> List[Dict[str, Any]]:
    """genage_models.csv → one record per gene × organism manipulation."""
    records = []
    for row in csv.DictReader(io.StringIO(csv_text)):
        symbol = (row.get("symbol") or "").strip()
        organism = (row.get("organism") or "").strip()
        if not symbol or not organism:
            continue
        entrez = (row.get("entrez gene id") or "").strip()
        name = (row.get("name") or "").strip()
        effect = (row.get("lifespan effect") or "").strip()
        influence = (row.get("longevity influence") or "").strip()
        change = (row.get("avg lifespan change (max obsv)") or "").strip()

        key = f"{symbol}|{organism}"
        item = hashlib.sha1(key.encode()).hexdigest()[:16]

        records.append(
            {
                "source": SOURCE,
                "item_id": item,
                "title": f"{symbol} in {organism} — {influence or 'lifespan'} "
                        "(GenAge)",
                "url": _gene_url(entrez),
                "published": "",
                "authors": [],
                "summary": (
                    f"GenAge-curated model-organism result: manipulating "
                    f"{symbol} ({name}) in {organism} changes lifespan. "
                    f"Longevity influence: {influence or '—'}; "
                    f"lifespan effect: {effect or '—'}; average lifespan "
                    f"change (max observed): {change or '—'}%. "
                    "Data from GenAge (Human Ageing Genomic Resources), "
                    "reused under CC BY 3.0."
                ),
                "gene_symbol": symbol,
                "gene_name": name,
                "organism": organism,
                "entrez_id": entrez,
                "lifespan_effect": effect,
                "longevity_influence": influence,
                "avg_lifespan_change_percent": change,
                "dataset": "models",
                "domain_query": "genetics-data",
            }
        )
    return records


def _read_zip(url: str) -> str:
    """Download one GenAge zip and return its CSV content."""
    resp = requests.get(url, timeout=120,
                        headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as bundle:
        csv_name = next(n for n in bundle.namelist() if n.endswith(".csv"))
        return bundle.read(csv_name).decode("utf-8")


def fetch(
    days: int = 7,
    limit: int = 0,
    queries: Optional[List] = None,
) -> Dict[str, Any]:
    """Download both GenAge snapshots and re-land every gene row."""
    from .. import config

    summary: Dict[str, Any] = {"new": 0, "total": 0, "per_query": {},
                               "errors": []}
    for label, url, parser in (
        ("human", HUMAN_URL, parse_human_rows),
        ("models", MODELS_URL, parse_models_rows),
    ):
        try:
            for record in parser(_read_zip(url)):
                path = config.LANDING_DIR / SOURCE / f"{record['item_id']}.json"
                is_new = not path.exists()
                land_item(SOURCE, record["item_id"], record)
                summary["total"] += 1
                if is_new:
                    summary["new"] += 1
            summary["per_query"][label] = summary["total"]
        except Exception as exc:  # noqa: BLE001
            summary["errors"].append({"dataset": label, "error": str(exc)})
    summary["fetched_at"] = utc_now_iso()
    return summary
