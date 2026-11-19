"use client";

import Link from "next/link";
import { Camera, ChevronRight, HandHeart, Sparkles } from "lucide-react";
import type { FulfillableRequest, HomeFeed } from "@/lib/api/types";
import { useHomeFeed } from "@/lib/queries/feed";
import { useMe } from "@/lib/queries/me";
import { firstName } from "@/lib/format";
import { formatUsd, VALUE_EXCHANGE } from "@/lib/value";
import { ItemCard } from "@/components/daha/item-card";
import { ItemThumb } from "@/components/daha/item-thumb";
import { MutualMatches } from "@/components/daha/mutual-matches";
import { RequestCard } from "@/components/daha/request-card";
import { UserAvatar } from "@/components/daha/user-avatar";
import { EmptyState, ErrorState, ItemGridSkeleton, RequestListSkeleton, SectionHeader } from "@/components/daha/states";
import { Skeleton } from "@/components/ui/skeleton";

function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Hey" : "Good evening";
}

function ScanCard() {
  return (
    <Link
      href="/add/scan"
      className="relative block overflow-hidden rounded-3xl bg-gradient-to-br from-brand-500 via-brand-600 to-brand-deep p-5 text-white shadow-lg shadow-brand-600/20 active:scale-[0.99]"
    >
      <span aria-hidden className="absolute -top-6 -right-4 text-[96px] opacity-20 select-none">📸</span>
      <p className="text-[13px] font-semibold tracking-wide text-brand-100 uppercase">Start here</p>
      <p className="mt-1 text-[22px] leading-7 font-semibold">Show us what you have</p>
      <p className="mt-1 max-w-[16rem] text-brand-50">Snap your desk, we&apos;ll list it. You pick what to share.</p>
      <span className="mt-4 inline-flex h-11 items-center gap-2 rounded-full bg-white px-5 font-semibold text-brand-700">
        <Camera className="size-5" /> Snap your desk
      </span>
    </Link>
  );
}

function ScanBanner() {
  return (
    <Link href="/add/scan" className="flex min-h-14 items-center gap-3 rounded-2xl bg-primary-soft px-4 py-2.5 active:bg-brand-100">
      <span className="flex size-9 items-center justify-center rounded-full bg-primary text-primary-foreground"><Camera className="size-[18px]" /></span>
      <span className="flex-1 text-[15px]"><span className="font-semibold">Snap more stuff</span><span className="text-muted-foreground"> · we&apos;ll list it for you</span></span>
      <ChevronRight className="size-5 text-accent-foreground" />
    </Link>
  );
}

function HelpCard({ f }: { f: FulfillableRequest }) {
  const item = f.my_matching_items[0];
  return (
    <div className="flex w-[17rem] shrink-0 snap-start flex-col rounded-2xl bg-card p-3.5 shadow-sm ring-1 ring-border/60">
      <div className="flex items-center gap-2 text-[13px]">
        <UserAvatar user={f.request.requester} className="size-6" />
        <span className="shrink-0 font-semibold">{firstName(f.request.requester.name)}</span>
        <span className="min-w-0 truncate text-muted-foreground">· {f.request.requester.dorm_name ?? f.request.community_label}</span>
      </div>
      <Link href={`/requests/${f.request.id}`} className="mt-2 line-clamp-2 min-h-10 text-[15px] leading-5">&ldquo;{f.request.raw_text}&rdquo;</Link>
      {item && (
        <div className="mt-3 flex items-center gap-2.5 rounded-xl bg-muted p-2">
          <ItemThumb url={item.thumbnail_url} category={item.category} className="size-10 shrink-0 rounded-lg" emojiClassName="text-xl" />
          <span className="min-w-0 flex-1">
            <span className="block text-[12px] text-muted-foreground">You have</span>
            <span className="block truncate text-[14px] font-medium">{item.name}</span>
          </span>
        </div>
      )}
      <Link
        href={`/requests/${f.request.id}?help=1${item ? `&offer_item=${item.id}` : ""}`}
        className="mt-3 flex h-11 items-center justify-center rounded-full bg-primary font-semibold text-primary-foreground active:bg-primary-hover"
      >
        Offer it
      </Link>
    </div>
  );
}

function Stats({ feed }: { feed: HomeFeed }) {
  const name = feed.dorm?.name.split(" (")[0];
  const shared = feed.stats.dorm_value_shared_month_usd;
  return (
    <>
      <p className="flex items-center gap-1.5 text-[13px] text-muted-foreground">
        <Sparkles className="size-3.5 text-points" />
        {name ? `${name} has ${feed.stats.dorm_items} things to share` : `${feed.stats.campus_items} things to share on campus`}
        {` · ${feed.stats.open_requests} open asks`}
      </p>
      {/* Value exchange: an estimate from completed exchanges this month. */}
      {VALUE_EXCHANGE && name && shared != null && shared > 0 && (
        <p className="mt-0.5 flex items-center gap-1.5 text-[13px] text-muted-foreground">
          <HandHeart className="size-3.5 text-points" aria-hidden />
          {name} shared about {formatUsd(shared)} this month <span className="sr-only">(an estimate)</span>
        </p>
      )}
    </>
  );
}

export default function HomePage() {
  const { data: me } = useMe();
  const feed = useHomeFeed();

  return (
    <div className="space-y-7">
      <div>
        <h1 className="text-[22px] leading-7 font-semibold">
          {greeting()}{me ? `, ${firstName(me.name)}` : ""} 👋
        </h1>
        {feed.data ? <Stats feed={feed.data} /> : <Skeleton className="mt-1.5 h-4 w-56" />}
      </div>

      {feed.isError && <ErrorState message="Couldn't load your feed." onRetry={() => feed.refetch()} />}

      {feed.data && (feed.data.show_scan_cta ? <ScanCard /> : <ScanBanner />)}

      {/* Pairs where each has something the other needs; hidden when the server has it off. */}
      <MutualMatches />

      {feed.data && feed.data.you_can_help.length > 0 && (
        <section>
          <SectionHeader title="You could help" />
          <div className="no-scrollbar -mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-1">
            {feed.data.you_can_help.map((f) => <HelpCard key={f.request.id} f={f} />)}
          </div>
        </section>
      )}

      <section>
        <SectionHeader
          title="Requests near you"
          action={<Link href="/add/request" className="-my-2 inline-flex min-h-11 items-center text-[13px] font-semibold text-primary">Ask for something</Link>}
        />
        {feed.isPending && <RequestListSkeleton />}
        {feed.data && feed.data.requests_nearby.length === 0 && (
          <EmptyState emoji="🙋" title="No open asks nearby" body="Need something? Your dorm might have it." actionLabel="Ask your dorm" actionHref="/add/request" />
        )}
        <div className="space-y-4">
          {feed.data?.requests_nearby.slice(0, 5).map((r) => <RequestCard key={r.id} request={r} />)}
        </div>
      </section>

      <section>
        <SectionHeader title="New near you" action={<Link href="/explore" className="-my-2 inline-flex min-h-11 items-center px-1 text-[13px] font-semibold text-primary">See all</Link>} />
        {feed.isPending && <ItemGridSkeleton />}
        {feed.data && feed.data.new_nearby.length === 0 && (
          <EmptyState emoji="📦" title="Nothing shared nearby yet" body="Be the first. Snap your desk and we'll list it." actionLabel="Snap your stuff" actionHref="/add/scan" />
        )}
        <div className="grid grid-cols-2 gap-3">
          {feed.data?.new_nearby.map((i) => <ItemCard key={i.id} item={i} />)}
        </div>
      </section>
    </div>
  );
}
