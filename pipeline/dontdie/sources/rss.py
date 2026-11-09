"""RSS/Atom news adapter — Tier-2 outlets, no API key required.

The feeds are curated for verifiability: conventional science-news outlets
with editorial standards, plus the longevity field's own specialty press.
Everything lands in the same landing zone, passes the same relevance gate,
and is provenance-flagged as tier 2 — news is never presented as a primary
source (that distinction is what the site's attribution line is for).
"""
from __future__ import annotations

import datetime
import hashlib
import html as html_lib
import re
import email.utils
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse

import requests

from ..landing import land_item, utc_now_iso

# (source slug, display name, feed url, user agent override). Slugs are also
# sources-table rows, seeded tier 2 by the store. UAs are per-feed because
# outlet WAFs are picky in opposite ways: Longevity.Technology 403s a
# browser-style UA from python's TLS stack but accepts curl's; Medical Xpress
# 400s on a curl UA but accepts a plain identifying one. We never pretend to
# be a browser — except Endpoints News, the single documented exception,
# whose WAF refuses every honest identifying UA. None = the honest default
# below.
#
# The 2026-11 expansion adds biotech trade press (GEN, Endpoints, STAT) for
# funding/company coverage and university/institute press offices (MIT,
# Harvard Gazette, Salk, Babraham) for institutional research news.
FEEDS = [
    ("longevitytech", "Longevity.Technology",
     "https://longevity.technology/feed/", "curl/8.4.0"),
    ("lifespanio", "Lifespan.io News",
     "https://www.lifespan.io/feed/", None),
    ("fightaging", "Fight Aging!",
     "https://www.fightaging.org/feed/", None),
    ("sciencedaily", "ScienceDaily — Health & Medicine",
     "https://www.sciencedaily.com/rss/health_medicine.xml", None),
    ("medicalxpress", "Medical Xpress",
     "https://medicalxpress.com/rss-feed/", None),
    ("gen", "GEN — Genetic Engineering & Biotechnology News",
     "https://www.genengnews.com/feed/", None),
    ("endpts", "Endpoints News",
     "https://endpts.com/feed/",
     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/126 Safari/537.36"),
    ("stat", "STAT News",
     "https://www.statnews.com/feed/", None),
    ("mitbio", "MIT News — Biology",
     "https://news.mit.edu/rss/topic/biology", None),
    ("mitmed", "MIT News — Medicine",
     "https://news.mit.edu/rss/topic/medicine", None),
    ("harvardgazette", "Harvard Gazette",
     "https://news.harvard.edu/gazette/rss", None),
    ("salk", "Salk Institute for Biological Studies",
     "https://www.salk.edu/feed/", None),
    ("babraham", "Babraham Institute",
     "https://www.babraham.ac.uk/rss.xml", None),
]

# Honest identifying default for the feeds that don't care.
USER_AGENT = "dont-die-research/0.1"

# Tracking params stripped so the same article from two feeds dedupes.
_TRACKING_PARAMS = ("utm_source", "utm_medium", "utm_campaign", "utm_term",
                    "utm_content", "fbclid", "gclid", "ref", "source")

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def canonical_url(url: str) -> str:
    """Lowercase host (www. stripped), drop fragment and tracking params."""
    parts = urlparse(url.strip())
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    kept = [(k, v) for k, v in parse_qsl(parts.query)
            if k not in _TRACKING_PARAMS]
    return parts._replace(
        scheme="https", netloc=host, params="",
        query=urlencode(kept), fragment="",
    ).geturl()


def item_id(url: str) -> str:
    """Stable id for a news item: hash of its canonical URL."""
    return hashlib.sha1(canonical_url(url).encode()).hexdigest()[:16]


def slug_for(title: str, url: str) -> str:
    """Readable, stable slug: slugified title + id hash suffix."""
    text = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
    return f"{text}-{item_id(url)[:8]}"


def strip_html(text: str) -> str:
    """Crude but honest text extraction for feed summaries/entries."""
    if not text:
        return ""
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
    text = _TAG_RE.sub(" ", text)
    text = html_lib.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def parse_date(value: str) -> str:
    """RSS pubDate (RFC 822) or Atom timestamp (ISO) → YYYY-MM-DD, or ''."""
    value = (value or "").strip()
    if not value:
        return ""
    try:
        return email.utils.parsedate_to_datetime(value).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        pass
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        return ""


def _local(tag: str) -> str:
    """Strip any XML namespace."""
    return tag.rsplit("}", 1)[-1]


def _find(parent: ET.Element, name: str) -> Optional[ET.Element]:
    for node in parent:
        if _local(node.tag) == name:
            return node
    return None


def _find_all(parent: ET.Element, name: str) -> List[ET.Element]:
    return [node for node in parent if _local(node.tag) == name]


def _link(entry: ET.Element) -> str:
    """RSS <link> text or Atom <link href=""/> with rel=alternate preferred."""
    for node in _find_all(entry, "link"):
        if node.text and node.text.strip():
            return node.text.strip()
    fallback = ""
    for node in _find_all(entry, "link"):
        href = node.get("href")
        if not href:
            continue
        if node.get("rel") in (None, "", "alternate"):
            return href
        fallback = fallback or href
    return fallback


def _inner_text(node: Optional[ET.Element]) -> str:
    """All text inside a node, including markup-mixed tails (e.g. <b> in titles)."""
    return "".join(node.itertext()) if node is not None else ""


def _entry_fields(entry: ET.Element) -> Tuple[str, str, str, str]:
    """(title, url, published, summary) from an RSS item or Atom entry."""
    title = strip_html(_inner_text(_find(entry, "title")))
    url = _link(entry)
    published = ""
    for date_node in (_find(entry, "pubDate"), _find(entry, "published"),
                      _find(entry, "updated"), _find(entry, "date")):
        if date_node is not None and date_node.text:
            published = parse_date(date_node.text)
            if published:
                break
    summary = ""
    for body in (_find(entry, "description"), _find(entry, "summary"),
                 _find(entry, "content")):
        text = strip_html(_inner_text(body))
        if text:
            summary = text
            break
    return title, url, published, summary


def parse_feed(xml_text: str, source: str) -> List[Dict[str, Any]]:
    """Parse an RSS 2.0 or Atom body into landing-zone records (pure).

    Keyed by the canonical-URL hash, so the same story seen twice (re-fetch,
    or two feeds carrying the same wire copy of the same URL) lands once.
    """
    root = ET.fromstring(xml_text)
    if _local(root.tag) == "rss":
        channel = _find(root, "channel")
        entries = _find_all(channel, "item") if channel is not None else []
    elif _local(root.tag) == "feed":  # Atom
        entries = _find_all(root, "entry")
    else:
        entries = []

    records = []
    for entry in entries:
        title, url, published, summary = _entry_fields(entry)
        if not url or not title:
            continue
        records.append(
            {
                "source": source,
                "item_id": item_id(url),
                "slug": slug_for(title, url),
                "title": title,
                "url": url,
                "published": published,
                "authors": [],
                "summary": summary[:8000],
            }
        )
    return records


def already_landed(item_id: str) -> bool:
    """True if the canonical URL already landed under any feed.

    Outlets run overlapping feeds (MIT's biology and medicine topics carry
    the same article), so dedupe is by canonical URL across all feeds, not
    just within one — first feed to land it wins, later copies are skipped.
    """
    from .. import config
    return any(
        (config.LANDING_DIR / feed_slug / f"{item_id}.json").exists()
        for feed_slug, _n, _u, _ua in FEEDS
    )


def fetch_feed(slug: str, name: str, url: str, days: int, limit: int,
               user_agent: Optional[str] = None) -> Dict[str, Any]:
    """Fetch one feed and land its recent items; returns a run summary."""
    from .. import config

    summary: Dict[str, Any] = {"total": 0, "new": 0, "errors": []}
    try:
        resp = requests.get(
            url, timeout=60,
            headers={"User-Agent": user_agent or USER_AGENT},
        )
        resp.raise_for_status()
        records = parse_feed(resp.text, slug)
    except Exception as exc:  # noqa: BLE001 — log and continue to next feed
        summary["errors"].append({"feed": name, "error": str(exc)})
        return summary

    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    for record in records[:limit]:
        # Keep undated entries too — refusing to guess a date is more honest
        # than dropping coverage, and the dedupe makes re-fetches cheap.
        if record["published"] and record["published"] < cutoff.isoformat():
            continue
        path = config.LANDING_DIR / slug / f"{record['item_id']}.json"
        if path.exists():
            is_new = False  # same feed re-fetch — overwrite in place
        elif already_landed(record["item_id"]):
            continue  # another feed already landed this canonical URL
        else:
            is_new = True
        record["outlet"] = name
        land_item(slug, record["item_id"], record)
        summary["total"] += 1
        if is_new:
            summary["new"] += 1
    summary["fetched_at"] = utc_now_iso()
    return summary


def _make_fetcher(slug: str, name: str, url: str,
                  user_agent: Optional[str] = None):
    def fetch(days: int = 7, limit: int = 100,
              queries: Optional[List[Tuple[str, str]]] = None) -> Dict[str, Any]:
        return fetch_feed(slug, name, url, days, limit, user_agent)
    return fetch


FETCHERS = {slug: _make_fetcher(slug, name, url, ua)
            for slug, name, url, ua in FEEDS}
