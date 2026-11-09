import type { Item } from "./types";

/**
 * One honest label per source kind — mirrors the pipeline's source tiers:
 * PubMed (journal), ClinicalTrials.gov (sponsor), or a tier-2 news outlet.
 */
export function sourceLabel(item: Item): string {
  if (item.source === "pubmed") return item.raw.journal ?? "PubMed";
  if (item.source === "ctgov") return item.raw.sponsor ?? "ClinicalTrials.gov";
  return item.raw.outlet ?? item.source; // tier-2 news outlet
}
