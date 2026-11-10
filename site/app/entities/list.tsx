import Link from "next/link";
import {
  kindPath, linkLine, entitySubline,
  type Entity, type EntityKind,
} from "@/lib/entities";

/**
 * An index of one entity kind — shared by /compounds, /orgs and /trials.
 * Pages own their heading and tagline; this renders the list.
 */
export function EntityList({
  kind,
  entities,
}: {
  kind: EntityKind;
  entities: Entity[];
}) {
  return (
    <ul className="items entities">
      {entities.map((e) => (
        <li key={e.slug}>
          <Link href={`${kindPath(kind)}/${e.slug}`}>
            <strong>{e.name}</strong>
          </Link>{" "}
          <span className="count">{e.data.items}</span>
          <span className="meta">
            {entitySubline(e) ? `${entitySubline(e)} · ` : ""}
            {linkLine(e.data)}
          </span>
        </li>
      ))}
    </ul>
  );
}
