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

## 6. Open decisions

1. **Primary consumer** — personal research tool for you, public database, or
   feedstock for another project (yc-app / Vista wedge content)? Changes how much
   polish the surfaces need.
2. **Language / runtime** — Python (fits the research-tool world, PubMed/analysis
   libs) is the default; say if you want TypeScript to match other repos.
3. **Cadence** — daily fetch + weekly digest, or everything real-time-ish?
4. **LLM extraction budget** — which tier items get LLM-extracted fields (cost
   scales with corpus size); proposed default: only items that pass the relevance
   classifier.
5. **Storage** — SQLite single-file to start (backs the no-keys, runs-anywhere
   default), Postgres later if multi-user.

## 7. Milestones (not yet approved — for discussion)

- M0: source adapters for PubMed + ClinicalTrials.gov, raw JSON landing, dedupe.
- M1: normalized item schema + relevance tagging + SQLite store.
- M2: terminal digest v1 (ranked markdown).
- M3: extraction pass + provenance labels.
- M4: search + per-domain pages.
