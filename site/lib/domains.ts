/**
 * The domain map, mirroring pipeline/dontdie/queries.py slugs — the pipeline
 * owns the domains; this mirrors them for routing (decision 3).
 */
export const DOMAINS: { slug: string; name: string; blurb: string }[] = [
  {
    slug: "geroscience",
    name: "Geroscience",
    blurb: "Aging biology: senescence, mTOR, autophagy, hallmarks of aging.",
  },
  {
    slug: "senolytics",
    name: "Senolytics",
    blurb: "Clearing senescent cells and what that buys.",
  },
  {
    slug: "interventions-pharma",
    name: "Pharmacological interventions",
    blurb: "Rapamycin, metformin, NAD+ precursors, senolytics, spermidine.",
  },
  {
    slug: "rejuvenation",
    name: "Rejuvenation biotech",
    blurb: "Partial reprogramming, plasma dilution, thymus regeneration.",
  },
  {
    slug: "biomarkers",
    name: "Biomarkers",
    blurb: "Epigenetic clocks, biological age, functional biomarkers.",
  },
  {
    slug: "longevity",
    name: "Longevity",
    blurb: "Lifespan and life-extension evidence across the field.",
  },
  {
    slug: "diet-restriction",
    name: "Diet & restriction",
    blurb: "Caloric restriction, fasting protocols and their outcomes.",
  },
  {
    slug: "clinical",
    name: "Clinical evidence",
    blurb: "Trials, endpoints and the move of aging into the clinic.",
  },
  {
    slug: "peptides",
    name: "Peptides",
    blurb:
      "Longevity-circulating peptides: BPC-157, epitalon, MOTS-c, humanin, elamipretide, GLP-1 agonists.",
  },
  {
    slug: "lifespan-data",
    name: "Lifespan experiments",
    blurb:
      "Curated lifespan data: DrugAge compound assays and AnAge species longevity records.",
  },
  {
    slug: "genetics-data",
    name: "Longevity genetics",
    blurb:
      "Curated gene datasets: GenAge aging genes and CellAge cellular senescence genes (HAGR).",
  },
];

export function domainName(slug: string): string {
  return DOMAINS.find((d) => d.slug === slug)?.name ?? slug;
}
