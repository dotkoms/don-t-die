/**
 * The watchlist (M6, decision 15): an anonymous follow list that lives in
 * the visitor's browser and never reaches the server — localStorage only,
 * so the production site role stays read-only and no visitor data is
 * collected. Export/import is the portability story (and the honesty
 * story: the empty states say where the data lives).
 */

export type WatchKind = "domain" | "compound" | "org" | "trial";

export type Watchlist = {
  version: 1;
  domains: string[];
  compounds: string[];
  orgs: string[];
  trials: string[];
};

const KEY = "dont-die-watchlist";

const EMPTY: Watchlist = {
  version: 1,
  domains: [],
  compounds: [],
  orgs: [],
  trials: [],
};

// localStorage can throw (private window, blocked storage, full quota) —
// every read/write is guarded; the list degrades to empty, never breaks.
export function readWatchlist(): Watchlist {
  if (typeof window === "undefined") return EMPTY;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return EMPTY;
    const parsed = JSON.parse(raw) as Partial<Watchlist>;
    // Merge over EMPTY so a future shape change never crashes old browsers.
    return {
      version: 1,
      domains: Array.isArray(parsed.domains) ? parsed.domains : [],
      compounds: Array.isArray(parsed.compounds) ? parsed.compounds : [],
      orgs: Array.isArray(parsed.orgs) ? parsed.orgs : [],
      trials: Array.isArray(parsed.trials) ? parsed.trials : [],
    };
  } catch {
    return EMPTY;
  }
}

export function writeWatchlist(list: Watchlist): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(list));
  } catch {
    // blocked storage: the follow button just won't stick; never crash
  }
}

const ARRAY_KEYS = {
  domain: "domains",
  compound: "compounds",
  org: "orgs",
  trial: "trials",
} as const;

function arrayKey(
  kind: WatchKind,
): "domains" | "compounds" | "orgs" | "trials" {
  return ARRAY_KEYS[kind];
}

export function isFollowed(kind: WatchKind, slug: string): boolean {
  return readWatchlist()[arrayKey(kind)].includes(slug);
}

export function toggleFollow(kind: WatchKind, slug: string): Watchlist {
  const list = readWatchlist();
  const key = arrayKey(kind);
  const current = list[key];
  list[key] = current.includes(slug)
    ? current.filter((s) => s !== slug)
    : [...current, slug];
  writeWatchlist(list);
  return list;
}

/** /watching state as URL search params — the server page stays plain
 * read-only queries; the URL is the whole handoff. */
export function watchlistParams(list: Watchlist): string {
  const params = new URLSearchParams();
  if (list.domains.length) params.set("d", list.domains.join(","));
  if (list.compounds.length) params.set("c", list.compounds.join(","));
  if (list.orgs.length) params.set("o", list.orgs.join(","));
  if (list.trials.length) params.set("t", list.trials.join(","));
  const qs = params.toString();
  return qs ? `/watching?${qs}` : "/watching";
}
