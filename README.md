# don't die

**A public knowledge base for life-extension medical science.**

A pipeline gathers the field's evidence from free public sources — PubMed,
ClinicalTrials.gov, Europe PMC preprints and non-Medline open access, the
ISRCTN and EU CTIS trial registries, the DrugAge lifespan-assay dataset, the
GenAge / CellAge / AnAge curated gene and longevity datasets, the NIH
RePORTER, EU CORDIS and UKRI GtR grant databases (who is funded to study
what, and how much), plus tier-2 news coverage from verifiable outlets (trade
press and university/institute research news included) — normalizes,
dedupes, and relevance-tags every item, then runs a Retraction Watch
integrity pass that flags anything the journals have withdrawn. A website
publishes the result: a browsable domain map into entity pages, item pages
with full source attribution, corpus search, and (publishing from M3) a
weekly digest of what actually changed. An on-demand multi-agent research
layer (opt-in, see below) answers questions the scheduled ingestion misses.

The full plan and decision log live in [`docs/PLAN.md`](docs/PLAN.md).

## Roadmap

| Milestone | Scope | Status |
|---|---|---|
| M0 | Source adapters (PubMed, ClinicalTrials.gov), raw JSON landing zone, dedupe | **Done** |
| M1 | Postgres store, relevance gate, web app skeleton (domain map, item pages, search) | **Done** |
| M2 | News outlets (tier 2), peptides domain, gate v1.2, multi-agent research layer, coverage expansion (Europe PMC, DrugAge, ISRCTN, EU CTIS), funding + institution sources (NIH RePORTER, EU CORDIS, trade press + university feeds), free-source sweep (UKRI GtR, Retraction Watch integrity pass, GenAge + CellAge + AnAge) | **Done** |
| M3 | Weekly digest as the landing page's top section | Planned |
| M4 | Entity pages (compounds, trials, orgs) — the digest's destinations | Planned |
| M5 | LLM extraction pass with labeled, provenance-safe fields | Planned |
| M6 | Tracking / follow features for visitors | Planned |

## Corpus at a glance

Numbers from the last pipeline run (2026-11-09); they grow with every fetch.
Everything below is live query output from the store, not an estimate.

**26,418 items ingested, 18,624 passing the relevance gate (70%).** Every
item is kept for auditability; only gate-passing items appear in public
views.

By source:

| Source | Tier | Relevant | Total |
|---|---|---|---|
| NIH RePORTER (US grants) | 1 | 5,605 | 8,271 |
| AnAge species longevity records | 2 | 4,141 | 4,141 |
| DrugAge lifespan assays | 2 | 3,416 | 3,416 |
| GenAge aging genes (human + models) | 2 | 1,951 | 2,508 |
| EU CORDIS (European grants) | 1 | 1,496 | 4,405 |
| CellAge senescence genes | 2 | 866 | 866 |
| Europe PMC (preprints + non-Medline OA) | 1 | 620 | 1,867 |
| PubMed | 1 | 252 | 327 |
| ClinicalTrials.gov | 1 | 145 | 259 |
| EU Clinical Trials Information System | 1 | 67 | 83 |
| ISRCTN Registry | 1 | 33 | 73 |
| News outlets (13 feeds, combined) | 2 | 32 | 202 |

UKRI Gateway to Research (decision 11) ships in this release; its first
full backfill fetches every unique matched project in detail, so those
items land with the next load after it completes.

By domain (an item can carry more than one):

| Domain | Relevant items |
|---|---|
| Lifespan experiments (DrugAge + AnAge) | 7,557 |
| Longevity | 2,538 |
| Longevity genetics (GenAge + CellAge) | 2,817 |
| Geroscience | 1,753 |
| Peptides | 1,098 |
| Senolytics | 931 |
| Pharmacological interventions | 759 |
| Rejuvenation | 535 |
| Biomarkers | 520 |
| Clinical evidence | 61 |
| Diet & restriction | 23 |

What the corpus contains:

- **7,101 relevant grant records** answering "who is funded to study what":
  5,605 NIH project-years (FY 2026–27, ~$3.6B in obligations) across 544
  institutions and every NIH institute that funds aging science; 1,496 EU
  projects from CORDIS — 676 signed and ongoing, 746 closed, 74 terminated.
  Each renders as a funding record (agency, amount, institution, PI, period).
- **722 preprints** (bioRxiv/medRxiv and peers) — earliest signal, each
  flagged "not peer reviewed" on its item page; the other 1,145 Europe PMC
  items are non-Medline open-access articles.
- **3,416 curated lifespan experiments** from DrugAge: 1,046 distinct
  compounds across 38 species, citing 664 underlying PubMed studies; 164 rows
  come from the Interventional Testing Program.
- **The rest of the HAGR family** (all CC BY 3.0, curated, tier 2): 307
  GenAge human aging genes with their evidence classes; 2,194 model-organism
  longevity genes across 9 organisms (557 rows whose own annotation claims
  no longevity effect stay in the corpus, auditable but unlisted); 866
  CellAge genes that induce or inhibit cellular senescence, each citing its
  PubMed study; and 4,141 AnAge species records with measured maximum
  longevity — from a 1.1-year parasitic worm to the 15,000-year glass sponge
  the dataset itself records.
