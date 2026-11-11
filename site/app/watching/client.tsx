"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  readWatchlist,
  watchlistParams,
  writeWatchlist,
  type Watchlist,
} from "@/lib/watchlist";

/**
 * On a bare /watching, hand the browser's watchlist to the server page as
 * URL params — the whole server boundary stays plain read-only queries.
 * A URL that already carries params wins: shared links stay pinned to
 * what was shared, and never silently rewrite the visitor's own list.
 */
export function WatchingSync({ hasParams }: { hasParams: boolean }) {
  const router = useRouter();
  const done = useRef(false);

  useEffect(() => {
    if (done.current) return;
    done.current = true;
    if (hasParams) return;
    const list = readWatchlist();
    const followed =
      list.domains.length + list.compounds.length +
      list.orgs.length + list.trials.length;
    if (followed > 0) router.replace(watchlistParams(list));
  }, [hasParams, router]);

  return null;
}

/**
 * Export / import / clear — the portability the empty state promises.
 * All in-browser: export downloads the JSON, import merges it into what
 * is already there, nothing touches the network.
 */
export function WatchlistTools() {
  const router = useRouter();
  const [count, setCount] = useState<number | null>(null);

  useEffect(() => {
    const l = readWatchlist();
    setCount(l.domains.length + l.compounds.length +
             l.orgs.length + l.trials.length);
  }, []);

  const exportList = () => {
    const blob = new Blob([JSON.stringify(readWatchlist(), null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "dont-die-watchlist.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const importList = async (file: File) => {
    try {
      const parsed = JSON.parse(await file.text()) as Partial<Watchlist>;
      const current = readWatchlist();
      const merged: Watchlist = {
        version: 1,
        domains: [...new Set([...current.domains, ...(parsed.domains ?? [])])],
        compounds: [...new Set([...current.compounds, ...(parsed.compounds ?? [])])],
        orgs: [...new Set([...current.orgs, ...(parsed.orgs ?? [])])],
        trials: [...new Set([...current.trials, ...(parsed.trials ?? [])])],
      };
      writeWatchlist(merged);
      router.replace(watchlistParams(merged));
      router.refresh();
    } catch {
      // a bad file: refuse quietly — the list is untouched
    }
  };

  const clearAll = () => {
    writeWatchlist({ version: 1, domains: [], compounds: [], orgs: [], trials: [] });
    router.replace("/watching");
    router.refresh();
  };

  return (
    <>
      <p className="meta">
        This browser&apos;s watchlist holds {count ?? "…"}{" "}
        {count === 1 ? "thing" : "things"} — it is stored here only, never
        on the server (a shared /watching link shows the sharer&apos;s
        selection without adding it to yours). Export to move devices;
        import merges, never overwrites.
      </p>
      <p className="watch-tools">
        <button type="button" className="follow" onClick={exportList}>
          Export
        </button>{" "}
        <label className="follow watch-import">
          Import
          <input
            type="file"
            accept="application/json"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void importList(f);
            }}
          />
        </label>{" "}
        <button type="button" className="follow" onClick={clearAll}>
          Stop watching everything
        </button>
      </p>
    </>
  );
}
