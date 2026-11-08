# don't die

A public knowledge base for life-extension / longevity medical science. A
Python pipeline gathers from free public sources — PubMed and
ClinicalTrials.gov today, preprints and more later — normalizes, dedupes, and
relevance-tags the items; a Next.js site publishes the corpus as a browsable
knowledge base with per-domain pages, item pages with attribution, and
(publishing from M2) a weekly digest.

The plan and full decision log live in [`docs/PLAN.md`](docs/PLAN.md). All six
founding decisions are closed there: public site, knowledge-base homepage with
digest landing, monorepo Python + Next.js over one Postgres, fetch daily /
publish weekly, LLM extraction on all relevant items (Haiku-class, labeled,
never merged with source truth), and free-tier hosting (Vercel + Neon +
GitHub Actions).

## Layout

```
pipeline/        Python — fetch, landing zone, relevance gate, Postgres store
  dontdie/         the package (sources/, landing.py, relevance.py, store.py, cli.py)
  migrations/      SQL migrations; the pipeline owns the schema
  tests/           offline fixture tests + store round-trip tests
site/            Next.js/TypeScript — the public knowledge base (read-only DB role)
.github/workflows/daily-fetch.yml   the daily cron (needs DATABASE_URL secret)
```

## Pipeline

No API keys are required. NCBI E-utilities run unauthenticated at 3 req/s
(set `NCBI_API_KEY` for 10 req/s; opt-in only).

```sh
cd pipeline

export DATABASE_URL="postgresql://localhost/dontdie"   # any Postgres

python3 -m dontdie migrate          # apply migrations (0001 schema, 0002 relevance)
python3 -m dontdie fetch             # all sources → raw JSON landing zone
python3 -m dontdie load              # landing zone → Postgres, relevance-tagged
python3 -m dontdie run               # fetch + load — what the cron runs
python3 -m dontdie fetch --source pubmed --days 7 --limit 50
```

- **Landing zone** (`pipeline/state/landing/`, gitignored): one JSON file per
  source item keyed by its stable id (PMID, NCT id). Re-fetching overwrites
  the same path — the landing zone **is** the dedupe mechanism, and every item
  is re-derivable and auditable.
- **Relevance gate** (`relevance.py`): a deterministic keyword filter
  (`keyword-v1`), labeled by method — not a model, and never presented as one.
  Excluded items stay in the corpus for auditability but are out of public
  views.
- **Extraction honesty**: LLM-extracted fields (from M4) will live in a
  separate table with model + date, never merged with source-truth fields.

Tests: `cd pipeline && python3 -m pytest` (offline tests always run; store
round-trip tests need `DATABASE_URL` and skip without it).

## Site

```sh
cd site
npm install
export DATABASE_URL="postgresql://localhost/dontdie"  # read-only role in production
npm run dev    # http://localhost:3000
```

Routes: `/` the domain map + recently gathered, `/domains/[slug]` per-domain
browse, `/items/[slug]` item pages with source attribution and link-back,
`/search?q=…` corpus search. Without `DATABASE_URL` the site builds and runs
with an honest "store not connected" state rather than a guess.

## Deploy (free tier)

1. **Postgres**: create a free database on Neon; export its URL as
   `DATABASE_URL`. For the site, create a read-only role and use that URL in
   Vercel's env (`GRANT SELECT ON ALL TABLES …`).
2. **Site**: import the repo into Vercel, set root directory to `site/`, set
   `DATABASE_URL`, deploy.
3. **Daily pipeline**: set the repo secret `DATABASE_URL` (read-write) —
   `daily-fetch.yml` then runs `migrate` + `fetch` + `load` daily at ~06:10
   UTC. Without the secret the workflow skips itself.

## Attribution

PubMed abstracts are publisher-copyrighted, redistributed under NCBI's terms
with attribution and link-back; ClinicalTrials.gov data is US-government
public domain. LLM-generated summaries, when they arrive, are visibly labeled
as generated.
