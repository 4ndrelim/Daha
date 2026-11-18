"use client";

import Link from "next/link";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Home, Loader2, LocateFixed, MapPin, ShoppingBag, Store } from "lucide-react";
import { api, ApiError, track } from "@/lib/api";
import type { CommercialOffer, CommercialSearchBody } from "@/lib/api/types";
import { useMe } from "@/lib/queries/me";
import { canUseDeviceLocation, roughDeviceLocation, useNearChoice, type NearChoice } from "@/lib/near";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const TYPE_LABEL: Record<CommercialOffer["offer_type"], string | null> = { buy: null, rent: "Rent", service: "Service" };

/**
 * "Buy or rent nearby" (C6): store and rental alternatives for a search, cheapest first.
 * Opens by itself when campus has little (`auto`); otherwise it waits behind a button.
 */
export function BuyNearby({ q, auto }: { q: string; auto: boolean }) {
  const [opened, setOpened] = useState(false);
  const open = auto || opened;
  const [choice, choose] = useNearChoice();
  const [picking, setPicking] = useState(false);
  const me = useMe();
  const dormName = me.data?.dorm?.name ?? null;

  const result = useQuery({
    queryKey: ["commercial", q, choice],
    enabled: open && q.trim().length > 0,
    staleTime: 10 * 60_000,
    retry: false,
    queryFn: async () => {
      const body: CommercialSearchBody = { q };
      if (choice.mode === "place") body.place = choice.place;
      let noLocation = false;
      if (choice.mode === "device") {
        try {
          Object.assign(body, await roughDeviceLocation());
        } catch {
          noLocation = true; // refused or unavailable: the server falls back to the dorm
        }
      }
      return { ...(await api.search.commercial(body)), noLocation };
    },
  });

  // One event per answer (no free text: counts and kinds only).
  const tracked = useRef("");
  useEffect(() => {
    const data = result.data;
    if (!data) return;
    const key = `${q}|${JSON.stringify(choice)}`;
    if (tracked.current === key) return;
    tracked.current = key;
    track("commercial_search_shown", {
      auto, results: data.offers.length, provider: data.provider, near: data.near_source, cached: data.cached,
    });
  });

  const status = result.error instanceof ApiError ? result.error.status : null;
  // Not set up or switched off on this server: when it opened by itself, stay out of the way.
  if (auto && status === 503) return null;

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpened(true)}
        className="flex h-12 w-full items-center justify-center gap-2 rounded-full bg-card font-semibold ring-1 ring-border active:bg-muted"
      >
        <ShoppingBag className="size-4" /> Compare store prices nearby
      </button>
    );
  }

  const data = result.data;
  const nearLabel = data?.near ?? (choice.mode === "place" ? choice.place : choice.mode === "device" ? "your location" : dormName ?? "your dorm");

  return (
    <section aria-labelledby="buy-nearby-title" className="space-y-3 rounded-2xl bg-card p-4 shadow-sm ring-1 ring-border/60">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 id="buy-nearby-title" className="text-[17px] font-semibold">
            {auto ? "Can't wait? Buy or rent nearby" : "Buy or rent nearby"}
          </h2>
          <p className="text-[13px] text-muted-foreground">Store and rental prices, cheapest first</p>
        </div>
        {data?.provider === "mock" && (
          <span className="shrink-0 rounded-full bg-points-soft px-2 py-0.5 text-[12px] font-semibold">Sample data</span>
        )}
      </div>

      <button
        type="button"
        onClick={() => setPicking(true)}
        className="flex h-11 max-w-full items-center gap-1.5 rounded-full bg-muted px-3.5 text-[14px] font-semibold active:bg-muted/70"
      >
        <MapPin className="size-4 shrink-0" />
        <span className="truncate">Near {nearLabel}</span>
        <span className="shrink-0 text-muted-foreground">· Change</span>
      </button>

      {result.isPending && result.fetchStatus !== "idle" && (
        <div aria-live="polite" className="space-y-3">
          <p className="flex items-center gap-2 text-[13px] text-muted-foreground">
            <Loader2 className="size-4 animate-spin" /> Checking stores near {nearLabel}…
          </p>
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex items-center gap-3">
              <Skeleton className="size-14 rounded-xl" />
              <div className="flex-1 space-y-2"><Skeleton className="h-4 w-1/3" /><Skeleton className="h-4 w-3/4" /></div>
            </div>
          ))}
        </div>
      )}

      {data?.noLocation && (
        <p className="text-[13px] text-muted-foreground">
          Couldn&apos;t get your location, so these are near {data.near}.
        </p>
      )}

      {result.isError && (
        <div className="rounded-2xl bg-muted px-4 py-3 text-[14px]">
          <p>{result.error instanceof ApiError ? result.error.detail : "Store search didn't work."}</p>
          {(status === null || status >= 500) && status !== 503 && (
            <button type="button" onClick={() => result.refetch()} className="mt-2 h-11 rounded-full bg-card px-4 font-semibold ring-1 ring-border">
              Try again
            </button>
          )}
        </div>
      )}

      {data && data.offers.length === 0 && (
        <p className="rounded-2xl bg-muted px-4 py-3 text-[14px]">
          No store listings found near {data.near}. Try other words, or ask your dorm.
        </p>
      )}

      {data && data.offers.length > 0 && (
        <ul className="divide-y divide-border/60">
          {data.offers.map((offer, rank) => (
            <li key={`${offer.url}-${rank}`}>
              <OfferRow
                offer={offer}
                onOpen={() => track("commercial_offer_clicked", {
                  rank, offer_type: offer.offer_type, has_price: offer.price !== null, provider: data.provider,
                })}
              />
            </li>
          ))}
        </ul>
      )}

      <p className="text-[12px] leading-relaxed text-muted-foreground">
        Prices come from store websites and can change, so check before you go. Borrowing is free:{" "}
        <Link href={`/add/request?text=${encodeURIComponent(q)}`} className="font-semibold text-primary underline-offset-2 hover:underline">
          ask your dorm first
        </Link>
        .
      </p>

      <NearSheet
        open={picking}
        onOpenChange={setPicking}
        choice={choice}
        dormName={dormName}
        onChoose={(next) => { choose(next); setPicking(false); }}
      />
    </section>
  );
}

