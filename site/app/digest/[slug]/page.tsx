import Link from "next/link";
import { notFound } from "next/navigation";
import { getDigest, getDigestItems, weekLabel } from "@/lib/digest";
import { IssueView } from "../issue";

export const dynamic = "force-dynamic";

export default async function IssuePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const digest = await getDigest(slug);
  if (!digest) notFound();
  const items = (await getDigestItems(slug)) ?? [];

  return (
    <main>
      <Link href="/digest" className="back">
        ← the weekly digest
      </Link>
      <h1>Issue {digest.slug}</h1>
      <IssueView digest={digest} items={items} />
      <p className="meta">
        Week of {weekLabel(digest.week_start, digest.week_end)} ·{" "}
        <Link href="/digest">all issues</Link>
      </p>
    </main>
  );
}
