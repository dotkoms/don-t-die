"""Deterministic relevance tagging (v1) — keywords, not ML.

The domain queries over-fetch (a "longevity" PubMed search happily returns
papers about the longevity of dental fillings), so before an item is shown it
passes a transparent keyword gate. This is deliberately naive and labeled:
`relevance_method` records which gate version made the call, and nothing here
is presented as learned or statistical — it is a visible, auditable filter.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

# (pattern, needs_word_boundary). Whole words are matched on boundaries so
# "aging" does not hit "imaging" and "aged" does not hit "damaged"; stems
# (senescen-, rejuvenat-, …) are matched as substrings so inflections work.
AGING_TERMS: List[Tuple[str, bool]] = [
    ("aging", True), ("ageing", True), ("aged", True),
    ("senescen", False), ("senolytic", False),
    ("geroscience", False), ("gerontolog", False), ("geriatric", False),
    ("longevity", False), ("lifespan", False), ("life span", True),
    ("life extension", True), ("rejuvenat", False), ("biological age", True),
    ("epigenetic clock", False), ("mTOR", False), ("metformin", False),
    ("rapamycin", False), ("autophagy", False), ("yamanaka", False),
    ("nicotinamide", False), ("NAD+", False), ("telomere", False),
    ("healthspan", False), ("health span", True),
    ("caloric restriction", True), ("calorie restriction", True),
    ("dietary restriction", True), ("age-related", True),
    ("age associated", True), ("mortality", False),
]

# Strong false-positive sources inside those terms; e.g. "aging" of materials.
EXCLUDE_HINTS = [
    "dental", "composite", "resin", "concrete", "batter", "capacitor",
    "corrosion", "paint", "coating", "adhesive", "photovoltaic", "bitumen",
    "asphalt", "weld", "solder",
]

# Aging-specific terms strong enough to keep an item even if a materials
# hint appears (aging is also a materials-science word).
STRONG_TERMS = [
    "senescen", "senolytic", "geroscience", "gerontolog", "longevity",
    "lifespan", "life span", "rejuvenat", "healthspan", "geriatric",
    "epigenetic clock", "biological age", "caloric restriction",
    "calorie restriction", "dietary restriction", "life extension", "yamanaka",
]

_TERM_RE = [
    (re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE) if bounded
     else re.compile(re.escape(term), re.IGNORECASE), term)
    for term, bounded in AGING_TERMS
]


def _search_text(record: Dict[str, Any]) -> str:
    fields = ["title", "abstract", "brief_summary", "official_title"]
    return " ".join(record.get(f) or "" for f in fields).lower()


def classify(record: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Return (is_relevant, matched_terms) for a landing-zone record."""
    text = _search_text(record)
    matched = sorted({term for regex, term in _TERM_RE if regex.search(text)})
    if not matched:
        return False, []
    if any(hint in text for hint in EXCLUDE_HINTS) and not any(
        term.lower() in text for term in STRONG_TERMS
    ):
        return False, []
    return True, matched


def tag(record: Dict[str, Any]) -> Dict[str, Any]:
    """Return the record plus relevance fields (does not mutate)."""
    is_relevant, matched = classify(record)
    out = dict(record)
    out["is_relevant"] = is_relevant
    out["relevance_terms"] = matched
    out["relevance_method"] = "keyword-v1"
    return out
