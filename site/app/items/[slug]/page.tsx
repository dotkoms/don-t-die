import Link from "next/link";
import { notFound } from "next/navigation";
import { query } from "@/lib/db";
import { sourceLabel } from "@/lib/sourceLabel";
import type { Item } from "@/lib/types";

export const dynamic = "force-dynamic";

type DomainRow = { domain: string };

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
    `SELECT slug, source, source_id, title, url, published, is_relevant,
            relevance_terms, relevance_method, raw
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

  const isPubmed = item.source === "pubmed";
  const isDrugage = item.source === "drugage";
  const isPreprint = item.source === "europemc" && item.raw.preprint;
  const isCtgov = item.source === "ctgov";
  const isRegistry = item.source === "isrctn" || item.source === "ctis";
  const isNews = !(isPubmed || isDrugage || item.source === "europemc" ||
                   isCtgov || isRegistry);

  const body = isDrugage
    ? item.raw.summary
    : isPubmed || item.source === "europemc"
      ? item.raw.abstract
      : isNews
        ? item.raw.summary
        : isCtgov
          ? item.raw.brief_summary
          : item.raw.abstract; // ISRCTN / CTIS: conditions + interventions

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
