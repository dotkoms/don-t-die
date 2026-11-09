"""Multi-agent research layer — news scout, verifier, synthesizer.

Built per the plan's honesty principles:

- the **news scout** is an LLM agent with server-side web search, restricted
  to the outlet allowlist (``agents/outlets.py``), so "conventional but
  verifiable" is enforced by the tool, not by the model's judgment;
- the **primary scout** is free and deterministic — an NCBI esearch for the
  target, so every research note is anchored to primary literature at zero
  cost;
- the **verifier** is deterministic code, not a model: a URL is on the
  allowlist or it is not, and only verified sources are attached to a note;
- the **synthesizer** writes the note from fetched article text and is
  labeled with its model in ``research_notes`` (never merged with source
  truth).

No paid run happens without an explicit, per-job go — ``--go`` on the CLI —
even when ``ANTHROPIC_API_KEY`` is set. The default invocation is a dry run
that prints the plan and the cost estimate.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

import requests

from .. import config
from ..sources import rss as rss_mod
from ..sources import pubmed as pubmed_mod
from . import outlets

# Default model for the scout and synthesizer agents. Opus 5 per the project
# default; override per-run with --model or DD_RESEARCH_MODEL.
DEFAULT_MODEL = os.environ.get("DD_RESEARCH_MODEL", "claude-opus-5")

# Rough per-run shape for the dry-run cost estimate. Honest bounds, labeled
# as an estimate: a few allowlisted web searches plus one synthesis pass.
_ESTIMATED_SEARCHES = 5          # news scout's web_search budget
_ESTIMATED_INPUT_TOKENS = 60_000  # fetched article text into the synthesizer
_ESTIMATED_OUTPUT_TOKENS = 4_000

SCOUT_SYSTEM = (
    "You are the news scout for a life-extension medical science knowledge "
    "base. Find recent, substantive news and update coverage of the research "
    "target, only on the allowed news outlets. Prefer reporting that names "
    "its primary source (a study, a trial, a paper). Ignore press releases "
    "for supplements, marketing pages, and opinion. Respond with ONLY a "
    "JSON array of objects {\"title\", \"url\", \"note\"} where url is the "
    "outlet article URL and note is one sentence on why it matters."
)

SYNTH_SYSTEM = (
    "You write research notes for a public life-extension knowledge base. "
    "You may cite ONLY the numbered sources provided — no outside knowledge "
    "presented as fact. Distinguish human evidence from animal and in-vitro "
    "evidence explicitly; say what is unknown; flag where news coverage is "
    "ahead of the primary literature. Write compact markdown with [n] "
    "citations and a final 'Sources' section is unnecessary (stored "
    "separately). Never invent a study, dose, or trial number."
)


def plan(target: str, model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    """The run manifest for a target (pure — used by the dry run and tests)."""
    return {
        "target": target,
        "model": model,
        "steps": [
            {"agent": "news scout",
             "detail": f"web search for '{target}' on "
                       f"{len(outlets.NEWS_OUTLETS)} allowlisted outlets "
                       f"(LLM + server-side web search)"},
            {"agent": "primary scout",
             "detail": "PubMed esearch + efetch for the target (free, "
                       "deterministic)"},
            {"agent": "verifier",
             "detail": "allowlist check on every candidate URL "
                       "(deterministic, no model)"},
            {"agent": "synthesizer",
             "detail": "write the note from fetched article text (LLM), "
                       "stored labeled by model"},
        ],
        "estimate": {
            "web_searches": _ESTIMATED_SEARCHES,
            "input_tokens": _ESTIMATED_INPUT_TOKENS,
            "output_tokens": _ESTIMATED_OUTPUT_TOKENS,
            "note": "rough estimate, typically well under $1 per target",
        },
    }


def _client():
    """Lazily import and return an Anthropic client, or exit honestly."""
    import anthropic  # noqa: PLC0415 — optional dependency, opt-in feature

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set — the research agents are an "
            "opt-in, keyed feature. The pipeline itself needs no keys."
        )
    return anthropic.Anthropic()


def _extract_json_array(text: str) -> List[Dict[str, Any]]:
    """Pull the first JSON array out of a model response (tolerate fences)."""
    text = re.sub(r"(?s)```(?:json)?|```", "", text)
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        parsed = json.loads(text[start : end + 1])
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def _text_blocks(message) -> str:
    return "".join(
        block.text for block in message.content if block.type == "text"
    )


def scout_news(target: str, client, model: str) -> List[Dict[str, Any]]:
    """LLM agent: find allowlisted news coverage of the target."""
    response = client.messages.create(
        model=model,
        max_tokens=6000,
        system=SCOUT_SYSTEM,
        thinking={"type": "adaptive"},
        tools=[{
            "type": "web_search_20260209",
            "name": "web_search",
            "max_uses": _ESTIMATED_SEARCHES,
            "allowed_domains": outlets.web_search_domains(),
        }],
        messages=[{
            "role": "user",
            "content": (
                f"Research target: {target}. Find up to 6 pieces of recent "
                f"news or update coverage worth attaching to its research "
                f"note."
            ),
        }],
    )
    candidates = _extract_json_array(_text_blocks(response))
    out = []
    for item in candidates:
        url = (item.get("url") or "").strip()
        if url:
            out.append({
                "title": (item.get("title") or url).strip(),
                "url": url,
                "note": (item.get("note") or "").strip(),
            })
    return out


def scout_primary(target: str, limit: int = 6) -> List[Dict[str, Any]]:
    """Deterministic scout: recent PubMed-indexed literature for the target.

    Free (E-utilities, unauthenticated), verifiable by construction — the
    URLs are NCBI record URLs.
    """
    try:
        params = {
            "db": "pubmed", "term": f"{target}[Title/Abstract]",
            "retmode": "json", "retmax": limit, "sort": "pub_date",
            "datetype": "edat", "reldate": 365,
            **pubmed_mod._ncbi_params(),
        }
        resp = pubmed_mod._get(
            f"{config.NCBI_EUTILS_BASE_URL}/esearch.fcgi", params
        )
        pmids = pubmed_mod.parse_esearch(resp.json())
        if not pmids:
            return []
        efetch = pubmed_mod._get(
            f"{config.NCBI_EUTILS_BASE_URL}/efetch.fcgi",
            {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml",
             **pubmed_mod._ncbi_params()},
        )
    except Exception:  # noqa: BLE001 — primary scout is best-effort, free
        return []
    return [
        {
            "title": record["title"],
            "url": record["url"],
            "kind": "primary",
            "note": "PubMed-indexed literature",
            "abstract": (record.get("abstract") or "")[:4000],
        }
        for record in pubmed_mod.parse_efetch_xml(efetch.text)
    ]


def verify(candidates: List[Dict[str, Any]],
           max_sources: int = 12) -> List[Dict[str, Any]]:
    """Deterministic gate: keep only allowlisted candidates, deduped by URL.

    Attaches kind/outlet from the allowlist; anything unverifiable is
    reported (so the operator sees what was refused), not silently dropped.
    """
    kept: List[Dict[str, Any]] = []
    refused: List[str] = []
    seen = set()
    for cand in candidates:
        url = cand.get("url", "").strip()
        if not url:
            continue
        key = rss_mod.canonical_url(url)
        if key in seen:
            continue
        kind, outlet = outlets.verify_url(url)
        if not kind:
            refused.append(url)
            continue
        seen.add(key)
        kept.append({**cand, "url": url, "kind": kind, "outlet": outlet,
                     "verified": True})
    return kept[:max_sources], refused


def fetch_text(url: str) -> str:
    """Fetch one article and strip it to text (in-memory only; never stored).

    Some outlets 403 the honest fetcher UA (see rss.FEEDS notes); a curl UA
    retry is enough for the allowlisted set.
    """
    try:
        resp = requests.get(
            url, timeout=60, headers={"User-Agent": rss_mod.USER_AGENT}
        )
        if resp.status_code == 403:
            resp = requests.get(
                url, timeout=60, headers={"User-Agent": "curl/8.4.0"}
            )
        resp.raise_for_status()
        return rss_mod.strip_html(resp.text)[:6000]
    except Exception:  # noqa: BLE001 — a dead link is a skip, not a failure
        return ""


def synthesize(target: str, sources: List[Dict[str, Any]], client,
               model: str) -> str:
    """LLM agent: write the note from the verified sources' text."""
    blocks = []
    for i, src in enumerate(sources, 1):
        excerpt = src.get("abstract") or src.get("text") or src.get("note") or ""
        blocks.append(
            f"[{i}] ({src['kind']}; {src.get('outlet', '')}) {src['title']}\n"
            f"    {src['url']}\n    {excerpt[:4000]}"
        )
    response = client.messages.create(
        model=model,
        max_tokens=8000,
        system=SYNTH_SYSTEM,
        thinking={"type": "adaptive"},
        messages=[{
            "role": "user",
            "content": (
                f"Research target: {target}\n\nVerified sources:\n\n"
                + "\n\n".join(blocks)
                + "\n\nWrite the research note (markdown, [n] citations)."
            ),
        }],
    )
    return _text_blocks(response).strip()


