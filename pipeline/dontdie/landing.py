"""Raw JSON landing zone — one file per source item, keyed by stable source id.

The landing zone is the dedupe mechanism: an item's id (PMID, NCT id, …) is its
filename, so a re-fetch overwrites the same path instead of duplicating. Every
file carries the fetch metadata (source, query/domain, fetched_at) alongside
the source payload, so any item is re-derivable and auditable.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any, Dict

from . import config


def utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def land_item(source: str, item_id: str, record: Dict[str, Any]) -> Path:
    """Write one item's raw record; returns the landing path.

    `record` should contain the normalized front matter (title, url, …) plus a
    `payload` key with the verbatim source data. Fetch metadata is added here.
    """
    path = config.LANDING_DIR / source / f"{item_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "source": source,
        "item_id": item_id,
        "fetched_at": utc_now_iso(),
        **record,
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True, default=str))
    tmp.replace(path)
    return path


def append_fetch_log(run: Dict[str, Any]) -> None:
    config.FETCH_LOG.parent.mkdir(parents=True, exist_ok=True)
    with config.FETCH_LOG.open("a") as f:
        f.write(json.dumps(run, default=str) + "\n")
