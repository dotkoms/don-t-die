-- Retraction Watch flags (integrity pass, not a source): columns the
-- integrity pass recomputes from the Crossref Retraction Watch CSV by
-- matching DOI / PubMed id. Source truth stays in raw; these are derived
-- but deterministic (no model involved), so real columns are fine.

ALTER TABLE items
    ADD COLUMN is_retracted      boolean NOT NULL DEFAULT false,
    ADD COLUMN retraction_nature text,
    ADD COLUMN retraction_reason text,
    ADD COLUMN retraction_date   text,
    ADD COLUMN retraction_url    text;
