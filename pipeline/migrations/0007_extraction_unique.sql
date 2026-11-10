-- Extraction uniqueness (M5): one extraction per (item, field). Idempotent
-- writes (ON CONFLICT upsert), and a model bump rewrites in place instead of
-- accumulating stale rows. The table has been empty until now, so no
-- deduplication is needed before the index.

CREATE UNIQUE INDEX extractions_item_field_key ON extractions (item_id, field);
