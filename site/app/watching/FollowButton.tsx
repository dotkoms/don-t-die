"use client";

import { useEffect, useState } from "react";
import {
  isFollowed,
  toggleFollow,
  type WatchKind,
} from "@/lib/watchlist";

/**
 * The follow button (M6): plain toggle, state in the visitor's browser.
 * Renders "Follow" server-side, then settles to the browser's truth on
 * mount — no server round trip ever happens.
 */
export function FollowButton({ kind, slug }: { kind: WatchKind; slug: string }) {
  const [following, setFollowing] = useState<boolean | null>(null);

  useEffect(() => {
    setFollowing(isFollowed(kind, slug));
  }, [kind, slug]);

  const onClick = () => {
    toggleFollow(kind, slug);
    setFollowing(isFollowed(kind, slug));
  };

  return (
    <button
      type="button"
      className="follow"
      aria-pressed={following ?? undefined}
      onClick={onClick}
    >
      {following === null ? "Follow" : following ? "Following — click to stop" : "Follow"}
    </button>
  );
}
