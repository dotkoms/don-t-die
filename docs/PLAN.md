# don-t-die — Research & Data Gathering System for Life Extension Medical Science

Status: planning. Nothing is implemented yet; this doc is the scope of record.

## 1. What this is

A system that continuously gathers, normalizes, and curates *everything* relevant to
life-extension / longevity medicine, so that a human researcher can track the field
without reading fifty sources by hand.

Two halves:

1. **Data gathering** — scheduled ingestion from public scientific sources.
2. **Research** — structured storage, retrieval, extraction, and a curation layer
   that turns raw items into answerable questions ("what changed this week in
   senolytics?", "which trials targeting epigenetic reprogramming are recruiting?").

## 2. Scope of "everything"

The domain map, each of which becomes a tag/classification target:

| Domain | Examples |
|---|---|
| Geroscience fundamentals | Hallmarks of aging, mTOR, autophagy, cellular senescence, mitochondrial function, epigenetic clocks |
| Interventions — pharmacological | Rapamycin, metformin, NAD+ precursors (NR/NMN), senolytics (dasatinib+quercetin, fisetin), GLP-1s, spermidine, TA-65 |
| Interventions — non-pharmacological | Caloric restriction, fasting protocols, exercise science, sleep, heat/cold exposure |
| Rejuvenation biotech | Partial epigenetic reprogramming (OSK/Yamanaka), plasma dilution, thymus regeneration, cross-link breakers, senescent cell clearance |
| Biomarkers | DNAm clocks (Horvath, Hannum, DunedinPACE), GlycanAge, blood panels (albumin, CRP, insulin, lipids), functional biomarkers (grip strength, VO2max) |
| Clinical evidence | ClinicalTrials.gov pipeline, TAME-style trial design, off-label practice, trial endpoints & surrogate debates |
| Industry landscape | Company pipelines & funding (Altos, Calico, Retro, Unity, BioAge), clinic practices, regulatory (FDA, EMA) posture toward aging as indication |
| Longevity media & community | Longevity.Technology, Lifespan.io, Fight Aging!, r/longevity — for signal, always down-ranked vs. primary literature |
| Longevity-adjacent medicine | Cardiometabolic, oncology, neurodegeneration where outcomes track aging biology |

Out of scope for v1: consumer wearables data, personal health records, anything
requiring a paid API key.

## 3. Source landscape (free, public, no keys required — matches the no-keys-first constraint)

Tier 1 — primary, structured, machine-readable:

- **PubMed / NCBI E-utilities** — the spine. Daily new publications by domain query.
- **ClinicalTrials.gov API v2** — trials by condition/intervention keyword.
- **bioRxiv + medRxiv API** — preprints; earliest signal, lowest certainty.
- **OpenAlex** — scholarly metadata graph: citations, authors, institutions; good
  for "who is building on X" queries.
- **Europe PMC** — full text for open-access subset; better search API than PubMed's.
- **Semantic Scholar API** — citation counts, influential citations, S2 papers.
- **NIH RePORTER** — grants (who is getting money to study what).
- **FDA** — drug approvals (drugs@fda), meeting docs.

Tier 2 — derived/community, needs careful provenance:

- RSS: Longevity.Technology, Lifespan.io, Fight Aging!
- Reddit r/longevity (JSON, no key)
- Company press releases (scraped RSS where offered)

Tier 3 — deliberately not built on in v1: Google Scholar (no API, brittle),
Crunchbase (paid), Twitter/X (API paid), paywalled journals beyond abstracts.

Every stored item carries provenance: source, URL, fetch time, license, and a
primary-vs-derived tier flag.

## 4. Architecture (proposed)

```
sources (one adapter per source, pure fetch, no logic)
   → normalizer (papers / trials / news → one item schema)
   → dedupe (DOI, ClinicalTrials.gov NCT id, URL hash)
   → relevance classifier (is this longevity-relevant? domain tags)
   → extractor (compound, outcome, model organism, human vs animal, effect size)
   → store (SQLite to start; Postgres if/when it earns it)
   → surfaces: daily digest, searchable corpus, per-domain feeds, alerts
```

Principles:

- Stateless where possible; every item idempotently re-derivable from its source
  plus a fetch log (mirrors the no-state philosophy that works for volume-scanner).
- Extraction honesty: LLM-extracted fields are labeled as extractions with model +
  date, never merged silently with source-truth fields. A measured effect size in
  mice is never presented as a human result.
- No API keys required for first local run; keyed providers are opt-in only.
- One ranked queue per digest, not per-source alerts — attention is the scarce
  resource, the system exists to save it.

## 5. Candidate surfaces (v1 order of preference)

1. **Daily/weekly digest** — markdown or terminal, ranked by significance:
   new human-trial results > strong animal results > funding/regulatory news >
   preprints > media echo.
2. **Searchable corpus** — keyword + embedding search over normalized items.
3. **Per-domain tracking pages** — "senolytics", "reprogramming", "biomarkers".
4. **Alerts** — only for rare, high-signal events (phase II/III result lands,
   FDA action, major funding round).

## 6. Decisions

**Decided (2026-11-08):**

1. **Primary consumer: PUBLIC.** The system is a browsable public database/site,
   not a private tool. Implications:
   - The corpus-first architecture stands, but a real product surface moves to M1:
     web app, item pages, search, and per-domain browsing are core, not polish.
   - Multi-user read from day one → Postgres (not SQLite) becomes the default
     store; single SQLite file only if we want a dev-mode shortcut.
   - Data modeling gets stricter: normalized items need stable public IDs, slugs,
     and per-source attribution shown on-page, because the pages are the product.
   - Licensing matters once we republish: ClinicalTrials.gov is US-government
     public domain; PubMed abstracts are publisher-copyrighted and redistributed
     under NCBI's terms (attribution + link-back required); preprints vary by
     license (CC-BY on many bioRxiv/medRxiv items). Show abstracts with
     attribution and links; never mirror paywalled full text. LLM-generated
     summaries must be visually labeled as generated, per the honesty principle.
   - Editorial layer: a public site implies a point of view — ranked digests,
     "what changed this week", curated domain pages. The pipeline remains
     primary-source-first; media-tier items stay down-ranked.

**Open (in decision order):**

2. **What the public artifact is** — structured knowledge base (browse
   interventions, trials, papers as linked entities), publication (ranked
   editorial feed of what changed), or tracker (follow specific trials/
   compounds over time). Probably all three eventually; which is the homepage?
3. **Language / runtime** — Python for the pipeline is still the default; the
   public site wants a web stack (Next.js/TypeScript is the default candidate).
   Monorepo with both, or pipeline + site as separate deployables?
4. **Cadence** — daily fetch; digest published daily or weekly?
5. **LLM extraction budget** — which tier items get LLM-extracted fields;
   proposed default: only items that pass the relevance classifier.
6. **Hosting** — static-ish + serverless vs long-running Python worker +
   web app. Free tier first, no paid services without an explicit go.

## 7. Milestones (not yet approved — for discussion)

Revised for a public product:

- M0: source adapters for PubMed + ClinicalTrials.gov, raw JSON landing, dedupe.
- M1: normalized item schema + relevance tagging + Postgres store
  **+ public web app skeleton: item pages, search, per-domain browse**.
- M2: editorial digest v1 ("what changed this week") as a public page.
- M3: extraction pass + provenance/generated labels, shown on-page.
- M4: entity pages (compounds, trials, orgs) linking the corpus together.
- M5: tracking/follow features for visitors.
