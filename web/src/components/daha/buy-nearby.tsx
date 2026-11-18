"use client";

import Link from "next/link";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink, GraduationCap, Loader2, LocateFixed, MapPin, ShoppingBag, Store } from "lucide-react";
import { api, ApiError, track } from "@/lib/api";
import type { CommercialOffer, CommercialSearchBody } from "@/lib/api/types";
import {
  canUseDeviceLocation, forgetLocationFailure, locationPermission, NoDeviceLocation, roughDeviceLocation, useNearChoice,
  type NearChoice,
} from "@/lib/near";
import { MapPickerSheet } from "@/components/daha/map-picker";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const TYPE_LABEL: Record<CommercialOffer["offer_type"], string | null> = { buy: null, rent: "Rent", service: "Service" };

const WHY_LOCATION = "To show stores near you. Rough location only, never saved.";

/**
 * What happened with the phone's location for this answer (plans/LOCATION.md §4):
 * `used` (sent, rounded to ~1 km) · `can_ask` (not asked yet and nobody tapped, so we didn't prompt) ·
 * `blocked` (denied, off, or too slow) · `none` (plain http, or the person picked campus or a place).
 */
type LocationUse = "used" | "can_ask" | "blocked" | "none";

/**
 * "Buy or rent nearby" (C6): store and rental alternatives for a search, cheapest first.
 * Opens by itself when campus has little (`auto`); otherwise it waits behind a button.
 */