- **A Retraction Watch integrity pass** runs after every load: the CC0
  Crossref database (~73k retractions, expressions of concern and
  reinstatements, updated every working day) is matched against the corpus
  by DOI and PMID, and any hit is flagged on its item page with the nature,
  reason, date and a link to the notice. Flags fully recompute each run, so
  a reinstatement un-flags.
- **245 relevant trial records** across ClinicalTrials.gov, ISRCTN, and EU
  CTIS — 102 currently recruiting and 47 about to start.
- **Coverage windows:** PubMed accumulates since the first run (back to
  2026-01-01); Europe PMC fetches a trailing 30-day window; the registries
  refresh trials updated in the window. DrugAge re-lands its full snapshot
  every run; NIH RePORTER re-lands the current + previous fiscal year (its
  API has no date-added filter — verified); EU CORDIS re-lands its matched
  projects the same way. Landing is idempotent, so a re-fetch overwrites
  instead of duplicating.
- **Relevance gate:** `keyword-v1.2` — 61 aging/peptide term patterns, 15
  materials false-positive hints, 47 strong terms that override the hints.
  The 7,794 excluded items are kept in the store and reachable by slug, just
  not listed publicly. Known precision cost: ~1% of relevant items match only
  the demographic word "aged" (trial-eligibility language like "subjects aged
  18–65"), recorded in the plan as a possible gate v1.3 refinement.

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
                     genage.py, cellage.py, anage.py, isrctn.py, ctis.py,
                     reporter.py, cordis.py, gtr.py (one adapter per source)
    agents/          outlets.py (allowlists), research.py (research agents)
    landing.py       raw JSON landing zone (the dedupe mechanism)
    relevance.py     deterministic keyword-v1.2 gate
    integrity.py     Retraction Watch pass: retraction flags, not a source
    store.py         migrations + idempotent Postgres upserts
    queries.py       domain queries from the plan's domain map
    cli.py           migrate / fetch / load / integrity / run / research
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
python3 -m dontdie integrity   # Retraction Watch pass: flag retracted items
python3 -m dontdie run         # fetch + load + integrity — what the cron runs

# finer control:
python3 -m dontdie fetch --source pubmed --days 7 --limit 50
python3 -m dontdie fetch --source gtr --limit 2000
python3 -m dontdie fetch --source longevitytech   # any news feed slug
```

Sources: `pubmed`, `ctgov`, `europemc`, `isrctn`, `ctis`, `drugage`,
`genage`, `cellage`, `anage` (HAGR datasets), `reporter` (NIH grants),
`cordis` (EU grants), `gtr` (UK grants), plus the news feeds
`longevitytech`, `lifespanio`, `fightaging`, `sciencedaily`, `medicalxpress`,
`gen` (GEN), `endpts` (Endpoints News), `stat` (STAT News), `mitbio` / `mitmed`
(MIT News), `harvardgazette`, `salk`, `babraham`.

- Europe PMC fetches preprints (bioRxiv/medRxiv and peers) and non-Medline
  open-access articles — never Medline records, which are PubMed's job.
  Preprints are flagged "not peer reviewed" on the item page.
- DrugAge re-lands its full 3,400-assay snapshot each run (idempotent);
  `--days`/`--limit` do not apply to it.
- The registries fetch trials updated in the window (ISRCTN via its XML API,
  EU CTIS via its public JSON API); WHO ICTRP itself is skipped on licensing.
- NIH RePORTER lands up to `--limit` project-years per domain query for the
  current + previous fiscal year (the API exposes no date-added filter);
  EU CORDIS and UKRI GtR re-land their matched projects the same way (GtR
  searches one term per request — `--limit` applies per term, so a full
  first backfill takes a while: it fetches each unique project in detail).
  All are idempotent re-lands over the landing zone.
- The Retraction Watch pass downloads the CC0 database CSV (Crossref,
  ~70 MB) fresh each run and recomputes every item's flags — a paper can be
  retracted years after it landed.
- GenAge, CellAge and AnAge re-land their full snapshots each run, like
  DrugAge; `--days`/`--limit` do not apply to them.

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
with attribution and link-back. ClinicalTrials.gov and NIH RePORTER data are
US-government public domain. ISRCTN and EU CTIS registry records are public
data, linked to their registries. EU CORDIS project data is reused under
CC BY 4.0 with link-back. UKRI GtR project data is public data, linked back
to the Gateway to Research. DrugAge, GenAge, CellAge and AnAge data (Human
Ageing Genomic Resources) are reused under CC BY 3.0 with link-back. The
Retraction Watch Database is CC0 (Crossref). News items are tier-2 coverage:
only a short summary is stored, the article stays with its publisher, and
item pages point at the primary source. Preprints are shown with a "not peer
reviewed" flag. LLM-generated research notes record their model, and LLM
extraction (M5) will be visibly labeled as generated. Never mirrored:
paywalled full text.