def slugify(target: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", target.lower()).strip("-")


def run(target: str, go: bool = False, model: Optional[str] = None,
         dsn: Optional[str] = None) -> int:
    """Run the agent pipeline for one target. Dry-run unless go=True."""
    model = model or DEFAULT_MODEL
    manifest = plan(target, model)
    print(f"research plan for '{target}' (model {model}):")
    for i, step in enumerate(manifest["steps"], 1):
        print(f"  {i}. {step['agent']}: {step['detail']}")
    est = manifest["estimate"]
    print(
        f"  cost estimate: ~{est['web_searches']} web searches, "
        f"~{est['input_tokens']} in / ~{est['output_tokens']} out tokens "
        f"({est['note']})"
    )

    if not go:
        print(
            "\ndry run — nothing fetched, nothing spent. This is a paid "
            "LLM job, so it runs only on an explicit per-job go:\n"
            f"  python3 -m dontdie research {target!r} --go"
        )
        return 0
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "\nANTHROPIC_API_KEY is not set — the research agents are an "
            "opt-in, keyed feature (the pipeline itself needs no keys).",
        )
        return 2

    client = _client()

    news = scout_news(target, client, model)
    print(f"news scout: {len(news)} candidates")
    primary = scout_primary(target)
    print(f"primary scout: {len(primary)} PubMed records")

    verified, refused = verify(news + primary)
    print(f"verifier: {len(verified)} verified, {len(refused)} refused")
    for url in refused:
        print(f"  refused (not on the outlet allowlist): {url}")

    if not verified:
        print("no verified sources — nothing to synthesize. Not stored.")
        return 1

    for src in verified:
        if src["kind"] == "news":
            src["text"] = fetch_text(src["url"])
    verified = [s for s in verified if s["kind"] == "primary" or s.get("text")]

    note = synthesize(target, verified, client, model)

    note_doc = {
        "slug": f"research-{slugify(target)}",
        "target": target,
        "summary": note,
        "model": model,
        "status": "draft",
        "sources": [
            {"kind": s["kind"], "title": s["title"], "url": s["url"],
             "verified": True}
            for s in verified
        ],
    }
    if not os.environ.get("DATABASE_URL") and not dsn:
        print(
            "\nDATABASE_URL is not set — note not stored. Full text:\n\n"
            + note
        )
        return 0
    from .. import store  # noqa: PLC0415 — keeps the no-key path import-free

    note_id = store.save_research_note(note_doc, dsn=dsn)
    print(
        f"\nresearch note stored (id {note_id}, slug {note_doc['slug']}, "
        f"{len(verified)} sources, model {model}):\n\n{note}"
    )
    return 0
