from . import ctgov, pubmed  # noqa: F401

SOURCES = {
    pubmed.SOURCE: pubmed.fetch,
    ctgov.SOURCE: ctgov.fetch,
}
