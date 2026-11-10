"""LLM extraction pass (M5): one labeled, structured read of every relevant
item — the fields the site surfaces as clearly-generated, never merged with
source truth.

Extracted fields (one `extractions` row each, with model + date):

- **summary** — one plain-language sentence of what the record shows.
- **evidence** — the evidence level: human / animal / cell / dataset /
  registry / grant / other. A mouse or cell result is never presented as
  human; this field is what makes that checkable.
- **interventions** — the intervention names the record actually studies
  (max 5).
- **outcome** — one short phrase for what was measured / the headline result.

This module is a PAID job and is gated like the research agents: a dry run
by default (counts, cost estimate, sample prompt — no API call, no key),
and `--go` as the explicit, per-job approval. `run` never includes it.

Idempotency: UNIQUE (item_id, field) + upsert. Items already extracted with
the current model are skipped, so a re-run is free; bumping the model
(DD_EXTRACT_MODEL) re-extracts everything, which is an explicit paid
decision, not an accident. Realtime mode handles the daily trickle; the
Batch API (50% cost) handles the one-time backfill — `--batch` submits and
records the batch id, `--collect` downloads results (retrieval is free).
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from . import config, store

MODEL = os.environ.get("DD_EXTRACT_MODEL", "claude-haiku-4-5-20251001")

FIELDS = ("summary", "evidence", "interventions", "outcome")
EVIDENCE_LEVELS = (
    "human", "animal", "cell", "dataset", "registry", "grant", "other",
)

# Per-request caps. 300 output tokens is generous for ~4 short fields.
MAX_TOKENS = 300
# Abstracts longer than this are truncated — ~2k tokens is plenty to summarize.
TEXT_CHAR_CAP = 8000
# The Batch API caps a batch at 100,000 requests; we chunk below that anyway.
BATCH_CHUNK = 50000

# List prices, $ per million tokens (input, output) — for the dry-run cost
# estimate only; the bill is whatever the API reports.
PRICES: Dict[str, tuple] = {
    "claude-haiku-4-5-20251001": (1.0, 5.0),
}
DEFAULT_PRICE = (1.0, 5.0)

SYSTEM_PROMPT = (
    "You extract structured facts from life-extension science records for a "
    "public knowledge base. Answer with ONLY a JSON object, no prose, no "
    "fences, with exactly these keys:\n"
    '"summary": one plain-language sentence (max 200 chars) of what this '
    "record shows;\n"
    '"evidence": the evidence level, one of "human", "animal", "cell", '
    '"dataset", "registry", "grant", "other" — an animal or cell result is '
    "never human;\n"
    '"interventions": the names of the interventions the record studies '
    "(drugs, peptides, compounds; max 5, [] if none);\n"
    '"outcome": one short phrase (max 120 chars) for what was measured or '
    "the headline result."
)

_BODY_FIELDS = ("abstract", "brief_summary", "summary")


def _client():
    """Lazily import and return an Anthropic client, or exit honestly."""
    import anthropic  # noqa: PLC0415 — optional dependency, opt-in feature

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set — the extraction pass is an "
            "opt-in, keyed feature. The pipeline itself needs no keys."
        )
    return anthropic.Anthropic()


def item_text(title: Optional[str], raw_text: Dict[str, Any]) -> str:
    """The text the model reads: title plus the record's body fields."""
    parts = [p for p in (title, *(raw_text.get(f) for f in _BODY_FIELDS))
             if p]
    return "\n\n".join(parts)[:TEXT_CHAR_CAP]


def user_message(source: str, title: Optional[str], text: str) -> str:
    return f"Source: {source}\nTitle: {title}\n\n{text}"


