"""The verifiability contract for the research agents.

"Conventional but verifiable news and update outlets" is operationalized as
an allowlist: outlets with editorial standards or institutional provenance —
the feeds the pipeline already ingests, plus conventional science press.
Anything not on the list (blogs, forums, marketing pages) is never attached
to a research note. Primary sources verify by being primary.
"""
from __future__ import annotations

from typing import Optional, Tuple
from urllib.parse import urlparse

# News / update outlets (tier 2): hostname (apex) → display name.
NEWS_OUTLETS = {
    "longevity.technology": "Longevity.Technology",
    "lifespan.io": "Lifespan.io",
    "fightaging.org": "Fight Aging!",
    "sciencedaily.com": "ScienceDaily",
    "medicalxpress.com": "Medical Xpress",
    "reuters.com": "Reuters",
    "apnews.com": "AP News",
    "statnews.com": "STAT News",
    "the-scientist.com": "The Scientist",
    "fiercebiotech.com": "Fierce Biotech",
    "genengnews.com": "GEN — Genetic Engineering & Biotechnology News",
    "endpts.com": "Endpoints News",
    "eurekalert.org": "EurekAlert! (institutional press releases)",
    "newscientist.com": "New Scientist",
}

# Primary sources: journals, indexes, trial registries, preprint servers.
# An article on one of these hosts is evidence, not coverage of evidence.
# A tuple in specificity order — pubmed.ncbi.nlm.nih.gov must win over its
# parent ncbi.nlm.nih.gov when naming the source.
PRIMARY_HOSTS = (
    "pubmed.ncbi.nlm.nih.gov", "clinicaltrials.gov", "doi.org", "dx.doi.org",
    "medrxiv.org", "biorxiv.org", "arxiv.org",
    "nature.com", "science.org", "cell.com", "jamanetwork.com", "nejm.org",
    "thelancet.com", "sciencedirect.com", "link.springer.com", "springer.com",
    "onlinelibrary.wiley.com", "academic.oup.com", "frontiersin.org",
    "journals.plos.org", "plos.org", "mdpi.com", "elifesciences.org",
    "pnas.org", "jci.org", "ncbi.nlm.nih.gov", "nih.gov",
)

# nature.com hosts both its journal and its news desk; it is classified as
# primary (journal first) and the synthesizer treats it accordingly.


def _host(url: str) -> str:
    return (urlparse(url).netloc or "").lower().removeprefix("www.")


def verify_url(url: str) -> Tuple[str, str]:
    """Classify a URL: ('news'|'primary', outlet name) or ('', '')."""
    host = _host(url)
    for apex, name in NEWS_OUTLETS.items():
        if host == apex or host.endswith("." + apex):
            return "news", name
    for apex in PRIMARY_HOSTS:
        if host == apex or host.endswith("." + apex):
            return "primary", apex
    return "", ""


def is_verified(url: str) -> bool:
    kind, _ = verify_url(url)
    return kind in ("news", "primary")


def web_search_domains() -> list:
    """Domains the news scout's server-side web search is restricted to."""
    return sorted(NEWS_OUTLETS.keys())
