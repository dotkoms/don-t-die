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
  is_retracted?: boolean;
  retraction_nature?: string | null;
  retraction_reason?: string | null;
  retraction_date?: string | null;
  retraction_url?: string | null;
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
    // Grants / funded projects (NIH RePORTER, EU CORDIS).
    agency?: string;
    award_amount?: number;
    award_type?: string;
    fiscal_year?: number;
    project_num?: string;
    institution?: string;
    org_city?: string;
    org_state?: string;
    pi_names?: string[];
    project_start_date?: string;
    project_end_date?: string;
    is_active?: boolean;
    acronym?: string;
    end_date?: string;
    total_cost?: string | number;
    ec_contribution?: string | number;
    // UKRI GtR grants (award_amount is GBP — formatted as £).
    grant_reference?: string;
    grant_category?: string;
    research_topics?: string[];
    // GenAge aging genes + CellAge senescence genes (HAGR, CC BY 3.0).
    gene_symbol?: string;
    gene_name?: string;
    entrez_id?: string;
    uniprot?: string;
    evidence?: string;
    dataset?: string;
    organism?: string;
    lifespan_effect?: string;
    longevity_influence?: string;
    cancer_cell?: string;
    senescence_type?: string;
    senescence_effect?: string;
    // AnAge species longevity records.
    common_name?: string;
    taxon_class?: string;
    taxon_order?: string;
    taxon_family?: string;
    max_longevity_years?: string;
    adult_weight_g?: string;
    specimen_origin?: string;
    data_quality?: string;
  };
};
