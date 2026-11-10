import Link from "next/link";
import { listEntities } from "@/lib/entities";
import { EntityList } from "../entities/list";

export const dynamic = "force-dynamic";
export const metadata = { title: "Trials — don't die" };

export default async function TrialsPage() {
  const entities = await listEntities("trial");

  return (
    <main>
      <Link href="/" className="back">
        ← the domain map
      </Link>
      <h1>Trials</h1>
      <p className="tagline">
        Every relevant registry record in the corpus — ClinicalTrials.gov,
        ISRCTN, EU CTIS — with the corpus items that cite them. The registry
        record is the primary evidence; each trial page links to it and to
        anything in the corpus that references its registry id.
      </p>

      {entities === null ? (
        <p className="empty">
          The store is not connected (no <code>DATABASE_URL</code>). Run the
          pipeline first: <code>migrate</code>, then <code>fetch</code> +{" "}
          <code>load</code>, then <code>entities</code>.
        </p>
      ) : entities.length === 0 ? (
        <p className="empty">
          No trial entities yet — the pipeline has not built them against a
          loaded corpus. Run <code>python3 -m dontdie entities</code>.
        </p>
      ) : (
        <EntityList kind="trial" entities={entities} />
      )}
    </main>
  );
}
