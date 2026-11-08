# don't die

**A public knowledge base for life-extension medical science.**

A pipeline gathers the field's evidence from free public sources — PubMed and
ClinicalTrials.gov today, preprints and more as the system grows — normalizes,
dedupes, and relevance-tags every item. A website publishes the result: a
browsable domain map into entity pages, item pages with full source attribution,
corpus search, and (publishing from M2) a weekly digest of what actually
changed.

The full plan and decision log live in [`docs/PLAN.md`](docs/PLAN.md).

## Roadmap

| Milestone | Scope | Status |
|---|---|---|
| M0 | Source adapters (PubMed, ClinicalTrials.gov), raw JSON landing zone, dedupe | **Done** |
| M1 | Postgres store, relevance gate, web app skeleton (domain map, item pages, search) | **Done** |
| M2 | Weekly digest as the landing page's top section | Planned |
| M3 | Entity pages (compounds, trials, orgs) — the digest's destinations | Planned |
| M4 | LLM extraction pass with labeled, provenance-safe fields | Planned |
| M5 | Tracking / follow features for visitors | Planned |

## Principles

- **No API keys for a first run.** Everything needed to fetch and browse works
  with zero credentials; keyed providers are opt-in only.
- **The landing zone is the dedupe.** One JSON file per source item, keyed by
  its stable id (PMID, NCT id) — a re-fetch overwrites the same path instead of
  duplicating.
- **Honest labeling.** Relevance is a transparent keyword gate
  (`keyword-v1`), not a model, and says so. LLM-extracted fields (M4) will live
  in a separate table with model + date, never merged with source truth. A
  mouse result is never presented as a human result.
- **Attribution.** PubMed abstracts are publisher-copyrighted and redistributed
  under NCBI's terms with link-back; ClinicalTrials.gov data is US-government
  public domain. Every item page credits and links its source.
- **Free tier.** Vercel (site) + Neon (Postgres) + GitHub Actions (daily cron);
  the pieces are coupled only by the connection string.

## Layout

```
pipeline/        Python — fetch, landing zone, relevance gate, Postgres store
  dontdie/         the package
    sources/         pubmed.py, ctgov.py (one adapter per source)
    landing.py       raw JSON landing zone (the dedupe mechanism)
    relevance.py     deterministic keyword-v1 gate
    store.py         migrations + idempotent Postgres upserts
    queries.py       domain queries from the plan's domain map
    cli.py           migrate / fetch / load / run
  migrations/      SQL migrations — the pipeline owns the schema
  tests/           offline fixture tests + store round-trip tests
site/            Next.js/TypeScript — the public knowledge base
  app/             routes: /, /domains/[slug], /items/[slug], /search
  lib/             read-only Postgres access, domain map, types
.github/workflows/daily-fetch.yml   daily cron (needs DATABASE_URL secret)
docs/PLAN.md     the plan and decision log
```

## Running the pipeline

Requires Python 3.9+ and any Postgres (no keys).

```sh
cd pipeline
export DATABASE_URL="postgresql://localhost/dontdie"

python3 -m dontdie migrate     # apply migrations
python3 -m dontdie fetch       # all sources → raw JSON landing zone
python3 -m dontdie load        # landing zone → Postgres, relevance-tagged
python3 -m dontdie run         # fetch + load — what the cron runs

# finer control:
python3 -m dontdie fetch --source pubmed --days 7 --limit 50
```

- The landing zone lives in `pipeline/state/` (gitignored), with a
  `fetch_log.jsonl` of every run.
- Items that fail the relevance gate stay in the corpus (auditable) but are
  kept out of public views.
- NCBI E-utilities run unauthenticated at 3 req/s; set `NCBI_API_KEY` for
  10 req/s (opt-in only).

Tests:

```sh
cd pipeline && python3 -m pytest
```

Offline tests always run; store round-trip tests need `DATABASE_URL` and skip
without it.

## Running the site

Requires Node 20+.

```sh
cd site
npm install
export DATABASE_URL="postgresql://localhost/dontdie"  # read-only role in production
npm run dev    # http://localhost:3000
```

| Route | What it shows |
|---|---|
| `/` | The domain map, search box, recently gathered items |
| `/domains/[slug]` | Relevant items in one domain (senolytics, biomarkers, …) |
| `/items/[slug]` | One item: metadata, abstract/summary, attribution, gate disclosure |
| `/search?q=…` | Corpus search over titles and abstracts |

Without `DATABASE_URL` the site builds and runs with an honest
"store not connected" state rather than a guess.

## Deploying (free tier)

1. **Postgres** — create a free database on Neon; that URL is the
   read-write `DATABASE_URL` for the pipeline. For the site, create a
   read-only role and use that URL in Vercel's env
   (`GRANT SELECT ON ALL TABLES …`).
2. **Site** — import the repo into Vercel, root directory `site/`, set
   `DATABASE_URL`, deploy.
3. **Daily pipeline** — set the repo secret `DATABASE_URL`; the
   `daily-fetch` workflow then runs `migrate` + `fetch` + `load` daily at
   ~06:10 UTC. Without the secret it skips itself cleanly.

## Attribution & licensing

PubMed abstracts are publisher-copyrighted, redistributed under NCBI's terms
with attribution and link-back. ClinicalTrials.gov data is US-government
public domain. LLM-generated summaries, when they arrive (M4), will be visibly
labeled as generated. Never mirrored: paywalled full text.
