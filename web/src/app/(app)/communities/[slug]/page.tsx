"use client";

import Link from "next/link";
import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Loader2, Lock, Send, UserPlus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Community, FeedEntry, ItemCard as ItemCardT } from "@/lib/api/types";
import { categoryInfo } from "@/lib/categories";
import { firstName, plural, timeAgo } from "@/lib/format";
import { copyInvite, inviteUrl } from "@/lib/invite";
import { useJoin, useLeave } from "@/lib/queries/communities";
import { useMe } from "@/lib/queries/me";
import { ItemCard } from "@/components/daha/item-card";
import { ItemThumb } from "@/components/daha/item-thumb";
import { RequestCard } from "@/components/daha/request-card";
import { UserAvatar } from "@/components/daha/user-avatar";
import { EmptyState, ErrorState, ItemGridSkeleton, RequestListSkeleton } from "@/components/daha/states";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

type Tab = "channel" | "inventory" | "requests" | "members";
const TABS: { value: Tab; label: string }[] = [
  { value: "channel", label: "Channel" }, { value: "inventory", label: "Inventory" },
  { value: "requests", label: "Requests" }, { value: "members", label: "Members" },
];

function SharedCard({ item }: { item: ItemCardT }) {
  return (
    <div className="flex gap-2.5">
      <UserAvatar user={item.owner} className="mt-0.5 size-9 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="text-[13px]">
          <span className="font-semibold">{firstName(item.owner.name)}</span>
          <span className="text-muted-foreground"> shared </span>
          <span className="font-medium">{item.name.charAt(0).toLowerCase() + item.name.slice(1)}</span>
          <span className="text-muted-foreground"> · {timeAgo(item.created_at)}</span>
        </p>
        <Link href={`/items/${item.id}`} className="mt-1 flex items-center gap-3 rounded-2xl bg-card p-2 pr-3 ring-1 ring-border/60 active:bg-muted">
          <ItemThumb url={item.thumbnail_url} category={item.category} className="size-12 shrink-0 rounded-xl" emojiClassName="text-2xl" />
          <span className="min-w-0 flex-1">
            <span className="block truncate font-medium">{item.name}</span>
            <span className="block text-[12px] text-muted-foreground">{categoryInfo(item.category).label} · {item.transaction_type === "lend" ? "Lend" : item.transaction_type === "give" ? "Free" : "Swap"}</span>
          </span>
        </Link>
      </div>
    </div>
  );
}

function Feed({ c, tab }: { c: Community; tab: "channel" | "inventory" | "requests" }) {
  const kind = tab === "channel" ? "all" : tab === "inventory" ? "items" : "requests";
  const feed = useInfiniteQuery({
    queryKey: ["community-feed", c.id, kind],
    queryFn: ({ pageParam }) => api.feed.community(c.id, { kind, offset: pageParam, limit: 20 }),
    initialPageParam: 0,
    getNextPageParam: (last) => last.next_offset,
    refetchInterval: tab === "channel" ? 15_000 : false,
  });
  const entries: FeedEntry[] = feed.data?.pages.flatMap((p) => p.items) ?? [];

  if (feed.isPending) return tab === "inventory" ? <ItemGridSkeleton /> : <RequestListSkeleton count={4} />;
  if (feed.isError) {
    return feed.error instanceof ApiError && feed.error.status === 404
      ? <EmptyState emoji="🔒" title="Members only" body="Join to see what people here are sharing." />
      : <ErrorState onRetry={() => feed.refetch()} />;
  }
  if (entries.length === 0) {
    return tab === "inventory"
      ? <EmptyState emoji="📦" title="Nothing shared here yet" body="Be the first. Snap your desk and we'll list it." actionLabel="Snap your stuff" actionHref="/add/scan" />
      : <EmptyState emoji="🙋" title="No asks yet" body={`Need something? Ask ${c.name}.`} actionLabel="Ask for something" actionHref={`/add/request?community=${c.id}`} />;
  }
  const more = feed.hasNextPage && (
    <button type="button" onClick={() => feed.fetchNextPage()} disabled={feed.isFetchingNextPage}
      className="mt-4 flex h-12 w-full items-center justify-center gap-2 rounded-full bg-card font-semibold ring-1 ring-border active:bg-muted">
      {feed.isFetchingNextPage && <Loader2 className="size-4 animate-spin" />} Load more
    </button>
  );
  if (tab === "inventory") {
    return <><div className="grid grid-cols-2 gap-3">{entries.flatMap((e) => (e.kind === "item" ? [<ItemCard key={e.item.id} item={e.item} />] : []))}</div>{more}</>;
  }
  return (
    <>
      <div className="space-y-5">
        {entries.map((e) => (e.kind === "request"
          ? <RequestCard key={`r${e.request.id}`} request={e.request} />
          : <SharedCard key={`i${e.item.id}`} item={e.item} />))}
      </div>
      {more}
    </>
  );
}

