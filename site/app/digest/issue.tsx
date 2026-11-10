import Link from "next/link";
import { DOMAINS, domainName } from "@/lib/domains";
import { sourceLabel } from "@/lib/sourceLabel";
import type { DigestItem, DigestMeta } from "@/lib/digest";
import { statsLine, weekLabel } from "@/lib/digest";

/** Items shown per section before the "+ N more" link. */
const PER_SECTION = 10;

function sectionLabel(slug: string): string {
  // Tier-2 news has no domain page — the issue gives it its own section.
  return slug === "coverage" ? "Media coverage" : domainName(slug);
}

function inProgress(weekEnd: string): boolean {
  return weekEnd >= new Date().toISOString().slice(0, 10);
}

/**
 * One full issue: sections in the domain-map order (the "coverage" section
 * last), items ranked inside each section by the pipeline's editorial rank
 * (trials → papers → funding → preprints → media echo).
 */
export function IssueView({
  digest,
  items,
}: {
  digest: DigestMeta;
  items: DigestItem[];
}) {
  const sections = new Map<string, DigestItem[]>();
  for (const item of items ?? []) {
    const list = sections.get(item.section) ?? [];
    list.push(item);
    sections.set(item.section, list);
  }
  const ordered = [
    ...DOMAINS.filter((d) => sections.has(d.slug)).map((d) => d.slug),
    ...(sections.has("coverage") ? ["coverage"] : []),
    ...[...sections.keys()].filter(
      (s) => !DOMAINS.some((d) => d.slug === s) && s !== "coverage",
    ),
  ];

  return (
    <article className="issue">
      <h2>{weekLabel(digest.week_start, digest.week_end)}</h2>
      <p className="meta">
        {statsLine(digest.stats)}
        {inProgress(digest.week_end)
          ? " — this issue is still open and updates daily"
          : ""}
      </p>

      {ordered.map((slug) => {
        const list = sections.get(slug) ?? [];
        const more = list.length - PER_SECTION;
        const shown = more > 0 ? list.slice(0, PER_SECTION) : list;
        return (
          <section key={slug}>
            <h3>
              {slug === "coverage" ? (
                sectionLabel(slug)
              ) : (
                <Link href={`/domains/${slug}`}>{sectionLabel(slug)}</Link>
              )}{" "}
              <span className="count">{list.length}</span>
            </h3>
            <ul className="items">
              {shown.map((item) => (
                <li key={item.slug}>
                  <Link href={`/items/${item.slug}`}>{item.title}</Link>{" "}
                  <span className="meta">
                    {sourceLabel(item)}
                    {item.published ? ` · ${item.published}` : ""}
                  </span>
                </li>
              ))}
            </ul>
            {more > 0 ? (
              <p className="meta">
                <Link href={`/domains/${slug}`}>
                  + {more} more in {sectionLabel(slug)}
                </Link>
              </p>
            ) : null}
          </section>
        );
      })}
    </article>
  );
}
