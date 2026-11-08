export type Item = {
  slug: string;
  source: string;
  source_id: string;
  title: string;
  url: string;
  published: string | null;
  is_relevant: boolean;
  relevance_terms: string[];
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
  };
};