function Members({ c }: { c: Community }) {
  const members = useInfiniteQuery({
    queryKey: ["members", c.id],
    queryFn: ({ pageParam }) => api.communities.members(c.id, { offset: pageParam, limit: 30 }),
    initialPageParam: 0,
    getNextPageParam: (last) => last.next_offset,
  });
  if (members.isPending) return <div className="space-y-2">{Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-14 rounded-2xl" />)}</div>;
  if (members.isError) {
    return members.error instanceof ApiError && members.error.status === 404
      ? <EmptyState emoji="🔒" title="Members only" body="Who's in a private group stays private." />
      : <ErrorState onRetry={() => members.refetch()} />;
  }
  const list = members.data.pages.flatMap((p) => p.items);
  return (
    <div className="space-y-1">
      {list.map((u) => (
        <Link key={u.id} href={`/u/${u.id}`} className="flex min-h-14 items-center gap-3 rounded-2xl px-2 active:bg-muted">
          <UserAvatar user={u} className="size-10" />
          <span className="min-w-0 flex-1">
            <span className="block truncate font-medium">{u.name}</span>
            <span className="block truncate text-[13px] text-muted-foreground">{u.level_name}{u.dorm_name && c.kind !== "dorm" ? ` · ${u.dorm_name}` : ""}</span>
          </span>
          {u.rating_avg !== null && <span className="text-[13px] text-muted-foreground">★ {u.rating_avg.toFixed(1)}</span>}
        </Link>
      ))}
      {members.hasNextPage && (
        <button type="button" onClick={() => members.fetchNextPage()} className="h-12 w-full rounded-full font-semibold ring-1 ring-border">Load more</button>
      )}
    </div>
  );
}

export default function CommunityPage() {
  const { slug } = useParams<{ slug: string }>();
  const router = useRouter();
  const { data: me } = useMe();
  const community = useQuery({ queryKey: ["community", slug], queryFn: () => api.communities.get(slug) });
  const [tab, setTab] = useState<Tab>("channel");
  const [ask, setAsk] = useState("");
  const join = useJoin();
  const leave = useLeave();

  if (community.isPending) return <div className="space-y-3"><Skeleton className="h-24 rounded-3xl" /><Skeleton className="h-10" /><RequestListSkeleton /></div>;
  if (community.isError) {
    return community.error instanceof ApiError && community.error.status === 404
      ? <EmptyState emoji="🔍" title="No community here" actionLabel="Browse communities" actionHref="/communities" />
      : <ErrorState onRetry={() => community.refetch()} />;
  }
  const c = community.data;
  const canLeave = c.is_member && c.kind === "group";
  const short = c.name.split(" (")[0];

  return (
    <div className={cn("space-y-4", c.is_member && "pb-20")}>
      <header className="rounded-3xl bg-card p-4 shadow-sm ring-1 ring-border/60">
        <div className="flex items-start gap-3">
          <span className="flex size-14 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-3xl" aria-hidden>{c.emoji ?? "👥"}</span>
          <div className="min-w-0 flex-1">
            <h1 className="flex items-center gap-1.5 text-[20px] leading-6 font-semibold">
              <span className="truncate">{c.name}</span>{c.is_private && <Lock className="size-4 shrink-0 text-muted-foreground" aria-label="Private" />}
            </h1>
            <p className="mt-0.5 text-[13px] text-muted-foreground">
              {plural(c.member_count, "member")} · {plural(c.item_count, "thing")} · {plural(c.open_request_count, "open ask")}
              {c.distance_min !== null && c.kind === "dorm" && me?.dorm?.id !== c.id ? ` · ${c.distance_min} min walk` : ""}
            </p>
          </div>
        </div>
        {c.description && <p className="mt-3 text-[14px]">{c.description}</p>}
        {c.join_code && (
          <p className="mt-3 rounded-xl bg-muted px-3 py-2 text-[13px]">Join code (only admins see this): <span className="font-mono font-bold tracking-widest select-all">{c.join_code}</span></p>
        )}
        <div className="mt-3 flex gap-2">
          {!c.is_member && (
            c.is_private
              ? <Link href="/communities" className="flex h-11 flex-1 items-center justify-center rounded-full bg-primary font-semibold text-primary-foreground">Join with a code</Link>
              : <button type="button" disabled={join.isPending} onClick={() => join.mutate({ id: c.id })}
                  className="h-11 flex-1 rounded-full bg-primary font-semibold text-primary-foreground disabled:opacity-60">
                  {c.kind === "dorm" ? "Move to this dorm" : "Join"}
                </button>
          )}
          {c.is_member && me && c.kind !== "campus" && (
            <button type="button" onClick={() => copyInvite(inviteUrl(c, me.id), c.kind)}
              className="flex h-11 flex-1 items-center justify-center gap-1.5 rounded-full bg-primary-soft font-semibold text-accent-foreground">
              <UserPlus className="size-4" /> Invite
            </button>
          )}
          {canLeave && (
            <button type="button" disabled={leave.isPending} onClick={() => leave.mutate(c, { onSuccess: () => router.refresh() })}
              className="h-11 rounded-full px-5 font-semibold text-muted-foreground ring-1 ring-border active:bg-muted">
              Leave
            </button>
          )}
        </div>
      </header>

      <div className="sticky top-[calc(3.5rem+env(safe-area-inset-top))] z-10 -mx-4 flex gap-5 overflow-x-auto border-b border-border bg-background/95 px-4 backdrop-blur" role="tablist">
        {TABS.map((t) => (
          <button key={t.value} type="button" role="tab" aria-selected={tab === t.value} onClick={() => setTab(t.value)}
            className={cn("-mb-px h-11 shrink-0 border-b-2 text-[15px] font-semibold",
              tab === t.value ? "border-primary text-foreground" : "border-transparent text-muted-foreground")}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "members" ? <Members c={c} /> : <Feed c={c} tab={tab} />}

      {c.is_member && (
        <form
          onSubmit={(e) => { e.preventDefault(); router.push(`/add/request?community=${c.id}${ask.trim() ? `&text=${encodeURIComponent(ask.trim())}` : ""}`); }}
          className="fixed inset-x-0 bottom-[calc(5.5rem+env(safe-area-inset-bottom))] z-20"
        >
          <div className="mx-auto flex max-w-md gap-2 px-4">
            <input value={ask} onChange={(e) => setAsk(e.target.value)} placeholder={`Ask ${short} for something…`} aria-label={`Ask ${short} for something`}
              className="h-12 min-w-0 flex-1 rounded-full bg-card px-4 text-base shadow-lg ring-1 ring-border outline-none focus-visible:ring-2 focus-visible:ring-ring" />
            <button type="submit" aria-label="Ask" className="flex size-12 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg shadow-primary/30">
              <Send className="size-5" />
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
