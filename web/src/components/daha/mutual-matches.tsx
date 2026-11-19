"use client";

// "You two can help each other" (docs/plans/mutual-matching.md): pairs where each person has
// something the other needs. The server only returns pairs where BOTH people turned this on.
// Hidden completely when the server has the feature off (the query returns null).

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeftRight, Sparkles } from "lucide-react";
import { api, track } from "@/lib/api";
import type { MutualLink, MutualMatch, MutualMatchesResponse } from "@/lib/api/types";
import { useMutualMatches } from "@/lib/queries/feed";
import { meKey } from "@/lib/queries/me";
import { firstName } from "@/lib/format";
import { ItemThumb } from "@/components/daha/item-thumb";
import { UserAvatar } from "@/components/daha/user-avatar";
import { SectionHeader } from "@/components/daha/states";
import { cn } from "@/lib/utils";

const HIDE_KEY = "daha_mutual_invite_hidden";

function useOptIn() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (enabled: boolean) => api.me.update({ match_suggestions: enabled }),
    onSuccess: (me, enabled) => {
      qc.setQueryData(meKey, me);
      qc.invalidateQueries({ queryKey: ["feed", "mutual"] });
      track("match_suggestions_changed", { enabled });
    },
  });
}

/** Asked once, never pre-ticked: matching looks at what you list, ask for and search. */
function Invite() {
  const optIn = useOptIn();
  const [hidden, setHidden] = useState(() => {
    try {
      return window.localStorage.getItem(HIDE_KEY) === "1";
    } catch {
      return false;
    }
  });
  if (hidden) return null;
  return (
    <section className="rounded-2xl bg-card p-4 shadow-sm ring-1 ring-border/60">
      <p className="flex items-center gap-2 text-[17px] font-semibold">
        <ArrowLeftRight className="size-5 text-primary" /> Trade favors with neighbors
      </p>
      <p className="mt-1 text-[14px] text-muted-foreground">
        Get matched with people who have what you need and need what you have. DAHA looks at what you list, ask for
        and search. Only people who also turned this on are matched, and you can turn it off anytime.
      </p>
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          disabled={optIn.isPending}
          onClick={() => optIn.mutate(true)}
          className="h-11 flex-1 rounded-full bg-primary font-semibold text-primary-foreground active:bg-primary-hover disabled:opacity-60"
        >
          Turn on
        </button>
        <button
          type="button"
          onClick={() => {
            setHidden(true);
            try {
              window.localStorage.setItem(HIDE_KEY, "1");
            } catch {
              // fine: it will just ask again next time
            }
          }}
          className="h-11 rounded-full px-4 font-semibold text-muted-foreground ring-1 ring-border active:bg-muted"
        >
          Not now
        </button>
      </div>
      {optIn.isError && <p className="mt-2 text-[13px] text-destructive">Couldn&apos;t turn it on. Try again.</p>}
    </section>
  );
}

function LinkRow({ label, link }: { label: string; link: MutualLink }) {
  return (
    <Link href={`/items/${link.item.id}`} className="flex items-center gap-2.5 rounded-xl bg-muted p-2 active:bg-muted/70">
      <ItemThumb url={link.item.thumbnail_url} category={link.item.category} className="size-10 shrink-0 rounded-lg" emojiClassName="text-xl" />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[12px] text-muted-foreground">{label}</span>
        <span className="block truncate text-[14px] font-medium">{link.item.name}</span>
      </span>
    </Link>
  );
}

