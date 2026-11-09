# don't die

**A public knowledge base for life-extension medical science.**

A pipeline gathers the field's evidence from free public sources — PubMed,
ClinicalTrials.gov, Europe PMC preprints and non-Medline open access, the
ISRCTN and EU CTIS trial registries, the DrugAge lifespan-assay dataset, plus
tier-2 news coverage from verifiable outlets — normalizes, dedupes, and
relevance-tags every item. A website publishes the
result: a browsable domain map into entity pages, item pages with full source
attribution, corpus search, and (publishing from M3) a weekly digest of what
actually changed. An on-demand multi-agent research layer (opt-in, see below)
answers questions the scheduled ingestion misses.

The full plan and decision log live in [`docs/PLAN.md`](docs/PLAN.md).

## Roadmap

| Milestone | Scope | Status |
|---|---|---|
| M0 | Source adapters (PubMed, ClinicalTrials.gov), raw JSON landing zone, dedupe | **Done** |
| M1 | Postgres store, relevance gate, web app skeleton (domain map, item pages, search) | **Done** |
| M2 | News outlets (tier 2), peptides domain, gate v1.2, multi-agent research layer, coverage expansion (Europe PMC, DrugAge, ISRCTN, EU CTIS) | **Done** |
| M3 | Weekly digest as the landing page's top section | Planned |
| M4 | Entity pages (compounds, trials, orgs) — the digest's destinations | Planned |
| M5 | LLM extraction pass with labeled, provenance-safe fields | Planned |
| M6 | Tracking / follow features for visitors | Planned |

## Corpus at a glance

Numbers from the last pipeline run (2026-11-08); they grow with every fetch.
Everything below is live query output from the store, not an estimate.

**6,155 items ingested, 4,564 passing the relevance gate (74%).** Every item
is kept for auditability; only gate-passing items appear in public views.

By source:

| Source | Tier | Relevant | Total |
|---|---|---|---|
| DrugAge lifespan assays | 2 | 3,416 | 3,416 |
| Europe PMC (preprints + non-Medline OA) | 1 | 620 | 1,867 |
| PubMed | 1 | 252 | 327 |
| ClinicalTrials.gov | 1 | 145 | 259 |
| EU Clinical Trials Information System | 1 | 67 | 83 |
| ISRCTN Registry | 1 | 33 | 73 |
| News outlets (5 feeds, combined) | 2 | 31 | 130 |

By domain (an item can carry more than one):

| Domain | Relevant items |
|---|---|
| Lifespan experiments (DrugAge) | 3,416 |
| Geroscience | 232 |
| Longevity | 216 |
| Peptides | 208 |
| Senolytics | 131 |
| Pharmacological interventions | 123 |
| Biomarkers | 74 |
| Clinical evidence | 61 |
| Rejuvenation | 49 |
| Diet & restriction | 23 |

What the corpus contains:

- **722 preprints** (bioRxiv/medRxiv and peers) — earliest signal, each
  flagged "not peer reviewed" on its item page; the other 1,145 Europe PMC
  items are non-Medline open-access articles.
- **3,416 curated lifespan experiments** from DrugAge: 1,046 distinct
  compounds across 38 species, citing 664 underlying PubMed studies; 164 rows
  come from the Interventional Testing Program.
- **245 relevant trial records** across ClinicalTrials.gov, ISRCTN, and EU
  CTIS — 102 currently recruiting and 47 about to start.
- **Coverage windows:** PubMed accumulates since the first run (back to
  2026-01-01); Europe PMC fetches a trailing 30-day window; DrugAge re-lands
  its full snapshot every run; the registries refresh trials updated in the
  window.
- **Relevance gate:** `keyword-v1.2` — 61 aging/peptide term patterns, 15
  materials false-positive hints, 47 strong terms that override the hints.
  The 1,591 excluded items are kept in the store and reachable by slug, just
  not listed publicly.

## Principles

- **No API keys for a first run.** Everything needed to fetch and browse works
  with zero credentials; keyed providers are opt-in only.
- **The landing zone is the dedupe.** One JSON file per source item, keyed by
  its stable id (PMID, NCT id) — a re-fetch overwrites the same path instead of
  duplicating.
- **Honest labeling.** Relevance is a transparent keyword gate
  (`keyword-v1.2`), not a model, and says so. LLM-generated research notes
  record their generating model; LLM-extracted fields (M5) will live in a
  separate table with model + date, never merged with source truth. A
  mouse result is never presented as a human result, and a preprint is
  flagged as not peer reviewed.
