"use client";

import Link from "next/link";
import { useEffect, useEffectEvent, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useInfiniteQuery } from "@tanstack/react-query";
import { Loader2, Lock, Search, X } from "lucide-react";
import { api, track } from "@/lib/api";
import type { SearchQuery } from "@/lib/api/endpoints/search";
import type { Category, Condition, TransactionType } from "@/lib/api/types";
import { CATEGORIES } from "@/lib/categories";
import { BuyNearby } from "@/components/daha/buy-nearby";
import { CategoryChips } from "@/components/daha/category-chips";
import { FilterSheet, type Filters } from "@/components/daha/filter-sheet";
import { ItemCard } from "@/components/daha/item-card";
import { RequestCard } from "@/components/daha/request-card";
import { EmptyState, ErrorState, ItemGridSkeleton, RequestListSkeleton } from "@/components/daha/states";
import { cn } from "@/lib/utils";

/** The five demo queries (PLAN.md §10 step 7) rotate as the placeholder. */
const EXAMPLES = [
  "graphing calculator near me",
  "anyone have a vacuum in my dorm?",
  "formal clothes for an interview",
  "moving boxes available this weekend",
  "someone who can help repair my bike",
];

type Tab = "items" | "requests" | "communities";
const TABS: { value: Tab; label: string }[] = [
  { value: "items", label: "Items" },
  { value: "requests", label: "Requests" },
  { value: "communities", label: "Groups" },
];
const PAGE = 20;
/** At most this many campus items for a search → show store options right away (C6). */
const THIN_RESULTS = 2;

const CATEGORY_VALUES = new Set<string>(CATEGORIES.map((c) => c.value));
const TX_VALUES = new Set<string>(["lend", "give", "exchange"]);
const CONDITION_VALUES = new Set<string>(["new", "like_new", "good", "fair", "worn"]);

interface UrlState { q: string; category: Category | null; scope: "dorm" | null; tab: Tab; filters: Filters }

function readUrl(p: URLSearchParams): UrlState {
  const cat = p.get("category");
  const type = p.get("type");
  const cond = p.get("condition");
  const walk = Number(p.get("walk"));
  const tab = p.get("tab");
  return {
    q: p.get("q") ?? "",
    category: cat && CATEGORY_VALUES.has(cat) ? (cat as Category) : null,
    scope: p.get("scope") === "dorm" ? "dorm" : null,
    tab: tab === "requests" || tab === "communities" ? tab : "items",
    filters: {
      max_walk_min: walk > 0 ? walk : null,
      transaction_type: type && TX_VALUES.has(type) ? (type as TransactionType) : null,
      condition: cond && CONDITION_VALUES.has(cond) ? (cond as Condition) : null,
      available_only: p.get("all") !== "1",
    },
  };
}

function writeUrl(s: UrlState): string {
  const p = new URLSearchParams();
  if (s.q) p.set("q", s.q);
  if (s.category) p.set("category", s.category);
  if (s.scope) p.set("scope", s.scope);
  if (s.tab !== "items") p.set("tab", s.tab);
  if (s.filters.max_walk_min) p.set("walk", String(s.filters.max_walk_min));
  if (s.filters.transaction_type) p.set("type", s.filters.transaction_type);
  if (s.filters.condition) p.set("condition", s.filters.condition);
  if (!s.filters.available_only) p.set("all", "1");
  const str = p.toString();
  return str ? `?${str}` : "";
}

function useRotatingPlaceholder(active: boolean): string {
  const [i, setI] = useState(0);
  useEffect(() => {
    if (!active) return;
    const t = setInterval(() => setI((n) => (n + 1) % EXAMPLES.length), 3000);
    return () => clearInterval(t);
  }, [active]);
  return `Try "${EXAMPLES[i]}"`;
}

