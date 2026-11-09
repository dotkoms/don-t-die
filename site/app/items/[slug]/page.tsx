import Link from "next/link";
import { notFound } from "next/navigation";
import { query } from "@/lib/db";
import type { Item } from "@/lib/types";

export const dynamic = "force-dynamic";

type DomainRow = { domain: string };

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
          <code>{item.relevance_method || "keyword-v1.1"}</code>): no
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
  const isCtgov = item.source === "ctgov";
  const isNews = !isPubmed && !isCtgov;
  const body = isPubmed
    ? item.raw.abstract
    : isNews
      ? item.raw.summary
      : item.raw.brief_summary;

  return (
    <main>
      <Link href="/" className="back">
        ← the domain map
      </Link>
      <h1>
        <a href={item.url}>{item.title}</a>
      </h1>

      <p className="meta">
        {isPubmed
          ? (item.raw.authors ?? []).join(", ")
          : isNews
            ? `${item.raw.outlet ?? item.source} · news coverage (tier 2)`
            : `Sponsor: ${item.raw.sponsor ?? "—"}`}
      </p>
      <p className="meta">
        {isPubmed
          ? item.raw.journal
          : isCtgov
            ? [
                item.raw.status,
                (item.raw.phases ?? []).join(" / "),
                item.raw.conditions?.join(", "),
              ]
                .filter(Boolean)
                .join(" · ")
            : "News summarizes evidence — check the primary source."}
        {item.published ? ` · ${item.published}` : ""}
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

      {body ? (
        <section>
          <h2>{isPubmed ? "Abstract" : isNews ? "Coverage summary" : "Brief summary"}</h2>
          <p className="abstract">{body}</p>
          <p className="attribution">
            {isPubmed
              ? "Abstract text © its publisher, redistributed with attribution under NCBI terms — "
              : isNews
                ? "News coverage from a tier-2 outlet — it summarizes primary evidence; only this short summary is stored, the article © its publisher — "
                : "US-government public domain via ClinicalTrials.gov — "}
            <a href={item.url}>
              view the record at{" "}
              {isPubmed ? "PubMed" : isNews ? (item.raw.outlet ?? item.source) : "ClinicalTrials.gov"}
            </a>.
          </p>
        </section>
      ) : null}

      <p className="meta">
        Relevance gate: <code>{item.relevance_method || "keyword-v1.1"}</code>,
        matched {item.relevance_terms.join(", ") || "—"}
      </p>
    </main>
  );
}