function PairCard({ match, rank, wide }: { match: MutualMatch; rank: number; wide: boolean }) {
  const give = match.you_give[0];
  const get = match.you_get[0];
  if (!give || !get) return null;
  const them = firstName(match.user.name);
  const giveLabel = give.need.kind === "request" ? `${them} asked for ${give.need.name} · you have` : `${them} might need ${give.need.name} · you have`;
  const getLabel = get.need.kind === "request" ? `You asked for ${get.need.name} · ${them} has` : `You might need ${get.need.name} · ${them} has`;
  const request = give.need.request;
  const clicked = (action: string) => track("mutual_match_clicked", { rank, action, uses_prediction: match.uses_prediction });
  return (
    <div className={cn("flex shrink-0 snap-start flex-col rounded-2xl bg-card p-3.5 shadow-sm ring-1 ring-border/60", wide ? "w-full" : "w-[18.5rem]")}>
      <Link href={`/u/${match.user.id}`} className="flex items-center gap-2 text-[13px]" onClick={() => clicked("profile")}>
        <UserAvatar user={match.user} className="size-6" />
        <span className="shrink-0 font-semibold">You and {them}</span>
        <span className="min-w-0 truncate text-muted-foreground">· {match.user.dorm_name ?? "on campus"}</span>
      </Link>
      <div className="mt-2.5 space-y-2">
        <LinkRow label={giveLabel} link={give} />
        <LinkRow label={getLabel} link={get} />
      </div>
      <p className="mt-2 flex items-center gap-1 truncate text-[12px] text-muted-foreground">
        {match.uses_prediction && <Sparkles className="size-3.5 shrink-0 text-points" />}
        <span className="truncate">{match.reason}</span>
      </p>
      <div className="mt-3 flex gap-2">
        {request ? (
          <Link
            href={`/requests/${request.id}?help=1&offer_item=${give.item.id}`}
            onClick={() => clicked("offer")}
            className="flex h-11 flex-1 items-center justify-center rounded-full bg-primary font-semibold text-primary-foreground active:bg-primary-hover"
          >
            Offer yours
          </Link>
        ) : null}
        <Link
          href={`/items/${get.item.id}`}
          onClick={() => clicked("borrow")}
          className={
            request
              ? "flex h-11 flex-1 items-center justify-center rounded-full font-semibold ring-1 ring-border active:bg-muted"
              : "flex h-11 flex-1 items-center justify-center rounded-full bg-primary font-semibold text-primary-foreground active:bg-primary-hover"
          }
        >
          Ask for theirs
        </Link>
      </div>
    </div>
  );
}

/** One line of what the profile agent noticed, always worded as a guess. Shown only to the person it is about. */
function Noticed({ data }: { data: MutualMatchesResponse }) {
  if (!data.summary && data.likely_needs.length === 0) return null;
  return (
    <div className="mt-3 rounded-2xl bg-points-soft px-3.5 py-2.5 text-[13px]">
      <p className="flex items-start gap-1.5">
        <Sparkles className="mt-0.5 size-3.5 shrink-0 text-points" />
        <span>
          {data.summary ?? "Based on what you list, ask for and search."}
          {data.likely_needs.length > 0 && (
            <>
              {" "}You might need:{" "}
              {data.likely_needs.slice(0, 3).map((need, i) => (
                <span key={need}>
                  {i > 0 && ", "}
                  <Link href={`/explore?q=${encodeURIComponent(need)}`} className="font-semibold text-primary underline-offset-2 hover:underline">
                    {need}
                  </Link>
                </span>
              ))}
              .
            </>
          )}
        </span>
      </p>
      <p className="mt-1 text-[12px] text-muted-foreground">A guess from your own activity. Only you see this.</p>
    </div>
  );
}

export function MutualMatches() {
  const result = useMutualMatches();
  const optIn = useOptIn();
  const data = result.data;

  // One event per answer (counts and kinds only).
  const tracked = useRef(false);
  useEffect(() => {
    if (!data?.enabled || tracked.current) return;
    tracked.current = true;
    track("mutual_match_shown", { count: data.matches.length, uses_prediction: data.matches.some((m) => m.uses_prediction) });
  }, [data]);

  if (!data) return null; // loading, an error, or switched off on this server: stay out of the way
  if (!data.enabled) return <Invite />;
  if (data.matches.length === 0 && !data.summary && data.likely_needs.length === 0) return null;

  return (
    <section>
      <SectionHeader
        title={data.matches.length > 0 ? "You two can help each other" : "Matched for you"}
        action={
          <button
            type="button"
            disabled={optIn.isPending}
            onClick={() => optIn.mutate(false)}
            className="-my-2 inline-flex min-h-11 items-center px-1 text-[13px] font-semibold text-muted-foreground"
          >
            Turn off
          </button>
        }
      />
      {data.matches.length > 0 && (
        <div className="no-scrollbar -mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-1">
          {data.matches.slice(0, 3).map((m, rank) => (
            <PairCard key={m.user.id} match={m} rank={rank} wide={data.matches.length === 1} />
          ))}
        </div>
      )}
      <Noticed data={data} />
    </section>
  );
}
