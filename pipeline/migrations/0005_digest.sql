-- Weekly digest issues (M3). The digest is deterministic — a recompute
-- over the corpus, like the retraction flags, never hand-edited — so these
-- are derived tables, safe to rebuild on every pipeline run.

CREATE TABLE digests (
    id         bigserial PRIMARY KEY,
    slug       text NOT NULL UNIQUE,        -- '2026-w45' (ISO week, Mon–Sun)
    week_start date NOT NULL,               -- Monday
    week_end   date NOT NULL,               -- Sunday
    built_at   timestamptz NOT NULL DEFAULT now(),
    stats      jsonb NOT NULL DEFAULT '{}'::jsonb  -- counts by category + per-domain sections
);

CREATE TABLE digest_items (
    digest_id bigint NOT NULL REFERENCES digests(id) ON DELETE CASCADE,
    item_id   bigint NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    rank      int NOT NULL,                 -- editorial rank across the issue
    section   text NOT NULL,                -- domain slug ('senolytics', ...)
    PRIMARY KEY (digest_id, item_id)
);

CREATE INDEX digest_items_order_idx ON digest_items (digest_id, section, rank);
