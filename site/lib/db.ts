import { Pool } from "pg";

/**
 * Read-only Postgres access for the site.
 *
 * The pipeline owns the schema and writes through its own connection; this
 * module only ever SELECTs. When DATABASE_URL is unset (local first run,
 * build-time) the pool is null and callers render an honest empty state
 * instead of guessing a database.
 */
export type Row = Record<string, unknown>;

let pool: Pool | null = null;

export function getPool(): Pool | null {
  if (pool) return pool;
  if (!process.env.DATABASE_URL) return null;
  pool = new Pool({
    connectionString: process.env.DATABASE_URL,
    max: 5,
    // The site never writes; a read-only role in production enforces it.
  });
  return pool;
}

export async function query<RowT = Row>(
  sql: string,
  params: readonly unknown[] = [],
): Promise<RowT[] | null> {
  const p = getPool();
  if (!p) return null;
  const { rows } = await p.query(sql, params as never[]);
  return rows as RowT[];
}
