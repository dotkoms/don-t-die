from . import ctgov, pubmed, rss  # noqa: F401

SOURCES = {
    pubmed.SOURCE: pubmed.fetch,
    ctgov.SOURCE: ctgov.fetch,
    **rss.FETCHERS,
}
