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

- **PubMed / NCBI E-utilities** — the spine. Daily new publications by domain query. (built)
- **ClinicalTrials.gov API v2** — trials by condition/intervention keyword. (built)
- **Europe PMC** (built, keyless) — `SRC:PPR` preprints (bioRxiv/medRxiv and
  peers) plus non-Medline open-access articles; Medline stays PubMed's job so
  nothing is double-counted.
- **ISRCTN Registry** (built, keyless XML API) + **EU Clinical Trials
  Information System / CTIS** (built, keyless JSON API) — registry coverage
  beyond the US. WHO ICTRP itself rejected on licensing (decision 9).
- **NIH RePORTER** (built, keyless v2 API) — US grants: agency, amount,
  institution, PI, abstract per project-year. The old
  api.reporter.research.gov host is DNS-dead; the canonical host is
  api.reporter.nih.gov. No date-added filter exists (verified — the criteria
  are silently ignored), so the adapter re-lands the current + previous
  fiscal year per query each run.
- **EU CORDIS** (built, keyless) — EU research projects (objective, cost, EC
  contribution, status); data reused under CC BY 4.0. The legacy REST API
  retired in 2026; the live surface is the portal's own JSON search
  (`/search/en?format=json&q=…`), queried inside `/project/objective` and
  re-landed full-snapshot like DrugAge.
- **OpenAlex** — scholarly metadata graph: citations, authors, institutions; good
  for "who is building on X" queries.
- **Semantic Scholar API** — citation counts, influential citations, S2 papers.
- **FDA** — drug approvals (drugs@fda), meeting docs.

Tier 2 — derived/community, needs careful provenance:

- RSS (built, keyless): Longevity.Technology, Lifespan.io, Fight Aging!,
  ScienceDaily (health/medicine), Medical Xpress — plus the decision-10
  expansion: GEN, Endpoints News, STAT News (trade press) and MIT News
  (biology/medicine), Harvard Gazette, Salk Institute, Babraham Institute
  (university/institute research news). Cross-feed canonical-URL dedupe;
  Endpoints News is the single browser-UA exception (its WAF 403s every
  honest identifying UA). Salk and Babraham feeds are dormant (latest posts
  2020 / Oct 2025) but live and cheap to poll.
- **DrugAge** (built, keyless) — curated lifespan-assay dataset, CC BY 3.0,
  `lifespan-data` domain; every row cites its PubMed study. Geroprotectors
  would join it here if its site returns.
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

**Decided (2026-11-08):**

9. **Coverage expansion: preprints, non-Medline OA, curated lifespan data,
   and non-US registries.** A live coverage audit (per-peptide PubMed counts,
   CT.gov trial counts) found three gap classes; four workstreams close them,
   all keyless:
   - **Peptide widening** — the peptide list grew from 12 compounds to the
     full set circulating in the longevity space (thymosin β4/TB-500,
     thymosin α1, GHRP-2/-6/hexarelin, SHLP small humanin-like peptides,
     AOD-9604, selank, semax, dihexa, noopept, carnosine, retatrutide,
     orforglipron, klotho-derived). The list lives in one shared constant
     (`PEPTIDE_TERMS`) consumed by every source query; the gate moved to
     `keyword-v1.2` with the new compounds as strong terms.
   - **Europe PMC** (`SRC:PPR` preprints + `SRC:PMC AND NOT PMID:*`
     non-Medline open access) — bioRxiv/medRxiv preprints are the earliest
     signal and PubMed never covers them; non-Medline PMC articles cover
     journals Medline skips. Medline records stay PubMed's job (fetching
     them here would double-count). Preprints are visually flagged "not
     peer reviewed" on the item page. Tier 1.
   - **DrugAge** (Human Ageing Genomic Resources, CC BY 3.0) — 3,423
     curated lifespan assays, one item per experiment, each linking its
     PubMed study. A new `lifespan-data` domain. Tier 2: it is a curated
     secondary dataset, like news — every row cites its primary source.
   - **Registries beyond CT.gov** — ISRCTN (keyless XML API; search for
     windowing + WHO-format per-trial detail) and EU CTIS (keyless JSON
     API). WHO ICTRP itself was evaluated and **rejected on licensing**:
     its web service requires registration and fees and its terms forbid
     copying/republishing — incompatible with a public knowledge base. The
     member registries carry the same trials with genuinely open terms.
     Tier 1. Geroprotectors.org was unreachable during the audit — DrugAge
     alone ships; Geroprotectors is a possible later addition if it returns.
     jRCT/ChiCTR/UMIN/CTRI lack keyless APIs — future additions at most.

