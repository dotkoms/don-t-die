import Link from "next/link";
import { listEntities } from "@/lib/entities";
import { EntityList } from "../entities/list";

export const dynamic = "force-dynamic";
export const metadata = { title: "Organizations — don't die" };

export default async function OrgsPage() {
  const entities = await listEntities("org");

  return (
    <main>
      <Link href="/" className="back">
        ← the domain map
      </Link>
      <h1>Organizations</h1>
      <p className="tagline">
        Funded institutions (NIH RePORTER, UKRI GtR) and trial sponsors
        (ClinicalTrials.gov, ISRCTN, EU CTIS) — who the money flows to and who
        runs the trials. Name variants collapse to one page; the display name
        prefers a properly-cased form over the grant registries&apos; ALL CAPS.
      </p>

      {entities === null ? (
        <p className="empty">
          The store is not connected (no <code>DATABASE_URL</code>). Run the
          pipeline first: <code>migrate</code>, then <code>fetch</code> +{" "}
          <code>load</code>, then <code>entities</code>.
        </p>
      ) : entities.length === 0 ? (
        <p className="empty">
          No organization entities yet — the pipeline has not built them
          against a loaded corpus. Run{" "}
          <code>python3 -m dontdie entities</code>.
        </p>
      ) : (
        <EntityList kind="org" entities={entities} />
      )}
    </main>
  );
}
