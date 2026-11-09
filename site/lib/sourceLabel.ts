import type { Item } from "./types";

/**
 * One honest label per source kind — mirrors the pipeline's source tiers:
 * PubMed (journal), a primary registry (sponsor), a preprint (its server),
 * a curated dataset, or a tier-2 news outlet.
 */
export function sourceLabel(item: Item): string {
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
  if (item.source === "reporter")
    return item.raw.institution ?? "NIH RePORTER";
  if (item.source === "cordis")
    return item.raw.acronym || "EU CORDIS";
  return item.raw.outlet ?? item.source; // tier-2 news outlet
}
