/** The shape sourceLabel actually reads — every item-like row (Item,
 * WatchItem, …) satisfies it. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type SourceLike = { source: string; raw: Record<string, any> };

/**
 * One honest label per source kind — mirrors the pipeline's source tiers:
 * PubMed (journal), a primary registry (sponsor), a preprint (its server),
 * a curated dataset, or a tier-2 news outlet.
 */
export function sourceLabel(item: SourceLike): string {
  if (item.source === "pubmed") return item.raw.journal ?? "PubMed";
  if (item.source === "ctgov") return item.raw.sponsor ?? "ClinicalTrials.gov";
  if (item.source === "europemc") {
    return item.raw.preprint
      ? `${item.raw.preprint_server ?? "preprint"} · not peer reviewed`
      : (item.raw.journal ?? "Europe PMC");
  }
  if (item.source === "isrctn") return item.raw.sponsor ?? "ISRCTN Registry";
  if (item.source === "ctis") return item.raw.sponsor ?? "EU Clinical Trials";
  if (item.source === "drugage") return "DrugAge (HAGR)";
  if (item.source === "genage") return "GenAge (HAGR)";
  if (item.source === "cellage") return "CellAge (HAGR)";
  if (item.source === "anage") return "AnAge (HAGR)";
  if (item.source === "reporter")
    return item.raw.institution ?? "NIH RePORTER";
  if (item.source === "cordis")
    return item.raw.acronym || "EU CORDIS";
  if (item.source === "gtr")
    return item.raw.institution ?? "UKRI Gateway to Research";
  return item.raw.outlet ?? item.source; // tier-2 news outlet
}
