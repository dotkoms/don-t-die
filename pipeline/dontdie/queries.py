"""Domain queries — one search expression per domain from the plan's domain map.

These are the recall queries; the relevance classifier (M1) narrows what lands
in the store. Each entry is (domain_slug, source query).
"""

PUBMED_QUERIES = [
    ("geroscience", 'aging[MeSH Terms] AND ("hallmarks of aging" OR geroscience OR senescence[MeSH Terms] OR "mTOR" OR autophagy)'),
    ("senolytics", 'senolytic OR senescence AND (clearance OR "senolytics"[Title/Abstract])'),
    ("interventions-pharma", "rapamycin OR metformin OR \"NAD+\" OR nicotinamide OR senolytics OR spermidine OR acarbose OR fisetin"),
    ("rejuvenation", "reprogramming OR \"partial reprogramming\" OR rejuvenation OR \"plasma dilution\" OR \"yamanaka factors\""),
    ("biomarkers", "\"epigenetic clock\" OR \"DNA methylation age\" OR \"biological age\" OR \"aging biomarkers\""),
    ("longevity", "(longevity[Title] OR \"life extension\"[Title/Abstract] OR \"lifespan\"[Title/Abstract])"),
    ("diet-restriction", "(\"caloric restriction\" OR \"dietary restriction\") AND (aging OR lifespan OR longevity)"),
    ("clinical", "(aging OR longevity) AND (\"clinical trial\"[pt] OR \"randomized\"[Title/Abstract])"),
]

CTGOV_QUERIES = [
    ("geroscience", "aging OR geroscience OR \"biological aging\""),
    ("senolytics", "senescence OR senolytic OR senescent"),
    ("interventions-pharma", "rapamycin OR metformin OR nicotinamide OR spermidine OR acarbose OR fisetin"),
    ("rejuvenation", "reprogramming OR rejuvenation OR \"plasma dilution\" OR \"young plasma\""),
    ("biomarkers", "\"epigenetic clock\" OR \"biological age\" OR \"aging biomarker\""),
    ("longevity", "longevity OR \"life extension\" OR lifespan"),
]
