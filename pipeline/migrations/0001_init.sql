-- don-t-die initial schema (foundation; applied to Postgres in M1).
-- The pipeline owns migrations; site/ TS types mirror them.

CREATE TABLE sources (
    slug        text PRIMARY KEY,          -- 'pubmed', 'ctgov', ...
    name        text NOT NULL,
    url         text NOT NULL,
    tier        int  NOT NULL              -- 1 primary, 2 derived/community, 3 excluded
);

CREATE TABLE items (
    id          bigserial PRIMARY KEY,
    source      text NOT NULL REFERENCES sources(slug),
    source_id   text NOT NULL,             -- PMID, NCT id, ...
    slug        text NOT NULL,             -- stable public id, e.g. 'pubmed-40123456'
    url         text NOT NULL,
    title       text NOT NULL,
    published   date,
    fetched_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    raw         jsonb NOT NULL,            -- verbatim normalized landing record
    UNIQUE (source, source_id)
);

CREATE UNIQUE INDEX items_slug_key ON items (slug);

CREATE TABLE item_domains (
    item_id     bigint NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    domain      text NOT NULL,             -- domain-map slug ('senolytics', ...)
    is_primary  boolean NOT NULL DEFAULT true,
    PRIMARY KEY (item_id, domain)
);

-- LLM-extracted fields are stored separately and labeled, never merged into
-- items (honesty principle). A field here is an extraction, not source truth.
CREATE TABLE extractions (
    id          bigserial PRIMARY KEY,
    item_id     bigint NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    field       text NOT NULL,             -- 'compound', 'outcome', 'model_organism', ...
    value       jsonb NOT NULL,
    model       text NOT NULL,             -- e.g. 'claude-haiku-4-5'
    extracted_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE fetch_log (
    id          bigserial PRIMARY KEY,
    fetched_at  timestamptz NOT NULL DEFAULT now(),
    source      text NOT NULL,
    summary     jsonb NOT NULL            -- per-query counts, errors
);
