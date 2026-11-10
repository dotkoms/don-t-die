import Link from "next/link";
import { listEntities } from "@/lib/entities";
import { EntityList } from "../entities/list";

export const dynamic = "force-dynamic";
export const metadata = { title: "Compounds — don't die" };

export default async function CompoundsPage() {
  const entities = await listEntities("compound");

  return (
    <main>
      <Link href="/" className="back">
        ← the domain map
      </Link>
      <h1>Compounds</h1>
      <p className="tagline">
        The intervention vocabulary this knowledge base tracks — rapamycin,
        metformin, the senolytics, the peptides, the GLP-1 family. A curated
        list, deliberately not the DrugAge compound column (which is full of
        generic chemistry): items link by mention, DrugAge rows by the compound
        they record. Rebuilt from the corpus on every pipeline run.
      </p>

      {entities === null ? (
        <p className="empty">
          The store is not connected (no <code>DATABASE_URL</code>). Run the
          pipeline first: <code>migrate</code>, then <code>fetch</code> +{" "}
          <code>load</code>, then <code>entities</code>.
        </p>
      ) : entities.length === 0 ? (
        <p className="empty">
          No compound entities yet — the pipeline has not built them against a
          loaded corpus. Run <code>python3 -m dontdie entities</code>.
        </p>
      ) : (
        <EntityList kind="compound" entities={entities} />
      )}
    </main>
  );
}
