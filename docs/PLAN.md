# don-t-die — Research & Data Gathering System for Life Extension Medical Science

Status: M0–M2 built (pipeline, site, news + peptides + research agents); this
doc is the scope of record.

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
| Peptide interventions | BPC-157, epitalon, MOTS-c, humanin, GHK-Cu, elamipretide (SS-31), tesamorelin, ipamorelin, CJC-1295, GLP-1 agonists — "all peptides" as a first-class domain |
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

- RSS (built, keyless): Longevity.Technology, Lifespan.io, Fight Aging!,
  ScienceDaily (health/medicine), Medical Xpress
- Reddit r/longevity (JSON, no key) — later
- Company press releases (scraped RSS where offered) — later

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

**Decided (2026-11-08):**

2. **Public artifact: knowledge base, with the digest as the landing section.**
   The front door is browsable structure — the domain map (senolytics,
   reprogramming, biomarkers, …), into entity pages (compounds, trials, orgs)
   collecting everything the pipeline has attached to them. The weekly digest is
   the landing page's top section ("what changed this week"), not the site's
   identity. Feed items link into entity pages, so nothing valuable ages off the
   front page. Entity pages therefore move earlier: they are the destination the
   digest points at.
3. **Stack: monorepo, two runtimes.** `pipeline/` is Python (fetchers, dedupe,
   relevance tagging, LLM extraction); `site/` is Next.js/TypeScript (browse,
   search, item/entity/digest pages). One Postgres shared by both; the site
   connects with a read-only role and never imports pipeline code. Schema
   ownership: migrations live with the Python pipeline; TS types mirror them.
   Rationale: Python matches the pipeline's grain (NCBI/OpenAlex wrangling,
   pandas backfill, no build step); Next.js gives SSR/SEO, which a public
   knowledge base lives or dies on, plus a free-tier host.
4. **Cadence: fetch daily, publish weekly.** The pipeline runs daily (keeps the
   corpus and entity pages fresh; high-signal events never sit in a queue).
   The digest publishes weekly as a real editorial unit — one substantial,
   linkable page per issue; daily longevity output is too thin to sustain a
   daily promise. The landing page always shows the latest issue. A "recent
   items" river between issues is a possible later UI addition, not a cadence
   items river between issues is a possible later UI addition, not a cadence
   change.
5. **LLM extraction budget: every item that passes the relevance classifier,
   extracted once, idempotently.** Rationale: the knowledge base's promise is
   structured evidence on entity pages, so extraction can't be limited to
   digest-ranked items without degrading the long tail. Model: Claude Haiku 4.5
   (`claude-haiku-4-5`) for bulk per-item extraction (~$10/month at a few dozen
   relevant items/day); editorial digest drafting is a later, small-volume
   decision where a stronger model can justify itself. The initial corpus
   backfill (~5–10K papers, one-time) runs through the Batch API (async, 50%
   cost) — a one-time ~$25–50. Standing rule: **no paid run happens without an
   explicit, job-specific go** — the backfill included. Extraction is LLM-labeled
   (model + date) per the honesty principle, never merged with source-truth
   fields.
6. **Hosting: managed-free split — Vercel + Neon + GitHub Actions.** Vercel
   hobby tier hosts the Next.js site (SSR/SEO, TLS, no servers). Neon free tier
   hosts Postgres (0.5 GB is years of headroom for metadata + abstracts; free
   compute auto-suspends when idle — a cold-start second, acceptable). GitHub
   Actions scheduled workflow runs the daily pipeline (cron delay up to
   ~15–30 min is irrelevant at daily cadence; minutes budget comfortable).
   Zero cost; pieces coupled only by the connection string, each swappable
   independently. No paid service without an explicit go, as ever.

7. **Multi-agent research system — "conventional but verifiable."** The
   pipeline now has an on-demand research layer (`python3 -m dontdie research
   <target>`) that answers questions beyond what scheduled ingestion catches.
   Design: four steps, only two of which cost money.
   - **News scout** — Claude with server-side web search restricted
     (`allowed_domains`) to a named allowlist of conventional outlets
     (Reuters, AP, STAT News, Longevity.Technology, Lifespan.io, Fight
     Aging!, ScienceDaily, Medical Xpress, New Scientist, EurekAlert, and
     peers). It can only cite from that surface.
   - **Primary scout** — free, deterministic, no LLM: PubMed esearch for
     recent publications matching the target.
   - **Verifier** — deterministic code, not a model: every URL the scouts
     produce is checked against a machine-readable allowlist (`NEWS_OUTLETS`,
     `PRIMARY_HOSTS`) and rejected otherwise; refused URLs are reported, not
     silently dropped.
   - **Synthesizer** — Claude writes a markdown brief citing only the
     verified sources, distinguishing human vs. animal evidence.
   Verifiability is operationalized as an allowlist, so "is this source
   trustworthy" is answered by code, not by a model's judgment. Results
   land in `research_notes` with the generating model recorded — an
   LLM-generated artifact, labeled as such per the honesty principle.
   Paid runs obey the standing rule doubly: the command **dry-runs by
   default and refuses to spend without an explicit `--go` flag**, even when
   `ANTHROPIC_API_KEY` is set. No key is required for anything else in the
   system.

**Decided (2026-11-08):**

8. **Tier-2 news ingestion + peptides as a first-class domain.** Two
   expansions of the ingestion surface, both keyless:
   - **News outlets via RSS** (Longevity.Technology, Lifespan.io, Fight
     Aging!, ScienceDaily, Medical Xpress): fetched, deduped by canonical
     URL, gated by the same relevance classifier, stored with
     `tier = 2`. News items are never presented as primary sources — item
     pages say "news coverage (tier 2)" and "check the primary source,"
     and only a short summary is stored, never the article body.
   - **Peptides**: a new `peptides` query domain (BPC-157, epitalon,
     MOTS-c, humanin, GHK-Cu, elamipretide/SS-31, tesamorelin, ipamorelin,
     CJC-1295, GLP-1 agonists) in PubMed, ClinicalTrials.gov, and the
     relevance gate. The gate moved to `keyword-v1.1`: Unicode hyphen
     normalization (PubMed abstracts contain U+2011), word-boundary
     matching, and peptide names added as strong terms so mainstream news
     mentioning them can't be excluded by materials hints.

All eight decisions closed (2026-11-08).

## 7. Milestones

Revised for a public product:

- **M0 — done, merged to main.** Source adapters for PubMed +
  ClinicalTrials.gov, raw JSON landing, dedupe.
- **M1 — done, merged to main.** Normalized item schema + relevance tagging
  + Postgres store **+ public web app skeleton: item pages, search,
  per-domain browse**.
- **M2 — done (this branch).** Tier-2 news outlets via RSS (5 feeds,
  keyless), the peptides domain, relevance gate v1.1, and the multi-agent
  research layer (decisions 7–8).
- M3: editorial digest v1 ("what changed this week") as the landing page's top
  section + domain-map browse.
- M4: entity pages (compounds, trials, orgs) — moved up: the digest's links
  need a destination.
- M5: extraction pass + provenance/generated labels, shown on-page.
- M6: tracking/follow features for visitors.
