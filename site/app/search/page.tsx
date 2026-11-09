import Link from "next/link";
import { query } from "@/lib/db";
import { sourceLabel } from "@/lib/sourceLabel";
import type { Item } from "@/lib/types";

export const dynamic = "force-dynamic";

type Result = Item & { matched_in: string };

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q } = await searchParams;
  const trimmed = (q ?? "").trim();

  const rows = trimmed
    ? await query<Result>(
        `SELECT slug, source, source_id, title, url, published, is_relevant,
                relevance_terms, raw,
                CASE
                  WHEN title ILIKE $1 THEN 'title'
                  ELSE 'abstract'
                END AS matched_in
         FROM items
         WHERE is_relevant
           AND (title ILIKE $1
                OR COALESCE(raw->>'abstract', '') ILIKE $1
                OR COALESCE(raw->>'brief_summary', '') ILIKE $1)
         ORDER BY COALESCE(published, updated_at::date) DESC NULLS LAST
         LIMIT 50`,
        [`%${trimmed}%`],
      )
    : null;

  return (
    <main>
      <Link href="/" className="back">
        ← the domain map
      </Link>
      <h1>Search</h1>

      <form action="/search" className="search">
        <input
          type="search"
          name="q"
          defaultValue={trimmed}
          placeholder="e.g. rapamycin, reprogramming, epigenetic clock"
          aria-label="Search the corpus"
        />
      </form>

      {rows === null ? (
        <p className="empty">Enter a term to search the corpus.</p>
      ) : rows.length === 0 ? (
        <p className="empty">No relevant items match “{trimmed}”.</p>
      ) : (
        <ul className="items">
          {rows.map((item) => (
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
    </main>
  );
}
