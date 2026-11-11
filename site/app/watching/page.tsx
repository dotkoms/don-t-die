import Link from "next/link";
import { WatchingSync, WatchlistTools } from "./client";
import { domainName } from "@/lib/domains";
import {
  entitySubline, kindLabel, kindPath, linkLine, type EntityKind,
} from "@/lib/entities";
import { sourceLabel } from "@/lib/sourceLabel";
import {
  domainCounts, domainItems, entityItems, entityRecentCount,
  getWatchedEntity, trialStatus, type WatchItem,
} from "@/lib/watching";

export const dynamic = "force-dynamic";

type Search = { d?: string; c?: string; o?: string; t?: string };

const ENTITY_KINDS: { param: "c" | "o" | "t"; kind: EntityKind }[] = [
  { param: "c", kind: "compound" },
  { param: "o", kind: "org" },
  { param: "t", kind: "trial" },
];

function watched(param: string | undefined): string[] {
  return (param ?? "").split(",").filter(Boolean);
}

/** One recent item: source, date, digest marker, and the M5 extraction
 * summary when one exists — labeled as generated. */
function WatchedItem({ item }: { item: WatchItem }) {
  return (
    <li>
      <Link href={`/items/${item.slug}`}>{item.title}</Link>{" "}
      <span className="meta">
        {sourceLabel(item)}
        {item.published ? ` · ${item.published}` : ""}
        {item.in_digest ? " · in this week's digest" : ""}
      </span>
      {item.ai_summary ? (
        <span className="meta ai-summary">
          {" "}(AI-extracted) {item.ai_summary}
        </span>
      ) : null}
    </li>
  );
}

async function DomainSection({ slug }: { slug: string }) {
  const [counts, items] = await Promise.all([
    domainCounts(slug),
    domainItems(slug),
  ]);
  return (
    <section>
      <h2>
        <Link href={`/domains/${slug}`}>{domainName(slug)}</Link>{" "}
        <span className="count">
          {counts
            ? `${counts.total.toLocaleString("en-US")} items · ` +
              `${counts.recent} new in the last two weeks`
            : ""}
        </span>
      </h2>
      {items && items.length > 0 ? (
        <ul className="items">
          {items.map((i) => <WatchedItem key={i.slug} item={i} />)}
        </ul>
      ) : (
        <p className="empty">No relevant items in this domain yet.</p>
      )}
    </section>
  );
}

async function EntitySection({ kind, slug }: { kind: EntityKind; slug: string }) {
  const [entity, recent, items] = await Promise.all([
    getWatchedEntity(kind, slug),
    entityRecentCount(kind, slug),
    entityItems(kind, slug),
  ]);
  const status =
    kind === "trial" && entity?.data.record_slug
      ? await trialStatus(entity.data.record_slug)
      : null;

  if (!entity) {
    return (
      <section>
        <h2>{slug}</h2>
        <p className="empty">
          No {kindLabel(kind)} by this slug in the corpus — it may have been
          rebuilt since you followed it.
        </p>
      </section>
    );
  }

  return (
    <section>
      <h2>
        <Link href={`${kindPath(kind)}/${slug}`}>{entity.name}</Link>{" "}
        <span className="count">
          {recent !== null
            ? `${recent} new linked item${recent === 1 ? "" : "s"} in the last two weeks`
            : ""}
        </span>
      </h2>
      <p className="meta">
        {[
          entitySubline(entity),
          status ? `status: ${status}` : null,
          linkLine(entity.data),
        ].filter(Boolean).join(" · ")}
      </p>
      {items && items.length > 0 ? (
        <ul className="items">
          {items.map((i) => <WatchedItem key={i.slug} item={i} />)}
        </ul>
      ) : (
        <p className="empty">No linked items yet.</p>
      )}
    </section>
  );
}

export default async function WatchingPage({
  searchParams,
}: {
  searchParams: Promise<Search>;
}) {
  const params = await searchParams;
  const hasParams = Boolean(params.d || params.c || params.o || params.t);
  const domains = watched(params.d);
  const entities = ENTITY_KINDS.flatMap(({ param, kind }) =>
    watched(params[param]).map((slug) => ({ kind, slug })),
  );
  const followedCount = domains.length + entities.length;

  return (
    <main className="watching">
      <WatchingSync hasParams={hasParams} />
      <Link href="/" className="back">
        ← the domain map
      </Link>
      <h1>Watching</h1>

      {!hasParams || followedCount === 0 ? (
        followedCount === 0 ? (
          <p className="empty">
            You are not following anything yet. Open a{" "}
            <Link href="/">domain</Link>, a{" "}
            <Link href="/compounds">compound</Link>, an{" "}
            <Link href="/orgs">organization</Link> or a{" "}
            <Link href="/trials">trial</Link> and press Follow — the list
            lives in this browser only (never on the server), and this page
            becomes your view of what changed lately in everything you
            follow.
          </p>
        ) : null
      ) : (
        <>
          {domains.map((slug) => (
            <DomainSection key={`domain/${slug}`} slug={slug} />
          ))}
          {entities.map(({ kind, slug }) => (
            <EntitySection key={kind + "/" + slug} kind={kind} slug={slug} />
          ))}
        </>
      )}

      <WatchlistTools />
      <p className="meta">
        <Link href="/">Browse the domain map</Link>
      </p>
    </main>
  );
}
