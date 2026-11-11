import Link from "next/link";
import { FollowButton } from "../watching/FollowButton";
import { sourceLabel } from "@/lib/sourceLabel";
import { linkLine, entitySubline, kindPath, kindLabel } from "@/lib/entities";
import type { Entity } from "@/lib/entities";
import type { Item } from "@/lib/types";

/**
 * One entity's page — shared by /compounds/[slug], /orgs/[slug] and
 * /trials/[slug]. The pipeline rebuilds these lists every run; the page shows
 * exactly the linked corpus items, most recent editorially first.
 */
export function EntityDetail({
  entity,
  items,
}: {
  entity: Entity;
  items: Item[];
}) {
  return (
    <>
      <h1>{entity.name}</h1>
      <FollowButton kind={entity.kind} slug={entity.slug} />
      <p className="meta">
        {entitySubline(entity)}
        {entitySubline(entity) ? " · " : ""}
        a {kindLabel(entity.kind)} in the corpus
      </p>
      <p className="meta">{linkLine(entity.data)}</p>

      {entity.kind === "trial" && entity.data.record_slug ? (
        <p className="meta">
          Registry record:{" "}
          <Link href={`/items/${entity.data.record_slug}`}>
            {entity.data.registry_id}
          </Link>
        </p>
      ) : null}

      {entity.kind === "compound" && entity.data.assay ? (
        <p className="meta">
          Includes DrugAge lifespan {entity.data.assay === 1 ? "assay" : "assays"}{" "}
          (tier-2 curated dataset, CC BY 3.0), linked by the compound the
          dataset itself records.
        </p>
      ) : null}

      {entity.kind === "org" ? (
        <p className="meta">
          Name variants from the grant registries and trial sponsors collapse
          here; the display name prefers a properly-cased form.
        </p>
      ) : null}

      <h2>Linked items</h2>
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
      <p className="meta">
        <Link href={kindPath(entity.kind)}>
          ← all {kindLabel(entity.kind)}s
        </Link>
      </p>
    </>
  );
}