def _parse_payload(text: str) -> Optional[Dict[str, Any]]:
    """Pull the first JSON object out of a model response (tolerate fences
    and stray prose); None if there is no parsable object."""
    text = re.sub(r"(?s)```(?:json)?|```", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def validate(raw: Any) -> Optional[Dict[str, Any]]:
    """Clean a parsed payload into the four fields, or reject it (None).
    A rejected item stays pending, so the next run retries it."""
    if not isinstance(raw, dict):
        return None

    summary = raw.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return None
    summary = " ".join(summary.split())[:300]

    evidence = raw.get("evidence")
    if not isinstance(evidence, str) or \
            evidence.strip().lower() not in EVIDENCE_LEVELS:
        return None
    evidence = evidence.strip().lower()

    interventions = raw.get("interventions")
    if interventions is None:
        interventions = []
    if not isinstance(interventions, list):
        return None
    interventions = [
        " ".join(str(n).split())[:100]
        for n in interventions if str(n).strip()
    ][:5]

    outcome = raw.get("outcome")
    if not isinstance(outcome, str) or not outcome.strip():
        return None
    outcome = " ".join(outcome.split())[:160]

    return {
        "summary": summary,
        "evidence": evidence,
        "interventions": interventions,
        "outcome": outcome,
    }


def _message_text(message: Any) -> str:
    return "".join(
        block.text for block in message.content if block.type == "text"
    )


def pending(
    dsn: Optional[str] = None, model: str = MODEL,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Relevant, un-retracted items with no extraction at the current model —
    plus the honest denominators for the dry-run report."""
    conn = store.connect(dsn)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT i.id, i.source, i.title,
                       i.raw->>'abstract', i.raw->>'brief_summary',
                       i.raw->>'summary'
                FROM items i
                WHERE i.is_relevant AND NOT i.is_retracted
                  AND NOT EXISTS (
                      SELECT 1 FROM extractions e
                      WHERE e.item_id = i.id AND e.model = %s
                  )
                ORDER BY i.id
                """
                + (f" LIMIT {int(limit)}" if limit else ""),
                (model,),
            )
            rows = cur.fetchall()
            cur.execute(
                "SELECT count(DISTINCT e.item_id) FROM extractions e"
                " WHERE e.model = %s",
                (model,),
            )
            already = cur.fetchone()[0]
    finally:
        conn.close()
    return {
        "items": [
            {"id": r[0], "source": r[1], "title": r[2],
             "text": item_text(r[2], {"abstract": r[3], "brief_summary": r[4],
                                      "summary": r[5]})}
            for r in rows
        ],
        "already": already,
        "model": model,
    }


def estimate_cost(items: List[Dict[str, Any]]) -> Dict[str, float]:
    """A list-price estimate for the pending items, realtime and batch.
    ~4 chars/token on input; output is capped by MAX_TOKENS."""
    in_tok = sum(
        (len(SYSTEM_PROMPT) + len(user_message(i["source"], i["title"],
                                               i["text"]))) / 4
        for i in items
    )
    out_tok = MAX_TOKENS * len(items)
    pin, pout = PRICES.get(MODEL, DEFAULT_PRICE)
    realtime = in_tok / 1e6 * pin + out_tok / 1e6 * pout
    return {
        "input_tokens": int(in_tok),
        "output_tokens": int(out_tok),
        # 4 decimals: a 2-item test run costs fractions of a cent.
        "realtime": round(realtime, 4),
        "batch": round(realtime / 2, 4),
    }


def _store_fields(
    dsn: Optional[str], item_id: int, fields: Dict[str, Any], model: str
) -> None:
    conn = store.connect(dsn)
    try:
        with conn, conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO extractions (item_id, field, value, model)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (item_id, field)
                DO UPDATE SET value = EXCLUDED.value, model = EXCLUDED.model,
                              extracted_at = now()
                """,
                [(item_id, f, json.dumps(fields[f]), model) for f in FIELDS],
            )
    finally:
        conn.close()


def run(
    go: bool = False,
    model: str = MODEL,
    limit: Optional[int] = None,
    batch: bool = False,
    client: Any = None,
    dsn: Optional[str] = None,
) -> Dict[str, Any]:
    """The extraction pass. Dry run unless go=True — the explicit, per-job
    approval; a dry run makes no API call and needs no key."""
    queue = pending(dsn, model, limit)

    if not go:
        sample = queue["items"][0] if queue["items"] else None
        return {
            "go": False,
            "batch": batch,
            "model": model,
            "pending": len(queue["items"]),
            "already": queue["already"],
            **(estimate_cost(queue["items"]) if queue["items"] else
               {"input_tokens": 0, "output_tokens": 0,
                "realtime": 0.0, "batch": 0.0}),
            "sample_prompt": (user_message(sample["source"], sample["title"],
                                            sample["text"])
                              if sample else None),
        }

    if client is None:
        client = _client()
    if batch:
        return _submit_batch(client, queue["items"], model)
    return _run_realtime(client, queue["items"], model, dsn)


def _run_realtime(
    client: Any, items: List[Dict[str, Any]], model: str,
    dsn: Optional[str] = None,
) -> Dict[str, Any]:
    """Sequential messages.create — the daily-trickle path."""
    extracted, failed, fields_written = 0, 0, 0
    for item in items:
        try:
            message = client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message(
                    item["source"], item["title"], item["text"])}],
            )
            fields = validate(_parse_payload(_message_text(message)))
            if fields is None:
                failed += 1
                continue
            _store_fields(dsn, item["id"], fields, model)
            extracted += 1
            fields_written += len(FIELDS)
        except Exception:  # noqa: BLE001 — one bad item never stops the pass
            failed += 1
    return {"go": True, "batch": False, "model": model,
            "items": len(items), "extracted": extracted, "failed": failed,
            "fields": fields_written}


def _submit_batch(
    client: Any, items: List[Dict[str, Any]], model: str,
) -> Dict[str, Any]:
    """Submit pending items as one Batch API job (50% cost) and record the
    batch id in the state file. Results are downloaded later by collect()."""
    batch_ids = []
    for start in range(0, len(items), BATCH_CHUNK):
        chunk = items[start : start + BATCH_CHUNK]
        batch = client.messages.batches.create(
            requests=[
                {"custom_id": str(i["id"]),
                 "params": {
                     "model": model,
                     "max_tokens": MAX_TOKENS,
                     "system": SYSTEM_PROMPT,
                     "messages": [{"role": "user", "content": user_message(
                         i["source"], i["title"], i["text"])}],
                 }}
                for i in chunk
            ]
        )
        batch_ids.append(batch.id)
    config.EXTRACT_BATCH.parent.mkdir(parents=True, exist_ok=True)
    config.EXTRACT_BATCH.write_text(json.dumps(
        {"batch_ids": batch_ids, "model": model, "items": len(items)},
        indent=2,
    ))
    return {"go": True, "batch": True, "model": model, "items": len(items),
            "batch_ids": batch_ids}


def collect(
    batch_id: Optional[str] = None,
    client: Any = None,
    dsn: Optional[str] = None,
) -> Dict[str, Any]:
    """Download the results of a submitted batch and store them. Retrieval
    is free, so no --go is needed — the spend happened at submit time."""
    if client is None:
        client = _client()
    if batch_id is None:
        if not config.EXTRACT_BATCH.exists():
            raise SystemExit(
                "No batch id given and no submitted batch on record "
                f"({config.EXTRACT_BATCH}) — submit one with "
                "`extract --go --batch` first."
            )
        batch_id = json.loads(config.EXTRACT_BATCH.read_text())["batch_ids"][0]

    info = client.messages.batches.retrieve(batch_id)
    if info.processing_status != "ended":
        return {"batch_id": batch_id, "status": info.processing_status,
                "stored": 0, "failed": 0, "pending": True}

    model = getattr(info, "model", None) or MODEL
    stored, failed = 0, 0
    for result in client.messages.batches.results(batch_id):
        if result.result.type != "succeeded":
            failed += 1
            continue
        text = _message_text(result.result.message)
        fields = validate(_parse_payload(text))
        if fields is None:
            failed += 1
            continue
        _store_fields(dsn, int(result.custom_id), fields, model)
        stored += 1
    return {"batch_id": batch_id, "status": info.processing_status,
            "stored": stored, "failed": failed, "pending": False}
