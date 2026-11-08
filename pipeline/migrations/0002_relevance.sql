-- Relevance gate output lives in real columns so public views can filter
-- on it and the gate stays auditable (method column names the version).

ALTER TABLE items
    ADD COLUMN is_relevant     boolean NOT NULL DEFAULT false,
    ADD COLUMN relevance_terms jsonb   NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN relevance_method text    NOT NULL DEFAULT '';