All nine decisions closed (2026-11-08).

**Decided (2026-11-09):**

10. **Funding and institution sources.** The corpus answered "what is being
   studied" but not "who is paying for it" and "who is doing it." A live
   keyless-API audit (Nov 8–9) picked two grant registries and eight feeds;
   company-funding *databases* (Crunchbase, PitchBook) stayed tier 3 — paid,
   and already listed there.
   - **NIH RePORTER v2** (tier 1, US public domain, keyless) — one item per
     funded project-year: agency, award amount, institution, PIs, abstract.
     Old hosts (api.reporter.research.gov, reporternih.gov) are DNS-dead;
     the canonical host is `api.reporter.nih.gov`. The API ignores
     date-added criteria (verified), so there is no window query: the
     adapter re-lands the current + previous fiscal year per domain query
     each run — idempotent by the landing zone. First run landed 8,271
     project-years (5,605 relevant), FY 2026–27, ~$3.6B in obligations
     across 544 institutions.
   - **EU CORDIS** (tier 1, CC BY 4.0, keyless) — EU research projects
     (objective, EC contribution, total cost, status), via the portal's
     internal JSON search after the legacy REST API retired in 2026;
     queried inside `/project/objective`, re-landed full-snapshot like
     DrugAge. Single-result queries return `hit` as a dict, not a list
     (handled). 4,405 projects landed, 1,496 relevant.
   - **Trade press + institutional research news** (tier 2, keyless RSS) —
     GEN, Endpoints News, STAT News for funding/company coverage; MIT News
     (biology + medicine topics), Harvard Gazette, Salk, Babraham for
     university/institute research. Outlets' overlapping feeds (MIT's two
     topics carry the same article) dedupe by canonical URL across feeds —
     first feed to land it wins. Dead ends probed and documented: Fierce
     Biotech (Cloudflare), BioSpace (no RSS), Buck/Mayo/Stanford/USC/UCSF/
     AFAR/SENS (no usable feeds), EurekAlert (RSS dead since Dec 2023),
     NIA (RSS 404). Salk and Babraham feeds are live but dormant.
   - **Site**: grant items render as a funding record (agency, award,
     institution, PI, period for RePORTER; status, EC contribution, cost
     for CORDIS) with the honest caveat that a grant is evidence of money
     going somewhere, not of results. Research agents' citation allowlist
     now includes the institutional press offices the pipeline ingests.
   - **Known precision cost, measured**: ~1% of relevant items (127 in the
     grant sources) match only the demographic word "aged"
     (trial-eligibility language, e.g. "subjects aged 18–65"); the same
     class already existed in trial sources (48 items before). A gate
     refinement (v1.3, e.g. discounting "aged" when it is the sole match
     adjacent to a number range) is a possible later decision — recorded
     here rather than fixed mid-expansion, because gate changes ripple
     across every source.

All ten decisions closed (2026-11-09).

## 7. Milestones

Revised for a public product:

- **M0 — done, merged to main.** Source adapters for PubMed +
  ClinicalTrials.gov, raw JSON landing, dedupe.
- **M1 — done, merged to main.** Normalized item schema + relevance tagging
  + Postgres store **+ public web app skeleton: item pages, search,
  per-domain browse**.
- **M2 — done (this branch).** Tier-2 news outlets via RSS (13 feeds,
  keyless), the peptides domain (widened in the coverage expansion),
  relevance gate v1.2, the multi-agent research layer (decisions 7–8),
  the coverage expansion (decision 9): Europe PMC preprints +
  non-Medline OA, the DrugAge lifespan-assay dataset (`lifespan-data`
  domain), and ISRCTN + EU CTIS registry coverage; and the funding +
  institution expansion (decision 10): NIH RePORTER and EU CORDIS grant
  records plus trade-press and university research feeds.
- M3: editorial digest v1 ("what changed this week") as the landing page's top
  section + domain-map browse.
- M4: entity pages (compounds, trials, orgs) — moved up: the digest's links
  need a destination.
- M5: extraction pass + provenance/generated labels, shown on-page.
- M6: tracking/follow features for visitors.
