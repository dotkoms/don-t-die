import { query } from "@/lib/db";
import type { Item } from "@/lib/types";

/**
 * The weekly digest (M3): one editorial issue per ISO week, rebuilt
 * deterministically by the pipeline (`python3 -m dontdie digest`).
 * These queries are read-only views over digests / digest_items.
 */

export type DigestStats = {
  items: number;
  trials: number;
  papers: number;
  grants: number;
  preprints: number;
  news: number;
  sections: Record<string, number>;
};

export type DigestMeta = {
  slug: string;
  week_start: string;
  week_end: string;
  stats: DigestStats;
};

export type DigestItem = Item & { rank: number; section: string };

export async function getDigest(
  slug?: string,
): Promise<DigestMeta | null> {
  const rows = await query<DigestMeta>(
    `SELECT slug, week_start::text AS week_start, week_end::text AS week_end, stats
     FROM digests
     ${slug ? "WHERE slug = $1" : ""}
     ORDER BY week_start DESC
     LIMIT 1`,
    slug ? [slug] : [],
  );
  return rows?.[0] ?? null;
}

export async function getDigestItems(
  slug: string,
  limit?: number,
): Promise<DigestItem[] | null> {
  return query<DigestItem>(
    `SELECT i.slug, i.source, i.source_id, i.title, i.url,
            i.published::text AS published, i.is_relevant,
            i.relevance_terms, i.raw,
            di.rank, di.section
     FROM digest_items di
     JOIN digests d ON d.id = di.digest_id
     JOIN items i ON i.id = di.item_id
     WHERE d.slug = $1
     ORDER BY di.rank
     ${limit ? `LIMIT ${limit}` : ""}`,
    [slug],
  );
}

export async function listDigests(): Promise<DigestMeta[] | null> {
  return query<DigestMeta>(
    `SELECT slug, week_start::text AS week_start, week_end::text AS week_end, stats
     FROM digests ORDER BY week_start DESC`,
  );
}

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/** "2026-11-02" + "2026-11-08" → "Nov 2 – Nov 8, 2026" */
export function weekLabel(weekStart: string, weekEnd: string): string {
  const s = weekStart.split("-").map(Number);
  const e = weekEnd.split("-").map(Number);
  const start = `${MONTHS[s[1] - 1]} ${s[2]}`;
  const end = `${MONTHS[e[1] - 1]} ${e[2]}`;
  return s[0] === e[0]
    ? `${start} – ${end}, ${e[0]}`
    : `${start}, ${s[0]} – ${end}, ${e[0]}`;
}

/** Honest one-liner of what an issue holds, e.g. "2 trials · 19 papers …". */
export function statsLine(stats: DigestStats): string {
  const parts = [
    stats.trials ? `${stats.trials} ${stats.trials === 1 ? "trial" : "trials"}` : null,
    stats.papers ? `${stats.papers} ${stats.papers === 1 ? "paper" : "papers"}` : null,
    stats.grants ? `${stats.grants} ${stats.grants === 1 ? "grant" : "grants"}` : null,
    stats.preprints
      ? `${stats.preprints} ${stats.preprints === 1 ? "preprint" : "preprints"}`
      : null,
    stats.news ? `${stats.news} news` : null,
  ].filter(Boolean);
  const domains = Object.keys(stats.sections ?? {}).length;
  return `${stats.items} ${stats.items === 1 ? "item" : "items"}: `
    + `${parts.join(" · ")} across ${domains} `
    + `${domains === 1 ? "section" : "sections"}`;
}
