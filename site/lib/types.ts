export type Item = {
  slug: string;
  source: string;
  source_id: string;
  title: string;
  url: string;
  published: string | null;
  is_relevant: boolean;
  relevance_terms: string[];
  relevance_method?: string;
  raw: {
    authors?: string[];
    journal?: string;
    doi?: string;
    abstract?: string;
    sponsor?: string;
    status?: string;
    phases?: string[];
    conditions?: string[];
    interventions?: string[];
    start_date?: string;
    completion_date?: string;
    last_update?: string;
    brief_summary?: string;
    domain_query?: string;
    // News items (tier-2 outlets): the outlet's own summary and name.
    summary?: string;
    outlet?: string;
    // Europe PMC: preprint flag (SRC:PPR) and server label (10.1101 = bioRxiv/medRxiv).
    preprint?: boolean;
    preprint_server?: string;
    // DrugAge lifespan assays (tier-2 curated dataset, CC BY 3.0).
    compound?: string;
    species?: string;
    strain?: string;
    dosage?: string;
    gender?: string;
    itp?: string;
    avg_lifespan_change_percent?: string;
    max_lifespan_change_percent?: string;
    avg_lifespan_significance?: string;
    max_lifespan_significance?: string;
    pubmed_id?: string;
    // Registry records (ISRCTN / EU CTIS / ClinicalTrials.gov).
    official_title?: string;
    enrollment?: string | number;
    study_type?: string;
    study_design?: string;
    sponsor_type?: string;
    countries?: string[];
    age_group?: string;
    registration_date?: string;
    decision_date?: string;
  };
};
