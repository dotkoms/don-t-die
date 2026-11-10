import Link from "next/link";
import { getDigest, getDigestItems, listDigests, weekLabel } from "@/lib/digest";
import { IssueView } from "./issue";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "The weekly digest — don't die",
};

export default async function DigestPage() {
  const [digest, all] = await Promise.all([
    getDigest(),
    listDigests(),
  ]);
  const items = digest ? await getDigestItems(digest.slug) : null;

  return (
    <main>
      <Link href="/" className="back">
        ← the domain map
      </Link>
      <h1>The weekly digest</h1>
      <p className="tagline">
        What changed in life-extension science, one issue per week — trials,
        papers, funding and preprints first, media echo last. Every issue is
        rebuilt from the corpus, never hand-written.
      </p>

      {digest === null ? (
        <p className="empty">
          No digest issue exists yet — the pipeline has not built one. Run{" "}
          <code>python3 -m dontdie digest</code> (or the full{" "}
          <code>run</code>) with a loaded corpus.
        </p>
      ) : (
        <IssueView digest={digest} items={items ?? []} />
      )}

      {all && all.length > 0 ? (
        <>
          <h2>Archive</h2>
          <ul className="items">
            {all.map((d) => (
              <li key={d.slug}>
                <Link href={`/digest/${d.slug}`}>{d.slug}</Link>{" "}
                <span className="meta">
                  {weekLabel(d.week_start, d.week_end)} ·{" "}
                  {d.stats.items} {d.stats.items === 1 ? "item" : "items"}
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </main>
  );
}
