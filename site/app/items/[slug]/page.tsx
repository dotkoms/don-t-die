import Link from "next/link";
import { notFound } from "next/navigation";
import { query } from "@/lib/db";
import { getItemEntities, kindPath } from "@/lib/entities";
import { sourceLabel } from "@/lib/sourceLabel";
import type { Item } from "@/lib/types";

export const dynamic = "force-dynamic";

type DomainRow = { domain: string };

// One row per extracted field (M5); value is jsonb — a string for
// summary/evidence/outcome, a string array for interventions.
type ExtractionRow = {
  field: string;
  value: string | string[];
  model: string;
  extracted_at: string;
};

function row(parts: (string | null | undefined)[]): string {
  return parts.filter(Boolean).join(" · ");
}

export default async function ItemPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const rows = await query<Item>(
    `SELECT slug, source, source_id, title, url,
            published::text AS published, is_relevant,
            relevance_terms, relevance_method,
            is_retracted, retraction_nature, retraction_reason,
            retraction_date, retraction_url, raw
     FROM items WHERE slug = $1`,
    [slug],
  );
  const item = rows?.[0];

  if (!item) notFound();
  if (!item.is_relevant) {
    return (
      <main>
        <Link href="/" className="back">
          ← the domain map
        </Link>
        <h1>{item.title}</h1>
        <p className="empty">
          This item is in the corpus but did not pass the relevance gate (
          <code>{item.relevance_method || "keyword-v1.2"}</code>): no
          aging-science term found in its title or abstract. It is kept for
          auditability, not shown in public views.
        </p>
      </main>
    );
  }

  const domains = await query<DomainRow>(
    `SELECT domain FROM item_domains WHERE item_id = (
       SELECT id FROM items WHERE slug = $1
     )`,
    [slug],
  );

  const linkedEntities = await getItemEntities(slug);

  const extractions = await query<ExtractionRow>(
    `SELECT field, value, model, extracted_at::text AS extracted_at
     FROM extractions WHERE item_id = (
       SELECT id FROM items WHERE slug = $1
     )`,
    [slug],
  );

  const isPubmed = item.source === "pubmed";
  const isDrugage = item.source === "drugage";
  const isGenage = item.source === "genage";
  const isCellage = item.source === "cellage";
  const isAnage = item.source === "anage";
  const isCurated = isDrugage || isGenage || isCellage || isAnage;
  const isPreprint = item.source === "europemc" && item.raw.preprint;
  const isCtgov = item.source === "ctgov";
  const isRegistry = item.source === "isrctn" || item.source === "ctis";
  const isGrant =
    item.source === "reporter" || item.source === "cordis" ||
    item.source === "gtr";
  const isNews = !(isPubmed || isDrugage || item.source === "europemc" ||
                   isCtgov || isRegistry || isGrant || isGenage ||
                   isCellage || isAnage);

  const body = isDrugage
    ? item.raw.summary
    : isPubmed || item.source === "europemc"
      ? item.raw.abstract
      : isNews
        ? item.raw.summary
        : isCtgov
          ? item.raw.brief_summary
          : item.raw.abstract; // ISRCTN / CTIS / RePORTER / CORDIS / GtR

  const usd = (n?: number) =>
    n == null ? null : `$${n.toLocaleString("en-US")}`;
  const eur = (n?: string | number) => {
    if (n == null || n === "") return null;
    const v = Number(n);
    return Number.isFinite(v) ? `€${v.toLocaleString("en-US")}` : null;
  };
  const gbp = (n?: number) =>
    n == null ? null : `£${n.toLocaleString("en-GB")}`;

  const attribution = isPubmed
    ? ["Abstract text © its publisher, redistributed with attribution under NCBI terms — ", "PubMed"]
    : isPreprint
      ? [`${item.raw.preprint_server ?? "A preprint server"} preprint — a first report that has NOT been peer reviewed — `, "Europe PMC"]
      : item.source === "europemc"
        ? ["Open-access article via Europe PMC (non-Medline) — ", "Europe PMC"]
        : isCtgov
          ? ["US-government public domain via ClinicalTrials.gov — ", "ClinicalTrials.gov"]
          : item.source === "isrctn"
            ? ["Registry record from the ISRCTN Registry (public data) — ", "the ISRCTN Registry"]
            : item.source === "ctis"
              ? ["Registry record from the EU Clinical Trials Information System (public data) — ", "the EU Clinical Trials Information System"]
              : isDrugage
                ? ["Data from DrugAge (Human Ageing Genomic Resources), reused under CC BY 3.0 — ", "DrugAge"]
                : isGenage
                  ? ["Data from GenAge (Human Ageing Genomic Resources), reused under CC BY 3.0 — ", "GenAge"]
                  : isCellage
                    ? ["Data from CellAge (Human Ageing Genomic Resources), reused under CC BY 3.0 — ", "CellAge"]
                    : isAnage
                      ? ["Data from AnAge (Human Ageing Genomic Resources), reused under CC BY 3.0 — ", "AnAge"]
                      : item.source === "reporter"
                        ? ["Grant record from NIH RePORTER (US-government public domain) — ", "NIH RePORTER"]
                        : item.source === "cordis"
                          ? ["Project data from the EU CORDIS database, reused under CC BY 4.0 — ", "CORDIS"]
                          : item.source === "gtr"
                            ? ["Project data from UKRI Gateway to Research (public data) — ", "UKRI GtR"]
                            : ["News coverage from a tier-2 outlet — it summarizes primary evidence; only this short summary is stored, the article © its publisher — ",
                               item.raw.outlet ?? item.source];

  return (
    <main>
      <Link href="/" className="back">
        ← the domain map
      </Link>
      <h1>
        <a href={item.url}>{item.title}</a>
      </h1>

      {isPreprint ? (
        <p className="callout">
          Preprint — a first report that has not been peer reviewed.
        </p>
      ) : null}

      {item.is_retracted ? (
        <p className="callout">
          {item.retraction_nature ?? "Retracted"} by the journal
          {item.retraction_reason ? ` — ${item.retraction_reason}` : ""}
          {item.retraction_date ? ` (${item.retraction_date})` : ""}. Treat
          this record as withdrawn.
          {item.retraction_url ? (
            <>
              {" "}
              <a href={item.retraction_url}>View the notice</a>.
            </>
          ) : null}
        </p>
      ) : null}

      <p className="meta">{sourceLabel(item)}</p>
      <p className="meta">
        {row([
          item.published,
          isRegistry
            ? [
                item.raw.status,
                (item.raw.phases ?? []).join(" / "),
                item.raw.study_type,
                item.raw.enrollment != null
                  ? `n=${item.raw.enrollment}`
                  : null,
              ].filter(Boolean).join(" · ")
            : isGrant
              ? (item.source === "cordis"
                  ? item.raw.status
                  : item.raw.agency ?? item.raw.status) ?? ""
              : null,
        ])}
      </p>

      {domains && domains.length > 0 ? (
        <p className="domains-on-item">
          {(domains ?? []).map((d) => (
            <Link key={d.domain} href={`/domains/${d.domain}`}>
              {d.domain}
            </Link>
          ))}
        </p>
      ) : null}

      {linkedEntities && linkedEntities.length > 0 ? (
        <p className="domains-on-item">
          {(linkedEntities ?? []).map((e) => (
            <Link key={`${e.kind}/${e.slug}`} href={`${kindPath(e.kind)}/${e.slug}`}>
              {e.name}
            </Link>
          ))}
        </p>
      ) : null}

      {isDrugage ? (
        <section>
          <h2>Lifespan assay</h2>
          <dl className="facts">
            <div><dt>Compound</dt><dd>{item.raw.compound ?? "—"}</dd></div>
            <div><dt>Species</dt>
              <dd>{row([item.raw.species, item.raw.strain]) || "—"}</dd></div>
            <div><dt>Dosage</dt>
              <dd>{row([item.raw.dosage, item.raw.gender]) || "—"}</dd></div>
            <div><dt>Avg lifespan change</dt>
              <dd>{item.raw.avg_lifespan_change_percent || "—"}
                {item.raw.avg_lifespan_significance
                  ? ` (p=${item.raw.avg_lifespan_significance})` : ""}</dd></div>
            <div><dt>Max lifespan change</dt>
              <dd>{item.raw.max_lifespan_change_percent || "—"}
                {item.raw.max_lifespan_significance
                  ? ` (p=${item.raw.max_lifespan_significance})` : ""}</dd></div>
            <div><dt>Interventional Testing Program</dt>
              <dd>{item.raw.itp || "—"}</dd></div>
          </dl>
          {body ? <p className="abstract">{body}</p> : null}
          {item.raw.pubmed_id ? (
            <p className="meta">
              Underlying study:{" "}
              <a href={`https://pubmed.ncbi.nlm.nih.gov/${item.raw.pubmed_id}/`}>
                PubMed {item.raw.pubmed_id}
              </a>
            </p>
          ) : null}
        </section>
      ) : isRegistry ? (
        <section>
          <h2>Trial record</h2>
          <dl className="facts">
            <div><dt>Status</dt><dd>{item.raw.status || "—"}</dd></div>
            <div><dt>Phases</dt>
              <dd>{(item.raw.phases ?? []).join(" / ") || "—"}</dd></div>
            <div><dt>Enrollment</dt>
              <dd>{item.raw.enrollment ?? "—"}</dd></div>
            <div><dt>Sponsor</dt>
              <dd>{item.raw.sponsor ?? "—"}</dd></div>
            {item.raw.study_design ? (
              <div><dt>Design</dt><dd>{item.raw.study_design}</dd></div>
            ) : null}
            {item.raw.conditions ? (
              <div><dt>Conditions</dt><dd>{item.raw.conditions}</dd></div>
            ) : null}
            {item.raw.interventions ? (
              <div><dt>Interventions</dt><dd>{item.raw.interventions}</dd></div>
            ) : null}
            {(item.raw.countries ?? []).length > 0 ? (
              <div><dt>Countries</dt>
                <dd>{(item.raw.countries ?? []).join(", ")}</dd></div>
            ) : null}
            {item.raw.registration_date ? (
              <div><dt>Registered</dt><dd>{item.raw.registration_date}</dd></div>
            ) : null}
            {item.raw.decision_date ? (
              <div><dt>Decision</dt><dd>{item.raw.decision_date}</dd></div>
            ) : null}
          </dl>
          {body ? <p className="abstract">{body}</p> : null}
        </section>
      ) : isGrant ? (
        <section>
          <h2>Funding record</h2>
          {item.source === "reporter" ? (
            <dl className="facts">
              <div><dt>Funding agency</dt>
                <dd>{item.raw.agency || "NIH"}</dd></div>
              <div><dt>Award</dt>
                <dd>{usd(item.raw.award_amount) || "—"}
                  {item.raw.fiscal_year ? ` (FY ${item.raw.fiscal_year})` : ""}</dd></div>
              {item.raw.award_type ? (
                <div><dt>Award type</dt><dd>{item.raw.award_type}</dd></div>
              ) : null}
              <div><dt>Institution</dt>
                <dd>{row([item.raw.institution,
                           item.raw.org_city, item.raw.org_state]) || "—"}</dd></div>
              <div><dt>Principal investigator</dt>
                <dd>{(item.raw.pi_names ?? []).join(", ") || "—"}</dd></div>
              <div><dt>Project period</dt>
                <dd>{row([item.raw.project_start_date,
                          item.raw.project_end_date]) || "—"}</dd></div>
              <div><dt>Active</dt>
                <dd>{item.raw.is_active ? "Yes" : "No"}</dd></div>
              {item.raw.project_num ? (
                <div><dt>Project number</dt><dd>{item.raw.project_num}</dd></div>
              ) : null}
            </dl>
          ) : item.source === "gtr" ? (
            <dl className="facts">
              <div><dt>Funding council</dt>
                <dd>{item.raw.agency || "UKRI"}</dd></div>
              <div><dt>Award</dt>
                <dd>{gbp(item.raw.award_amount) || "—"}</dd></div>
              {item.raw.grant_reference ? (
                <div><dt>Grant reference</dt>
                  <dd>{item.raw.grant_reference}</dd></div>
              ) : null}
              {item.raw.grant_category ? (
                <div><dt>Category</dt><dd>{item.raw.grant_category}</dd></div>
              ) : null}
              <div><dt>Institution</dt>
                <dd>{item.raw.institution || "—"}</dd></div>
              <div><dt>Principal investigator</dt>
                <dd>{(item.raw.pi_names ?? []).join(", ") || "—"}</dd></div>
              <div><dt>Project period</dt>
                <dd>{row([item.raw.project_start_date,
                          item.raw.project_end_date]) || "—"}</dd></div>
              <div><dt>Status</dt>
                <dd>{item.raw.status || "—"}</dd></div>
              {(item.raw.research_topics ?? []).length > 0 ? (
                <div><dt>Research topics</dt>
                  <dd>{(item.raw.research_topics ?? []).join(", ")}</dd></div>
              ) : null}
            </dl>
          ) : (
            <dl className="facts">
              <div><dt>Programme</dt>
                <dd>Horizon Europe / EU research funding</dd></div>
              <div><dt>Status</dt>
                <dd>{item.raw.status || "—"}</dd></div>
              <div><dt>EC contribution</dt>
                <dd>{eur(item.raw.ec_contribution) || "—"}</dd></div>
              <div><dt>Total cost</dt>
                <dd>{eur(item.raw.total_cost) || "—"}</dd></div>
              <div><dt>Project period</dt>
                <dd>{row([item.raw.start_date, item.raw.end_date]) || "—"}</dd></div>
              {item.raw.acronym ? (
                <div><dt>Acronym</dt><dd>{item.raw.acronym}</dd></div>
              ) : null}
            </dl>
          )}
          {body ? (
            <p className="abstract">{body}</p>
          ) : null}
          <p className="meta">
            A funded grant record — evidence of what money is going where,
            not of results. See the project&apos;s publications in the corpus.
          </p>
        </section>
      ) : isGenage ? (
        <section>
          <h2>Aging gene record</h2>
          <dl className="facts">
            <div><dt>Gene</dt>
              <dd>{row([item.raw.gene_symbol, item.raw.gene_name]) || "—"}</dd>
            </div>
            {item.raw.dataset === "human" ? (
              <>
                {item.raw.evidence ? (
                  <div><dt>Evidence</dt><dd>{item.raw.evidence}</dd></div>
                ) : null}
                {item.raw.uniprot ? (
                  <div><dt>UniProt</dt><dd>{item.raw.uniprot}</dd></div>
                ) : null}
              </>
            ) : (
              <>
                <div><dt>Organism</dt>
                  <dd>{item.raw.organism || "—"}</dd></div>
                {item.raw.longevity_influence ? (
                  <div><dt>Longevity influence</dt>
                    <dd>{item.raw.longevity_influence}</dd></div>
                ) : null}
                {item.raw.lifespan_effect ? (
                  <div><dt>Lifespan effect</dt>
                    <dd>{item.raw.lifespan_effect}</dd></div>
                ) : null}
                {item.raw.avg_lifespan_change_percent ? (
                  <div><dt>Avg lifespan change</dt>
                    <dd>{item.raw.avg_lifespan_change_percent}</dd></div>
                ) : null}
              </>
            )}
          </dl>
          {body ? <p className="abstract">{body}</p> : null}
        </section>
      ) : isCellage ? (
        <section>
          <h2>Senescence gene record</h2>
          <dl className="facts">
            <div><dt>Gene</dt>
              <dd>{row([item.raw.gene_symbol, item.raw.gene_name]) || "—"}</dd>
            </div>
            <div><dt>Effect on senescence</dt>
              <dd>{item.raw.senescence_effect || "—"}</dd></div>
            {item.raw.senescence_type ? (
              <div><dt>Senescence type</dt>
                <dd>{item.raw.senescence_type}</dd></div>
            ) : null}
            {item.raw.cancer_cell ? (
              <div><dt>Cancer cell</dt><dd>{item.raw.cancer_cell}</dd></div>
            ) : null}
          </dl>
          {body ? <p className="abstract">{body}</p> : null}
          {item.raw.pubmed_id ? (
            <p className="meta">
              Underlying study:{" "}
              <a href={`https://pubmed.ncbi.nlm.nih.gov/${item.raw.pubmed_id}/`}>
                PubMed {item.raw.pubmed_id}
              </a>
            </p>
          ) : null}
        </section>
      ) : isAnage ? (
        <section>
          <h2>Species longevity record</h2>
          <dl className="facts">
            <div><dt>Species</dt>
              <dd>{row([item.raw.species, item.raw.common_name]) || "—"}</dd>
            </div>
            <div><dt>Maximum longevity</dt>
              <dd>{item.raw.max_longevity_years
                ? `${item.raw.max_longevity_years} years` : "—"}</dd></div>
            {row([item.raw.taxon_class, item.raw.taxon_order,
                  item.raw.taxon_family]) ? (
              <div><dt>Taxonomy</dt>
                <dd>{row([item.raw.taxon_class, item.raw.taxon_order,
                           item.raw.taxon_family])}</dd></div>
            ) : null}
            {item.raw.adult_weight_g ? (
              <div><dt>Adult weight</dt>
                <dd>{Number(item.raw.adult_weight_g).toLocaleString("en-US")} g
                </dd></div>
            ) : null}
            {item.raw.specimen_origin ? (
              <div><dt>Specimen origin</dt>
                <dd>{item.raw.specimen_origin}</dd></div>
            ) : null}
            {item.raw.data_quality ? (
              <div><dt>Data quality</dt><dd>{item.raw.data_quality}</dd></div>
            ) : null}
          </dl>
          {body ? <p className="abstract">{body}</p> : null}
        </section>
      ) : body ? (
        <section>
          <h2>
            {isPubmed || item.source === "europemc"
              ? "Abstract"
              : isNews ? "Coverage summary" : "Brief summary"}
          </h2>
          <p className="abstract">{body}</p>
        </section>
      ) : null}

      {extractions && extractions.length > 0 ? (() => {
        const byField = Object.fromEntries(
          extractions.map((r) => [r.field, r]),
        );
        const model = extractions[0].model;
        const date = extractions[0].extracted_at.slice(0, 10);
        return (
          <section>
            <h2>AI-extracted summary</h2>
            <p className="callout">
              Generated by <code>{model}</code> on {date} — an LLM extraction
              of this record, labeled as such and never merged with the
              source data above. A mouse or cell result is never evidence in
              humans.
            </p>
            <dl className="facts">
              <div><dt>Summary</dt>
                <dd>{byField.summary?.value ?? "—"}</dd></div>
              <div><dt>Evidence level</dt>
                <dd>{byField.evidence?.value ?? "—"}</dd></div>
              <div><dt>Interventions studied</dt>
                <dd>{Array.isArray(byField.interventions?.value)
                  ? byField.interventions.value.join(", ") || "—"
                  : "—"}</dd></div>
              <div><dt>Outcome</dt>
                <dd>{byField.outcome?.value ?? "—"}</dd></div>
            </dl>
          </section>
        );
      })() : null}

      <p className="attribution">
        {attribution[0]}
        <a href={item.url}>view the record at {attribution[1]}</a>.
      </p>

      <p className="meta">
        Relevance gate: <code>{item.relevance_method || "keyword-v1.2"}</code>,
        matched {item.relevance_terms.join(", ") || "—"}
      </p>
    </main>
  );
}
