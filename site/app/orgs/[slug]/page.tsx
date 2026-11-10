import Link from "next/link";
import { notFound } from "next/navigation";
import { getEntity, getEntityItems } from "@/lib/entities";
import { EntityDetail } from "../../entities/detail";

export const dynamic = "force-dynamic";

export default async function OrgPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const entity = await getEntity("org", slug);
  if (!entity) notFound();
  const items = await getEntityItems("org", slug);

  return (
    <main>
      <Link href="/" className="back">
        ← the domain map
      </Link>
      <EntityDetail entity={entity} items={items ?? []} />
    </main>
  );
}