- **News is tier 2, never primary.** Conventional outlets are ingested via
  RSS with provenance flags; item pages mark them "news coverage (tier 2)"
  and point at the primary source. DrugAge is tier 2 the same way: a curated
  dataset whose every row cites its PubMed study.
- **Attribution.** PubMed abstracts are publisher-copyrighted and redistributed
  under NCBI's terms with link-back; ClinicalTrials.gov data is US-government
  public domain; DrugAge data is reused under CC BY 3.0. Every item page
  credits and links its source.
- **Free tier.** Vercel (site) + Neon (Postgres) + GitHub Actions (daily cron);
  the pieces are coupled only by the connection string.

## Layout

```
pipeline/        Python — fetch, landing zone, relevance gate, Postgres store
  dontdie/         the package
    sources/         pubmed.py, ctgov.py, rss.py, europemc.py, drugage.py,
                     isrctn.py, ctis.py (one adapter per source)
    agents/          outlets.py (allowlists), research.py (research agents)
    landing.py       raw JSON landing zone (the dedupe mechanism)
    relevance.py     deterministic keyword-v1.2 gate
    store.py         migrations + idempotent Postgres upserts
    queries.py       domain queries from the plan's domain map
    cli.py           migrate / fetch / load / run / research
  migrations/      SQL migrations — the pipeline owns the schema
  tests/           offline fixture tests + store round-trip tests
site/            Next.js/TypeScript — the public knowledge base
  app/             routes: /, /domains/[slug], /items/[slug], /search
  lib/             read-only Postgres access, domain map, source labels, types
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
python3 -m dontdie fetch --source longevitytech   # any news feed slug
```

Sources: `pubmed`, `ctgov`, `europemc`, `isrctn`, `ctis`, `drugage`, plus the
news feeds `longevitytech`, `lifespanio`, `fightaging`, `sciencedaily`,
`medicalxpress`.

- Europe PMC fetches preprints (bioRxiv/medRxiv and peers) and non-Medline
  open-access articles — never Medline records, which are PubMed's job.
  Preprints are flagged "not peer reviewed" on the item page.
- DrugAge re-lands its full 3,400-assay snapshot each run (idempotent);
  `--days`/`--limit` do not apply to it.
- The registries fetch trials updated in the window (ISRCTN via its XML API,
  EU CTIS via its public JSON API); WHO ICTRP itself is skipped on licensing.

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

## Research agents (opt-in)

`python3 -m dontdie research <target>` runs a multi-agent pass on a topic the
scheduled ingestion hasn't answered — e.g. `"BPC-157"` or `"reprogramming
trials 2026"`:

1. **News scout** — Claude with server-side web search, restricted to an
   allowlist of conventional outlets (Reuters, AP, STAT News,
   Longevity.Technology, Lifespan.io, Fight Aging!, ScienceDaily, Medical
   Xpress, New Scientist, and peers).
2. **Primary scout** — free, deterministic PubMed esearch for recent
   publications on the target (no LLM).
3. **Verifier** — deterministic code checks every candidate URL against the
   outlet/primary-host allowlist; anything off-list is refused and reported.
4. **Synthesizer** — Claude writes a markdown brief citing only verified
   sources, distinguishing human vs. animal evidence.

Cost and consent:

- **Dry run by default.** The command prints the plan and a cost estimate
  and spends nothing. `--go` is required to actually run the LLM steps —
  an explicit, per-job approval, never implied.
- Requires `ANTHROPIC_API_KEY` (opt-in only; nothing else in this repo needs
  a key). Model via `--model` or `DD_RESEARCH_MODEL`; a run is typically
  well under $1.
- Results are saved to `research_notes` with the generating model recorded —
  an LLM artifact, labeled as such.

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
| `/search?q=…` | Corpus search over titles and abstracts/summaries |

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
public domain. ISRCTN and EU CTIS registry records are public data, linked to
their registries. DrugAge data (Human Ageing Genomic Resources) is reused
under CC BY 3.0 with link-back. News items are tier-2 coverage: only a short
summary is stored, the article stays with its publisher, and item pages point
at the primary source. Preprints are shown with a "not peer reviewed" flag.
LLM-generated research notes record their model, and LLM extraction
(M5) will be visibly labeled as generated. Never mirrored: paywalled full
text.
