-- Multi-agent research notes (M2). The research agents' output is stored
-- like extractions: labeled with the model that wrote it, never merged with
-- source truth, and every attached source is one the verifier allowed
-- (whitelisted outlet or primary source).

CREATE TABLE research_notes (
    id          bigserial PRIMARY KEY,
    target      text NOT NULL,            -- research target, e.g. 'BPC-157'
    slug        text NOT NULL,
    summary     text NOT NULL,            -- the synthesized note (markdown)
    model       text NOT NULL,            -- e.g. 'claude-opus-5'
    status      text NOT NULL DEFAULT 'draft',   -- draft | published
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX research_notes_slug_key ON research_notes (slug);

CREATE TABLE research_note_sources (
    note_id     bigint NOT NULL REFERENCES research_notes(id) ON DELETE CASCADE,
    kind        text NOT NULL,            -- 'news' | 'primary' | 'trial'
    title       text NOT NULL,
    url         text NOT NULL,
    verified    boolean NOT NULL DEFAULT false,  -- passed the outlet allowlist
    PRIMARY KEY (note_id, url)
);
