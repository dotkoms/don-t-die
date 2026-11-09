from . import (  # noqa: F401
    ctgov, ctis, drugage, europemc, isrctn, pubmed, rss,
)

SOURCES = {
    pubmed.SOURCE: pubmed.fetch,
    ctgov.SOURCE: ctgov.fetch,
    **rss.FETCHERS,
    europemc.SOURCE: europemc.fetch,
    drugage.SOURCE: drugage.fetch,
    isrctn.SOURCE: isrctn.fetch,
    ctis.SOURCE: ctis.fetch,
}
