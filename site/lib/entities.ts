import { query } from "@/lib/db";
import type { Item } from "@/lib/types";

/**
 * Entity pages (M4): compounds, organizations, trials — the destinations the
 * digest and item pages link into. The pipeline rebuilds both tables
 * deterministically every run (`python3 -m dontdie entities`); these queries
 * are read-only views over entities / item_entities.
 */

export type EntityKind = "compound" | "org" | "trial";

export type EntityData = {
  family?: string;
  registry?: string;
  registry_id?: string;
  record_slug?: string;
  items: number;
  assay?: number;
  record?: number;
  citation?: number;
  funding?: number;
  sponsor?: number;
  mention?: number;
};

export type Entity = {
  kind: EntityKind;
  slug: string;
  name: string;
  data: EntityData;
};

export async function getEntity(
  kind: EntityKind,
  slug: string,
): Promise<Entity | null> {
  const rows = await query<Entity>(
    `SELECT kind, slug, name, data FROM entities
     WHERE kind = $1 AND slug = $2`,
    [kind, slug],
  );
  return rows?.[0] ?? null;
}

export async function listEntities(
  kind: EntityKind,
): Promise<Entity[] | null> {
  return query<Entity>(
    `SELECT kind, slug, name, data FROM entities
     WHERE kind = $1
     ORDER BY (data->>'items')::int DESC, name`,
    [kind],
  );
}

export async function getEntityItems(
  kind: EntityKind,
  slug: string,
  limit?: number,
): Promise<Item[] | null> {
  return query<Item>(
    `SELECT i.slug, i.source, i.source_id, i.title, i.url,
            i.published::text AS published, i.is_relevant,
            i.relevance_terms, i.raw
     FROM item_entities ie
     JOIN entities e ON e.id = ie.entity_id
     JOIN items i ON i.id = ie.item_id
     WHERE e.kind = $1 AND e.slug = $2
     ORDER BY i.published DESC NULLS LAST, i.updated_at DESC NULLS LAST
     ${limit ? `LIMIT ${limit}` : ""}`,
    [kind, slug],
  );
}

/** The entities an item links to, most specific kind first — the item page's
 * "appears in" line. */
export async function getItemEntities(
  itemSlug: string,
): Promise<(Entity & { how: string })[] | null> {
  return query<Entity & { how: string }>(
    `SELECT e.kind, e.slug, e.name, e.data, ie.how
     FROM item_entities ie
     JOIN entities e ON e.id = ie.entity_id
     JOIN items i ON i.id = ie.item_id
     WHERE i.slug = $1`,
    [itemSlug],
  );
}

export function kindPath(kind: EntityKind): string {
  return kind === "org" ? "/orgs" : `/${kind}s`;
}

export function kindLabel(kind: EntityKind): string {
  return kind === "org" ? "organization" : kind;
}

const KINDS: Record<EntityKind, (e: Entity) => string | null> = {
  compound: (e) => e.data.family ?? null,
  org: () => null,
  trial: (e) =>
    e.data.registry && e.data.registry_id
      ? `${e.data.registry.toUpperCase()} · ${e.data.registry_id}`
      : null,
};

export function entitySubline(entity: Entity): string | null {
  return KINDS[entity.kind]?.(entity) ?? null;
}

/** An honest one-liner of how the corpus is linked to an entity, e.g.
 * "303 items: 6 lifespan assays · 297 mentions" (no bullets — plain text). */
export function linkLine(data: EntityData): string {
  const parts: string[] = [];
  if (data.assay) parts.push(`${data.assay} lifespan ${data.assay === 1 ? "assay" : "assays"}`);
  if (data.record) parts.push(`${data.record} registry ${data.record === 1 ? "record" : "records"}`);
  if (data.citation) parts.push(`${data.citation} ${data.citation === 1 ? "item cites" : "items cite"} it`);
  if (data.funding) parts.push(`${data.funding} funded ${data.funding === 1 ? "grant" : "grants"}`);
  if (data.sponsor) parts.push(`sponsors ${data.sponsor} ${data.sponsor === 1 ? "trial" : "trials"}`);
  if (data.mention) parts.push(`${data.mention} ${data.mention === 1 ? "mention" : "mentions"}`);
  return `${data.items} ${data.items === 1 ? "linked item" : "linked items"}`
    + (parts.length ? ` — ${parts.join(" · ")}` : "");
}
