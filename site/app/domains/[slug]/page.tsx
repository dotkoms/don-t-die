import Link from "next/link";
import { notFound } from "next/navigation";
import { FollowButton } from "../../watching/FollowButton";
import { query } from "@/lib/db";
import { domainName } from "@/lib/domains";
import { sourceLabel } from "@/lib/sourceLabel";
import type { Item } from "@/lib/types";

export const dynamic = "force-dynamic";

type DomainRow = { domain: string };

export default async function DomainPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const [items, tagged] = await Promise.all([
    query<Item>(
      `SELECT slug, source, source_id, title, url,
              published::text AS published, is_relevant,
              relevance_terms, raw
       FROM items
       JOIN item_domains ON items.id = item_domains.item_id
       WHERE item_domains.domain = $1 AND items.is_relevant
       ORDER BY COALESCE(published, updated_at::date) DESC NULLS LAST
       LIMIT 200`,
      [slug],
    ),
    query<DomainRow>(
      `SELECT DISTINCT item_domains.domain
       FROM item_domains
       JOIN items ON items.id = item_domains.item_id
       WHERE items.is_relevant`,
    ),
  ]);

  const known = new Set((tagged ?? []).map((r) => r.domain));
  if (!known.has(slug) && !items) notFound();

  return (
    <main>
      <Link href="/" className="back">
        ← the domain map
      </Link>
      <h1>{domainName(slug)}</h1>
      <FollowButton kind="domain" slug={slug} />

      {items === null ? (
        <p className="empty">The store is not connected (no DATABASE_URL).</p>
      ) : items.length === 0 ? (
        <p className="empty">No relevant items in this domain yet.</p>
      ) : (
        <ul className="items">
          {items.map((item) => (
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