function OfferRow({ offer, onOpen }: { offer: CommercialOffer; onOpen: () => void }) {
  const [imageFailed, setImageFailed] = useState(false);
  const typeLabel = TYPE_LABEL[offer.offer_type];
  const safe = /^https?:\/\//i.test(offer.url);
  if (!safe) return null;
  return (
    <a
      href={offer.url}
      target="_blank"
      rel="noopener noreferrer nofollow"
      onClick={onOpen}
      className="flex min-h-16 items-center gap-3 py-2.5 active:bg-muted"
    >
      {offer.image_url && !imageFailed ? (
        // A store's product photo: plain <img> (no Next image proxy for arbitrary hosts), no referrer sent.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={offer.image_url}
          alt=""
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setImageFailed(true)}
          className="size-14 shrink-0 rounded-xl bg-muted object-cover"
        />
      ) : (
        <span className="flex size-14 shrink-0 items-center justify-center rounded-xl bg-muted text-muted-foreground" aria-hidden>
          <Store className="size-6" />
        </span>
      )}
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline gap-2">
          <span className="text-[17px] font-semibold">{offer.price_text ?? "See price"}</span>
          {typeLabel && (
            <span className="rounded-full bg-sky-50 px-2 py-0.5 text-[12px] font-semibold text-sky-700">{typeLabel}</span>
          )}
        </span>
        <span className="block truncate text-[15px]">{offer.title}</span>
        <span className="block truncate text-[13px] text-muted-foreground">
          {offer.seller}{offer.location ? ` · ${offer.location}` : ""}
        </span>
      </span>
      <ExternalLink className="size-4 shrink-0 text-muted-foreground" aria-hidden />
      <span className="sr-only">(opens the store&apos;s site)</span>
    </a>
  );
}

function NearSheet({ open, onOpenChange, choice, dormName, onChoose }: {
  open: boolean; onOpenChange: (open: boolean) => void; choice: NearChoice; dormName: string | null;
  onChoose: (choice: NearChoice) => void;
}) {
  const [draft, setDraft] = useState(choice.mode === "place" ? choice.place : "");
  const deviceOk = canUseDeviceLocation();
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="mx-auto max-h-[85dvh] max-w-md overflow-y-auto rounded-t-3xl pb-[calc(1rem+env(safe-area-inset-bottom))]">
        <SheetHeader>
          <SheetTitle className="text-[17px]">Where should we look?</SheetTitle>
          <SheetDescription>Only a rough area is shared with the store search, never your name or exact spot.</SheetDescription>
        </SheetHeader>
        <div className="space-y-2 px-4">
          <NearOption
            active={choice.mode === "dorm"}
            icon={<Home className="size-5" />}
            title={`Near ${dormName ?? "my dorm"}`}
            body="The default. No location permission needed."
            onClick={() => onChoose({ mode: "dorm" })}
          />
          {deviceOk && (
            <NearOption
              active={choice.mode === "device"}
              icon={<LocateFixed className="size-5" />}
              title="Near me right now"
              body="Your browser shares a rough location (about 1 km). Used for this search only, never saved."
              onClick={() => onChoose({ mode: "device" })}
            />
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const place = draft.trim();
              if (place) onChoose({ mode: "place", place });
            }}
            className={cn("space-y-2 rounded-2xl p-3 ring-1", choice.mode === "place" ? "bg-primary-soft ring-primary/40" : "ring-border")}
          >
            <label htmlFor="buy-near-place" className="block font-medium">Somewhere else</label>
            <div className="flex gap-2">
              <input
                id="buy-near-place"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                maxLength={60}
                autoComplete="address-level2"
                placeholder="Town or ZIP, e.g. Mountain View"
                className="h-12 min-w-0 flex-1 rounded-full bg-card px-4 text-base ring-1 ring-border outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              <button
                type="submit"
                disabled={!draft.trim()}
                className="h-12 shrink-0 rounded-full bg-primary px-5 font-semibold text-primary-foreground active:bg-primary-hover disabled:opacity-50"
              >
                Use
              </button>
            </div>
          </form>
        </div>
      </SheetContent>
    </Sheet>
  );
}

function NearOption({ active, icon, title, body, onClick }: {
  active: boolean; icon: ReactNode; title: string; body: string; onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "flex min-h-16 w-full items-center gap-3 rounded-2xl p-3 text-left ring-1",
        active ? "bg-primary-soft ring-primary/40" : "ring-border active:bg-muted",
      )}
    >
      <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-card ring-1 ring-border" aria-hidden>{icon}</span>
      <span className="min-w-0">
        <span className="block font-medium">{title}</span>
        <span className="block text-[13px] text-muted-foreground">{body}</span>
      </span>
    </button>
  );
}
