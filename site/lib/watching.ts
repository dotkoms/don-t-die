import { query } from "@/lib/db";
import type { Entity, EntityKind } from "@/lib/entities";

/**
 * The /watching page's read-only queries (M6, decision 15). For each
 * followed thing, the page shows everything the store honestly knows:
 * totals, what changed lately (last 14 days), the most recent items with
 * their AI-extracted summary when one exists (labeled), and a marker for
 * anything that made this week's digest.
 */

export type WatchItem = {
  slug: string;
  title: string;
  url: string;
  source: string;
  source_id: string;
  published: string | null;
  raw: Record<string, unknown>;
  ai_summary: string | null;
  in_digest: boolean;
};

export type WatchCounts = { total: number; recent: number };

// The shared item shape: recent-first, with the extraction summary (when
// the item has one, M5-labeled on the item page — here shown as a snippet)
// and the current-week digest marker.
const ITEM_SELECT = `
  SELECT i.slug, i.title, i.url, i.source, i.source_id,
         i.published::text AS published, i.raw,
         es.value AS ai_summary,
         (di.item_id IS NOT NULL) AS in_digest
  FROM items i
  LEFT JOIN extractions es
    ON es.item_id = i.id AND es.field = 'summary'
  LEFT JOIN digest_items di
    ON di.item_id = i.id
   AND di.digest_id = (SELECT id FROM digests ORDER BY week_start DESC LIMIT 1)
`;

export async function domainCounts(domain: string): Promise<WatchCounts | null> {
  const rows = await query<WatchCounts>(
    `SELECT count(*)::int AS total,
            count(*) FILTER (
              WHERE COALESCE(i.published::date, i.updated_at::date)
                    >= current_date - 14
            )::int AS recent
     FROM items i
     JOIN item_domains idm ON idm.item_id = i.id
     WHERE idm.domain = $1 AND i.is_relevant`,
    [domain],
  );
  return rows?.[0] ?? null;
}

export async function domainItems(
  domain: string,
  limit = 8,
): Promise<WatchItem[] | null> {
  return query<WatchItem>(
    `${ITEM_SELECT}
     JOIN item_domains idm ON idm.item_id = i.id
     WHERE idm.domain = $1 AND i.is_relevant
     ORDER BY COALESCE(i.published, i.updated_at) DESC NULLS LAST
     LIMIT ${limit}`,
    [domain],
  );
}

export async function entityRecentCount(
  kind: EntityKind,
  slug: string,
): Promise<number | null> {
  const rows = await query<{ recent: number }>(
    `SELECT count(*) FILTER (
              WHERE COALESCE(i.published::date, i.updated_at::date)
                    >= current_date - 14
            )::int AS recent
     FROM item_entities ie
     JOIN entities e ON e.id = ie.entity_id
     JOIN items i ON i.id = ie.item_id
     WHERE e.kind = $1 AND e.slug = $2 AND i.is_relevant`,
    [kind, slug],
  );
  return rows?.[0]?.recent ?? null;
}

export async function entityItems(
  kind: EntityKind,
  slug: string,
  limit = 8,
): Promise<WatchItem[] | null> {
  return query<WatchItem>(
    `${ITEM_SELECT}
     JOIN item_entities ie ON ie.item_id = i.id
     JOIN entities e ON e.id = ie.entity_id
     WHERE e.kind = $1 AND e.slug = $2 AND i.is_relevant
     ORDER BY COALESCE(i.published, i.updated_at) DESC NULLS LAST
     LIMIT ${limit}`,
    [kind, slug],
  );
}

/** A followed trial's current status, read from its registry record item. */
export async function trialStatus(
  recordSlug: string | undefined,
): Promise<string | null> {
  if (!recordSlug) return null;
  const rows = await query<{ status: string | null }>(
    `SELECT raw->>'status' AS status FROM items WHERE slug = $1`,
    [recordSlug],
  );
  return rows?.[0]?.status ?? null;
}

/** The followed entity itself (name, data) — getEntity narrowed to the
 * kinds a visitor can watch. */
export async function getWatchedEntity(
  kind: EntityKind,
  slug: string,
): Promise<Entity | null> {
  const rows = await query<Entity>(
    `SELECT kind, slug, name, data FROM entities WHERE kind = $1 AND slug = $2`,
    [kind, slug],
  );
  return rows?.[0] ?? null;
}
