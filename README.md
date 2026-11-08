# don-t-die

A public knowledge base and research system for life-extension / longevity
medical science: a pipeline that gathers from free public sources (PubMed,
ClinicalTrials.gov, preprints, …), normalizes and dedupes, and a Next.js site
that publishes the corpus as a browsable knowledge base with a weekly digest.

- **Plan / decision log**: [`docs/PLAN.md`](docs/PLAN.md)
- **`pipeline/`** — Python fetch, normalize, dedupe, extraction (the data half)
- **`site/`** — Next.js/TypeScript public site (the product half)

Both halves share one Postgres (Neon in production); the site reads it through
a read-only role and never imports pipeline code.

Requires no API keys for a first local run. Run the fetcher:

```sh
cd pipeline
python3 -m dontdie fetch            # all sources, defaults
python3 -m dontdie fetch --source pubmed --days 7 --limit 50
```

Raw items land in `pipeline/state/landing/` (gitignored), one JSON file per
source item — re-fetching the same item overwrites the same path, which is the
dedupe mechanism.

Tests: `cd pipeline && python3 -m pytest` (offline, fixtures only).
