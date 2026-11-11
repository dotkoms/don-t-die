import Link from "next/link";
import { query } from "@/lib/db";
import { DOMAINS } from "@/lib/domains";
import { getDigest, getDigestItems, statsLine, weekLabel } from "@/lib/digest";
import { sourceLabel } from "@/lib/sourceLabel";
import type { Item } from "@/lib/types";

export const dynamic = "force-dynamic";

type CountRow = { domain: string; n: string };

export default async function Home() {
  const [domainCounts, recent, digest] = await Promise.all([
    query<CountRow>(
      `SELECT domain, count(*)::text AS n
       FROM item_domains
       JOIN items ON items.id = item_domains.item_id
       WHERE items.is_relevant
       GROUP BY domain`,
    ),
    query<Item>(
      `SELECT slug, source, source_id, title, url,
              published::text AS published, is_relevant,
              relevance_terms, raw
       FROM items WHERE is_relevant
         AND published IS NOT NULL AND published <= CURRENT_DATE
       ORDER BY COALESCE(published, updated_at::date) DESC NULLS LAST
       LIMIT 10`,
    ),
    getDigest(),
  ]);
  const lead = digest ? await getDigestItems(digest.slug, 5) : null;

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

          <p className="meta">
            Browse by entity: <Link href="/compounds">compounds</Link> ·{" "}
            <Link href="/trials">trials</Link> ·{" "}
            <Link href="/orgs">organizations</Link>
          </p>
          <p className="meta">
            Follow things you care about and see{" "}
            <Link href="/watching">what changed lately</Link> — the list
            stays in your browser.
          </p>

          <h2 id="this-week">This week</h2>
          {digest && lead && lead.length > 0 ? (
            <>
              <p className="meta">
                <Link href={`/digest/${digest.slug}`}>
                  {weekLabel(digest.week_start, digest.week_end)}
                </Link>{" "}
                — {statsLine(digest.stats)}
              </p>
              <ul className="items">
                {lead.map((item) => (
                  <li key={item.slug}>
                    <Link href={`/items/${item.slug}`}>{item.title}</Link>{" "}
                    <span className="meta">
                      {sourceLabel(item)}
                      {item.published ? ` · ${item.published}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="meta">
                <Link href="/digest">Read the full issue →</Link>
              </p>
            </>
          ) : (
            <p className="empty">
              No digest issue yet — the pipeline has not built one. Run{" "}
              <code>python3 -m dontdie digest</code> against a loaded corpus.
            </p>
          )}

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
