"""Domain queries — one search expression per domain from the plan's domain map.

These are the recall queries; the relevance classifier (M1) narrows what lands
in the store. Each entry is (domain_slug, source query). Sources with plain
boolean search share _REGISTRY_TERMS (CT.gov, Europe PMC, ISRCTN); PubMed needs
its own field-tagged syntax; CTIS takes one term per query row (its full-text
search does not support boolean OR); DrugAge is a full-snapshot dataset, not a
search, so it has no queries here.
"""

# The peptide recall list — every compound circulating in the longevity space,
# broad on purpose: the relevance gate narrows to life-extension context and
# the rest stays in the corpus for auditability.
PEPTIDE_TERMS = (
    '"BPC-157" OR epitalon OR epithalon OR "MOTS-c" OR humanin OR "GHK-Cu" OR '
    '"mitochondrial-derived peptide" OR SHLP2 OR SHLP3 OR elamipretide OR '
    '"SS-31" OR tesamorelin OR ipamorelin OR "CJC-1295" OR semaglutide OR '
    'tirzepatide OR retatrutide OR orforglipron OR "GLP-1" OR '
    '"glucagon-like peptide" OR "growth hormone-releasing peptide" OR '
    'GHRP-6 OR GHRP-2 OR hexarelin OR "thymosin beta-4" OR "TB-500" OR '
    '"thymosin alpha-1" OR "AOD-9604" OR selank OR semax OR dihexa OR '
    'carnosine OR noopept OR "klotho-derived peptide" OR '
    # Gate v1.3 (2026-11-11): swept from current clinic/telehealth menus —
    # the most-prescribed peptides we had no term for, plus the newer GLP-1
    # family members in trials.
    'sermorelin OR ibutamoren OR "MK-677" OR "5-amino-1MQ" OR "ARA-290" OR '
    'cibinetide OR "FOXO4-DRI" OR "DSIP" OR cagrilintide OR mazdutide OR '
    'survodutide'
)

PUBMED_QUERIES = [
    ("geroscience", 'aging[MeSH Terms] AND ("hallmarks of aging" OR geroscience OR senescence[MeSH Terms] OR "mTOR" OR autophagy)'),
    ("senolytics", 'senolytic OR senescence AND (clearance OR "senolytics"[Title/Abstract])'),
    ("interventions-pharma", "rapamycin OR metformin OR \"NAD+\" OR nicotinamide OR senolytics OR spermidine OR acarbose OR fisetin OR berberine OR \"urolithin A\" OR GlyNAC"),
    ("rejuvenation", "reprogramming OR \"partial reprogramming\" OR rejuvenation OR \"plasma dilution\" OR \"yamanaka factors\""),
    ("biomarkers", "\"epigenetic clock\" OR \"DNA methylation age\" OR \"biological age\" OR \"aging biomarkers\""),
    ("longevity", "(longevity[Title] OR \"life extension\"[Title/Abstract] OR \"lifespan\"[Title/Abstract])"),
    ("diet-restriction", "(\"caloric restriction\" OR \"dietary restriction\") AND (aging OR lifespan OR longevity)"),
    ("clinical", '(aging OR longevity) AND ("clinical trial"[pt] OR "randomized"[Title/Abstract])'),
    ("peptides", PEPTIDE_TERMS.replace('"GLP-1" OR "glucagon-like peptide" OR',
                                       '"GLP-1"[Title/Abstract] OR "glucagon-like peptide"[Title/Abstract] OR')),
]

# Shared boolean recall terms for sources with plain OR/phrase search.
_REGISTRY_TERMS = [
    ("geroscience", 'aging OR geroscience OR "biological aging"'),
    ("senolytics", "senescence OR senolytic OR senescent"),
    ("interventions-pharma", "rapamycin OR metformin OR nicotinamide OR spermidine OR acarbose OR fisetin OR berberine OR \"urolithin A\" OR GlyNAC"),
    ("rejuvenation", 'reprogramming OR rejuvenation OR "plasma dilution" OR "young plasma"'),
    ("biomarkers", '"epigenetic clock" OR "biological age" OR "aging biomarker"'),
    ("longevity", 'longevity OR "life extension" OR lifespan'),
    ("peptides", PEPTIDE_TERMS),
]

