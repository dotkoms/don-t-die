from . import (  # noqa: F401
    cordis, ctgov, ctis, drugage, europemc, isrctn, pubmed, reporter, rss,
)

SOURCES = {
    pubmed.SOURCE: pubmed.fetch,
    ctgov.SOURCE: ctgov.fetch,
    **rss.FETCHERS,
    europemc.SOURCE: europemc.fetch,
    drugage.SOURCE: drugage.fetch,
    isrctn.SOURCE: isrctn.fetch,
    ctis.SOURCE: ctis.fetch,
    reporter.SOURCE: reporter.fetch,
    cordis.SOURCE: cordis.fetch,
}