export function BuyNearby({ q, auto }: { q: string; auto: boolean }) {
  const [opened, setOpened] = useState(false);
  const open = auto || opened;
  // How the panel opened: by itself (thin campus results) or by a tap. We only ever show the
  // browser's location prompt right after a tap, never when the panel opens by itself.
  const openedBy: "tap" | "auto" = opened ? "tap" : "auto";
  const [choice, choose] = useNearChoice();
  const [picking, setPicking] = useState(false);
  const [howTo, setHowTo] = useState(false);
  const [mapOpen, setMapOpen] = useState(false);
  const [mapKey, setMapKey] = useState(0); // a fresh map (starting at the current pin) each time it opens
  // Counts taps on "Use my location" / "Try again": each one may show the browser's prompt.
  const [asked, setAsked] = useState(0);
  const permissionTracked = useRef(false);

  const result = useQuery({
    queryKey: ["commercial", q, choice, openedBy, asked],
    enabled: open && q.trim().length > 0,
    staleTime: 10 * 60_000,
    retry: false,
    queryFn: async () => {
      const body: CommercialSearchBody = { q };
      let location: LocationUse = "none";
      if (choice.mode === "place") body.place = choice.place;
      if (choice.mode === "pin") Object.assign(body, { lat: choice.lat, lng: choice.lng, pinned: true });
      if (choice.mode === "auto") {
        const state = await locationPermission();
        if (!permissionTracked.current) {
          permissionTracked.current = true;
          track("location_permission", { state, opened_by: openedBy }); // kinds only, never coordinates
        }
        const mayPrompt = openedBy === "tap" || asked > 0;
        if (state === "granted" || (state === "prompt" && mayPrompt)) {
          try {
            Object.assign(body, await roughDeviceLocation()); // rounded to ~1 km in the browser
            location = "used";
          } catch (err) {
            location = "blocked"; // refused, off, or slower than 5 s: the server uses campus
            // Answered the prompt after we stopped waiting: refresh once with the location.
            if (err instanceof NoDeviceLocation) void err.late?.then(() => setAsked((n) => n + 1), () => undefined);
          }
        } else if (state === "prompt") {
          location = "can_ask";
        } else if (state === "denied") {
          location = "blocked";
        }
      }
      return { ...(await api.search.commercial(body)), location };
    },
  });

  // One event per answer (no free text: counts and kinds only).
  const tracked = useRef("");
  useEffect(() => {
    const data = result.data;
    if (!data) return;
    const key = `${q}|${JSON.stringify(choice)}|${asked}`;
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
  // "Near you" · "Near Stanford campus" · "Near <place>". Before the answer, `auto` isn't known yet.
  const nearLabel = data
    ? data.near_source === "device" ? "you" : data.near
    : choice.mode === "place" ? choice.place : choice.mode === "campus" ? "Stanford campus"
    : choice.mode === "pin" ? "the pin" : null;
  const openMap = () => {
    setPicking(false);
    setMapKey((k) => k + 1);
    setMapOpen(true);
  };
  const askForLocation = () => {
    forgetLocationFailure();
    if (choice.mode !== "auto") choose({ mode: "auto" });
    setAsked((n) => n + 1);
  };

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
        <span className="truncate">{nearLabel ? `Near ${nearLabel}` : "Nearby"}</span>
        <span className="shrink-0 text-muted-foreground">· Change</span>
      </button>

      {result.isPending && result.fetchStatus !== "idle" && (
        <div aria-live="polite" className="space-y-3">
          <p className="flex items-center gap-2 text-[13px] text-muted-foreground">
            <Loader2 className="size-4 animate-spin" /> {nearLabel ? `Checking stores near ${nearLabel}…` : "Checking stores nearby…"}
          </p>
          {choice.mode === "auto" && (openedBy === "tap" || asked > 0) && canUseDeviceLocation() && (
            <p className="text-[13px] text-muted-foreground">{WHY_LOCATION}</p>
          )}
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex items-center gap-3">
              <Skeleton className="size-14 rounded-xl" />
              <div className="flex-1 space-y-2"><Skeleton className="h-4 w-1/3" /><Skeleton className="h-4 w-3/4" /></div>
            </div>
          ))}
        </div>
      )}

      {data?.location === "can_ask" && (
        <div className="space-y-1">
          <button
            type="button"
            onClick={askForLocation}
            className="flex h-11 items-center gap-1.5 rounded-full bg-primary-soft px-3.5 text-[14px] font-semibold ring-1 ring-primary/40 active:bg-primary-soft/70"
          >
            <span aria-hidden>📍</span> Use my location
          </button>
          <p className="text-[13px] text-muted-foreground">{WHY_LOCATION}</p>
        </div>
      )}

      {data?.location === "blocked" && (
        <div className="space-y-1">
          <p className="text-[13px] text-muted-foreground">
            Couldn&apos;t use your location, so these are near {data.near}.
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setHowTo(true)}
              className="flex h-11 items-center gap-1.5 rounded-full bg-card px-3.5 text-[14px] font-semibold ring-1 ring-border active:bg-muted"
            >
              <LocateFixed className="size-4" /> Turn on location
            </button>
            <button
              type="button"
              onClick={openMap}
              className="flex h-11 items-center gap-1.5 rounded-full bg-card px-3.5 text-[14px] font-semibold ring-1 ring-border active:bg-muted"
            >
              <MapPin className="size-4" /> Pick a spot on the map
            </button>
          </div>
        </div>
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
        blocked={data?.location === "blocked"}
        onChoose={(next) => { choose(next); setPicking(false); }}
        onUseLocation={() => { setPicking(false); askForLocation(); }}
        onHowTo={() => { setPicking(false); setHowTo(true); }}
        onPickMap={openMap}
      />
      <MapPickerSheet
        key={mapKey}
        open={mapOpen}
        onOpenChange={setMapOpen}
        start={choice.mode === "pin" ? { lat: choice.lat, lng: choice.lng } : null}
        onUse={(spot) => { choose({ mode: "pin", ...spot }); setMapOpen(false); }}
      />
      <LocationHowTo open={howTo} onOpenChange={setHowTo} onRetry={() => { setHowTo(false); askForLocation(); }} />
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

function NearSheet({ open, onOpenChange, choice, blocked, onChoose, onUseLocation, onHowTo, onPickMap }: {
  open: boolean; onOpenChange: (open: boolean) => void; choice: NearChoice;
  /** Location was refused, is off, or timed out: "Use my location" opens the how-to instead of asking again. */
  blocked: boolean;
  onChoose: (choice: NearChoice) => void; onUseLocation: () => void; onHowTo: () => void; onPickMap: () => void;
}) {
  const [draft, setDraft] = useState(choice.mode === "place" ? choice.place : "");
  const deviceOk = canUseDeviceLocation(); // false on plain http: no location option there
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="mx-auto max-h-[85dvh] max-w-md overflow-y-auto rounded-t-3xl pb-[calc(1rem+env(safe-area-inset-bottom))]">
        <SheetHeader>
          <SheetTitle className="text-[17px]">Where should we look?</SheetTitle>
          <SheetDescription>Only a rough area is shared with the store search, never your name or exact spot.</SheetDescription>
        </SheetHeader>
        <div className="space-y-2 px-4">
          {deviceOk && (
            <NearOption
              active={choice.mode === "auto" && !blocked}
              icon={<LocateFixed className="size-5" />}
              title="Use my location (recommended)"
              body={blocked
                ? "Location is off or blocked for DAHA. Tap to see how to turn it on."
                : "A rough location (about 1 km), only for store search, never saved. Without it, pick a spot below."}
              onClick={blocked ? onHowTo : onUseLocation}
            />
          )}
          <NearOption
            active={choice.mode === "pin"}
            icon={<MapPin className="size-5" />}
            title="Pick a spot on the map"
            body={choice.mode === "pin"
              ? `Pin at ${choice.lat.toFixed(2)}, ${choice.lng.toFixed(2)}. Tap to move it.`
              : "Drag a pin to where you are. No location permission needed."}
            onClick={onPickMap}
          />
          <NearOption
            active={choice.mode === "campus" || (choice.mode === "auto" && (blocked || !deviceOk))}
            icon={<GraduationCap className="size-5" />}
            title="Stanford campus"
            body="No location permission needed."
            onClick={() => onChoose({ mode: "campus" })}
          />
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
                placeholder="Town, ZIP, or coordinates"
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
            <p className="text-[13px] text-muted-foreground">For example 94305, Kyoto, Japan, or 1.30, 103.85</p>
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

/** How to turn location on for DAHA (plans/LOCATION.md §5.2). Menus move between OS versions, so the steps stay short. */
function LocationHowTo({ open, onOpenChange, onRetry }: {
  open: boolean; onOpenChange: (open: boolean) => void; onRetry: () => void;
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="mx-auto max-h-[85dvh] max-w-md overflow-y-auto rounded-t-3xl pb-[calc(1rem+env(safe-area-inset-bottom))]">
        <SheetHeader>
          <SheetTitle className="text-[17px]">Turn on location</SheetTitle>
          <SheetDescription>
            {WHY_LOCATION} Until then we show stores near Stanford campus, or you can pick a spot on the map.
          </SheetDescription>
        </SheetHeader>
        <div className="space-y-4 px-4 text-[14px]">
          <div className="space-y-1.5">
            <h3 className="font-semibold">iPhone (Safari)</h3>
            <ol className="list-decimal space-y-1 pl-5">
              <li>Settings → Privacy &amp; Security → Location Services: turn it on.</li>
              <li>In the same list, Safari Websites → While Using the App.</li>
              <li>For this site: the page-settings button in Safari&apos;s address bar → Website Settings → Location → Allow.</li>
            </ol>
            <p className="text-[13px] text-muted-foreground">The DAHA app on your home screen asks by itself the first time.</p>
          </div>
          <div className="space-y-1.5">
            <h3 className="font-semibold">Android (Chrome)</h3>
            <ol className="list-decimal space-y-1 pl-5">
              <li>Turn Location on in quick settings.</li>
              <li>For this site: the icon left of the address → Permissions → Location → Allow.</li>
              <li>If Chrome itself has no location access: Settings → Apps → Chrome → Permissions → Location.</li>
            </ol>
          </div>
          <button
            type="button"
            onClick={onRetry}
            className="h-12 w-full rounded-full bg-primary font-semibold text-primary-foreground active:bg-primary-hover"
          >
            Try again
          </button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
