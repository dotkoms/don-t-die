-- Entity pages (M4): compounds, organizations, trials — the digest's link
-- destinations. Like the digest and retraction flags, entities are derived
-- deterministically from source-truth fields (never an LLM — extraction is
-- M5 and will live separately in `extractions`), so both tables are safe to
-- rebuild on every pipeline run.

CREATE TABLE entities (
    id         bigserial PRIMARY KEY,
    kind       text NOT NULL,                -- 'compound' | 'org' | 'trial'
    slug       text NOT NULL,                -- 'rapamycin', 'mayo-clinic', 'nct04006321'
    name       text NOT NULL,                -- display name
    data       jsonb NOT NULL DEFAULT '{}'::jsonb,  -- family / registry / link counts
    built_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (kind, slug)
);

CREATE TABLE item_entities (
    item_id    bigint NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    entity_id  bigint NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    how        text NOT NULL DEFAULT 'mention', -- 'assay' | 'record' | 'citation' | 'funding' | 'sponsor' | 'mention'
    PRIMARY KEY (item_id, entity_id)
);

CREATE INDEX item_entities_entity_idx ON item_entities (entity_id);
CREATE INDEX entities_kind_idx ON entities (kind);
