import Link from "next/link";
import { query } from "@/lib/db";
import { DOMAINS } from "@/lib/domains";
import { sourceLabel } from "@/lib/sourceLabel";
import type { Item } from "@/lib/types";

export const dynamic = "force-dynamic";

type CountRow = { domain: string; n: string };

export default async function Home() {
  const [domainCounts, recent] = await Promise.all([
    query<CountRow>(
      `SELECT domain, count(*)::text AS n
       FROM item_domains
       JOIN items ON items.id = item_domains.item_id
       WHERE items.is_relevant
       GROUP BY domain`,
    ),
    query<Item>(
      `SELECT slug, source, source_id, title, url, published, is_relevant,
              relevance_terms, raw
       FROM items WHERE is_relevant
       ORDER BY COALESCE(published, updated_at::date) DESC NULLS LAST
       LIMIT 10`,
    ),
  ]);

  const counts = new Map((domainCounts ?? []).map((r) => [r.domain, Number(r.n)]));
  const total = [...counts.values()].reduce((a, b) => a + b, 0);

  return (
    <main>
      <h1>don&apos;t die</h1>
      <p className="tagline">
        A public knowledge base for life-extension medical science — gathered
        from PubMed, trial registries, grant databases and verifiable news
        outlets, tagged, and open to browse.
      </p>

      {domainCounts === null ? (
        <p className="empty">
          The store is not connected (no <code>DATABASE_URL</code>). Run the
          pipeline first: <code>migrate</code>, then <code>fetch</code> +{" "}
          <code>load</code>.
        </p>
      ) : (
        <>
          <form action="/search" className="search">
            <input
              type="search"
              name="q"
              placeholder="Search the corpus…"
              aria-label="Search the corpus"
            />
          </form>

          <h2>The domain map</h2>
          <ul className="domains">
            {DOMAINS.map((d) => (
              <li key={d.slug}>
                <Link href={`/domains/${d.slug}`}>
                  <strong>{d.name}</strong>
                </Link>{" "}
                <span className="count">{counts.get(d.slug) ?? 0}</span>
                <p>{d.blurb}</p>
              </li>
            ))}
          </ul>

          <h2>Recently gathered</h2>
          {total === 0 ? (
            <p className="empty">
              The corpus is empty — the pipeline has not loaded any relevant
              items yet.
            </p>
          ) : (
            <ul className="items">
              {(recent ?? []).map((item) => (
                <li key={item.slug}>
                  <Link href={`/items/${item.slug}`}>{item.title}</Link>{" "}
                  <span className="meta">
                    {sourceLabel(item)}
                    {item.published ? ` · ${item.published}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      <footer>
        <p>
          Abstracts are redistributed with attribution and link back to their
          source (NCBI terms; ClinicalTrials.gov is US-government public
          domain; news is summarized, never mirrored, always link-back).
          Relevance tagging is a transparent keyword gate,{" "}
          <code>keyword-v1.2</code> — not a model. News items are tier-2
          coverage, distinct from primary sources.
        </p>
      </footer>
    </main>
  );
}