CTGOV_QUERIES = _REGISTRY_TERMS

# Europe PMC: the registry set plus the literature-only domains.
EPMC_QUERIES = _REGISTRY_TERMS + [
    ("diet-restriction", '("caloric restriction" OR "dietary restriction") AND (aging OR lifespan OR longevity)'),
    ("clinical", '(aging OR longevity) AND ("clinical trial" OR randomized)'),
]

# ISRCTN's API speaks Lucene-style booleans, so the shared terms work as-is.
ISRCTN_QUERIES = _REGISTRY_TERMS

# CTIS full-text search takes one term per request (no boolean OR): each row is
# a separate query; several rows can share a domain.
CTIS_QUERIES = [
    ("geroscience", "aging"),
    ("geroscience", "geroscience"),
    ("senolytics", "senescence"),
    ("senolytics", "senolytic"),
    ("interventions-pharma", "rapamycin"),
    ("interventions-pharma", "metformin"),
    ("interventions-pharma", "spermidine"),
    ("rejuvenation", "rejuvenation"),
    ("biomarkers", "epigenetic clock"),
    ("biomarkers", "biological age"),
    ("longevity", "longevity"),
    ("longevity", "life extension"),
    ("peptides", "BPC-157"),
    ("peptides", "epitalon"),
    ("peptides", "MOTS-c"),
    ("peptides", "humanin"),
    ("peptides", "elamipretide"),
    ("peptides", "semaglutide"),
    ("peptides", "tirzepatide"),
    ("peptides", "retatrutide"),
    ("peptides", "GLP-1"),
    ("peptides", "tesamorelin"),
    ("peptides", "thymosin"),
    # Gate v1.3 (2026-11-11): the clinic-sweep compounds.
    ("peptides", "sermorelin"),
    ("peptides", "ibutamoren"),
    ("peptides", "ARA-290"),
    ("peptides", "cagrilintide"),
    ("interventions-pharma", "berberine"),
    ("interventions-pharma", "urolithin A"),
]

# NIH RePORTER full-text search takes the same OR/phrase syntax as the
# registry sources, so the shared recall terms work as-is. RePORTER has no
# date-added filter (verified: date_added criteria are silently ignored), so
# the adapter lands the current fiscal year per query each run.
REPORTER_QUERIES = _REGISTRY_TERMS

# EU CORDIS searches inside /project/objective with quoted OR clauses; terms
# without the objective field could not match. Multi-word phrases are quoted
# the same as single words.
CORDIS_QUERIES = [
    ("geroscience", ["aging", "geroscience", "biological aging"]),
    ("senolytics", ["senescence", "senolytic", "senescent"]),
    ("interventions-pharma",
     ["rapamycin", "metformin", "nicotinamide", "spermidine", "acarbose",
      "fisetin", "berberine", "urolithin A", "GlyNAC"]),
    ("rejuvenation",
     ["reprogramming", "rejuvenation", "plasma dilution", "young plasma"]),
    ("biomarkers", ["epigenetic clock", "biological age", "aging biomarker"]),
    ("longevity", ["longevity", "life extension", "lifespan"]),
    ("peptides",
     ["BPC-157", "epitalon", "MOTS-c", "humanin", "elamipretide",
      "semaglutide", "tirzepatide", "GLP-1", "tesamorelin", "ipamorelin",
      "thymosin", "sermorelin", "ibutamoren", "cagrilintide"]),
]

# UKRI GtR's search takes one term per request (like CTIS), so the CORDIS
# term lists are flattened. "ageing" is added alongside "aging" because GtR
# is a UK database and full-text search does not stem spellings.
GTR_QUERIES = [
    (domain, term)
    for domain, terms in CORDIS_QUERIES for term in terms
] + [("geroscience", "ageing")]