export function ExploreScreen() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const state = useMemo(() => readUrl(new URLSearchParams(params.toString())), [params]);
  const [text, setText] = useState(state.q);
  const placeholder = useRotatingPlaceholder(!text);

  const update = (patch: Partial<UrlState>) => router.replace(`${pathname}${writeUrl({ ...state, ...patch })}`, { scroll: false });

  // Typing updates the URL (and the search) after a short pause; Enter does it right away.
  const commitText = useEffectEvent((q: string) => update({ q }));
  useEffect(() => {
    if (text.trim() === state.q) return;
    const t = setTimeout(() => commitText(text.trim()), 450);
    return () => clearTimeout(t);
  }, [text, state.q]);

  const query: SearchQuery = {
    q: state.q || undefined,
    kind: state.tab,
    category: state.category ?? undefined,
    scope: state.scope ?? undefined,
    max_walk_min: state.filters.max_walk_min ?? undefined,
    transaction_type: state.filters.transaction_type ?? undefined,
    condition: state.filters.condition ?? undefined,
    available_only: state.filters.available_only,
    limit: PAGE,
  };

  const results = useInfiniteQuery({
    queryKey: ["search", query],
    queryFn: ({ pageParam }) => api.search.search({ ...query, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (last) => last.next_offset,
  });

  const first = results.data?.pages[0];
  const items = results.data?.pages.flatMap((p) => p.items) ?? [];
  const requests = results.data?.pages.flatMap((p) => p.requests) ?? [];
  const communities = first?.communities ?? [];
  const count = state.tab === "items" ? items.length : state.tab === "requests" ? requests.length : communities.length;

  // One search_performed event per finished search (not per page).
  const tracked = useRef("");
  useEffect(() => {
    if (!first) return;
    const key = JSON.stringify(query);
    if (tracked.current === key) return;
    tracked.current = key;
    track("search_performed", {
      q: state.q, tab: state.tab, category: state.category, scope: state.scope, result_count: count,
    });
  });

  const clickResult = (kind: string, id: number, rank: number) =>
    track("search_result_clicked", { q: state.q, kind, id, rank });

  const chips = first?.parsed.chips ?? [];

  return (
    <div className="space-y-3">
      <h1 className="sr-only">Explore</h1>
      <form
        role="search"
        onSubmit={(e) => { e.preventDefault(); update({ q: text.trim() }); (document.activeElement as HTMLElement | null)?.blur(); }}
        className="relative"
      >
        <Search className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-muted-foreground" />
        <input
          type="search"
          enterKeyHint="search"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={placeholder}
          aria-label="Search DAHA"
          className="h-12 w-full rounded-full bg-card pr-11 pl-11 text-base shadow-sm ring-1 ring-border outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-search-cancel-button]:hidden"
        />
        {text && (
          <button type="button" aria-label="Clear search" onClick={() => { setText(""); update({ q: "" }); }}
            className="absolute top-1/2 right-1.5 flex size-10 -translate-y-1/2 items-center justify-center rounded-full text-muted-foreground active:bg-muted">
            <X className="size-5" />
          </button>
        )}
      </form>

      <div className="flex items-center gap-2">
        <div className="flex h-12 rounded-full bg-muted p-1" role="group" aria-label="Where to look">
          {([["dorm", "My dorm"], [null, "Campus"]] as const).map(([v, label]) => (
            <button
              key={label}
              type="button"
              aria-pressed={state.scope === v}
              onClick={() => update({ scope: v })}
              className={cn("rounded-full px-3.5 text-[14px] font-semibold transition",
                state.scope === v ? "bg-card text-foreground shadow-sm" : "text-muted-foreground")}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="ml-auto">
          <FilterSheet value={state.filters} onApply={(filters) => update({ filters })} />
        </div>
      </div>

      <CategoryChips value={state.category} onChange={(category) => update({ category })} />

      {state.q && chips.length > 0 && (
        <p className="flex flex-wrap items-center gap-1.5 text-[13px] text-muted-foreground">
          Understood:
          {chips.map((c) => (
            <span key={c} className="rounded-full bg-primary-soft px-2 py-0.5 font-medium text-accent-foreground">{c}</span>
          ))}
        </p>
      )}

      <div className="flex gap-5 border-b border-border" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.value}
            type="button"
            role="tab"
            aria-selected={state.tab === t.value}
            onClick={() => update({ tab: t.value })}
            className={cn("-mb-px h-11 border-b-2 text-[15px] font-semibold transition",
              state.tab === t.value ? "border-primary text-foreground" : "border-transparent text-muted-foreground")}
          >
            {t.label}
          </button>
        ))}
      </div>

      {results.isPending && (state.tab === "items" ? <ItemGridSkeleton count={6} /> : <RequestListSkeleton />)}
      {results.isError && <ErrorState message="Search didn't work." onRetry={() => results.refetch()} />}

      {results.isSuccess && count === 0 && (
        state.tab === "communities" ? (
          <EmptyState emoji="👥" title="No groups match that" body="Start one from the Communities tab." actionLabel="Go to Communities" actionHref="/communities" />
        ) : (
          <EmptyState
            emoji="🙋"
            title={state.q ? "Nobody's listed that yet — ask your dorm?" : "Nothing here yet"}
            body={state.q ? "Post it as a request and we'll ping people who might have one." : "Try a different category or filter."}
            actionLabel={state.q ? "Ask for it" : undefined}
            actionHref={state.q ? `/add/request?text=${encodeURIComponent(state.q)}` : undefined}
          />
        )
      )}

      {state.tab === "items" && items.length > 0 && (
        <div className="grid grid-cols-2 gap-3">
          {items.map((i, rank) => <ItemCard key={i.id} item={i} onClick={() => clickResult("item", i.id, rank)} />)}
        </div>
      )}

      {/* Buy or rent nearby: opens by itself when campus has little, else a button (C6). */}
      {state.tab === "items" && state.q && results.isSuccess && (
        <BuyNearby key={state.q} q={state.q} auto={items.length <= THIN_RESULTS} />
      )}

      {state.tab === "requests" && requests.length > 0 && (
        <div className="space-y-4" onClickCapture={(e) => {
          const id = (e.target as HTMLElement).closest("[data-request-id]")?.getAttribute("data-request-id");
          if (id) clickResult("request", Number(id), requests.findIndex((r) => r.id === Number(id)));
        }}>
          {requests.map((r) => <div key={r.id} data-request-id={r.id}><RequestCard request={r} /></div>)}
        </div>
      )}

      {state.tab === "communities" && communities.length > 0 && (
        <div className="space-y-2">
          {communities.map((c, rank) => (
            <Link
              key={c.id}
              href={`/communities/${c.slug}`}
              onClick={() => clickResult("community", c.id, rank)}
              className="flex min-h-16 items-center gap-3 rounded-2xl bg-card px-4 py-3 shadow-sm ring-1 ring-border/60 active:bg-muted"
            >
              <span className="text-2xl" aria-hidden>{c.emoji ?? "👥"}</span>
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-1.5 font-medium">
                  <span className="truncate">{c.name}</span>
                  {c.is_private && <Lock className="size-3.5 shrink-0 text-muted-foreground" aria-label="Private" />}
                </span>
                <span className="block text-[13px] text-muted-foreground">
                  {c.member_count} {c.member_count === 1 ? "member" : "members"} · {c.item_count} things
                  {c.is_member ? " · Joined" : ""}
                </span>
              </span>
            </Link>
          ))}
        </div>
      )}

      {results.hasNextPage && state.tab !== "communities" && (
        <button
          type="button"
          onClick={() => results.fetchNextPage()}
          disabled={results.isFetchingNextPage}
          className="flex h-12 w-full items-center justify-center gap-2 rounded-full bg-card font-semibold ring-1 ring-border active:bg-muted disabled:opacity-60"
        >
          {results.isFetchingNextPage && <Loader2 className="size-4 animate-spin" />} Load more
        </button>
      )}
    </div>
  );
}
