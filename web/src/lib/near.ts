"use client";

// Where "Buy or rent nearby" looks (plans/LOCATION.md): the phone's location when DAHA is allowed
// to use it (rounded to ~1 km before it leaves the browser), else Stanford campus, or a spot the
// person picks themselves: a pin on the map, or a town, ZIP or coordinates they type. The phone's
// own location is never saved; a picked pin is remembered in this browser, rounded to ~1 km, like
// a typed place.

import { useCallback, useState } from "react";

/** `auto` = use my location if allowed, else campus. `pin` = a spot picked on the map. */
export type NearChoice =
  | { mode: "auto" }
  | { mode: "campus" }
  | { mode: "place"; place: string }
  | { mode: "pin"; lat: number; lng: number };

export type LocationPermission = "granted" | "prompt" | "denied" | "unavailable";

const KEY = "daha_buy_near";

/** Two decimals, about 1 km: as precise as any location DAHA keeps or sends. */
export const roughly = (n: number) => Math.round(n * 100) / 100;

/** Where the map opens when there's no pin yet: Stanford campus (the server's COMMERCIAL_DEFAULT_*). */
export const CAMPUS = { lat: 37.4275, lng: -122.1697 };
const WAIT_MS = 5_000; // never keep someone waiting longer than this for a location

function readChoice(): NearChoice {
  try {
    const saved = JSON.parse(window.localStorage.getItem(KEY) ?? "null") as {
      mode?: string; place?: unknown; lat?: unknown; lng?: unknown;
    } | null;
    if (saved?.mode === "campus") return { mode: "campus" };
    if (saved?.mode === "pin" && typeof saved.lat === "number" && typeof saved.lng === "number"
      && Math.abs(saved.lat) <= 90 && Math.abs(saved.lng) <= 180) {
      return { mode: "pin", lat: roughly(saved.lat), lng: roughly(saved.lng) };
    }
    if (saved?.mode === "place" && typeof saved.place === "string" && saved.place.trim()) {
      return { mode: "place", place: saved.place.trim().slice(0, 60) };
    }
    // Older saved values ("dorm", "device") and anything unknown become `auto`.
  } catch {
    // storage blocked or unreadable: fall back to auto
  }
  return { mode: "auto" };
}

export function useNearChoice() {
  const [choice, setChoice] = useState<NearChoice>(readChoice);
  const choose = useCallback((next: NearChoice) => {
    setChoice(next);
    try {
      window.localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      // fine: the choice just isn't remembered
    }
  }, []);
  return [choice, choose] as const;
}

/** Browsers only share location on https (or localhost), so there's no location option on plain-http LAN links. */
export function canUseDeviceLocation(): boolean {
  return typeof window !== "undefined" && window.isSecureContext && "geolocation" in navigator;
}

// A refusal, a timeout, or "location is off" in this visit. While set we don't ask again by
// ourselves (no repeated prompts); only an explicit "Try again" tap clears it. Never persisted.
let failedThisVisit = false;

export function forgetLocationFailure(): void {
  failedThisVisit = false;
}

/**
 * Whether asking for the location would work without a prompt (`granted`), would show the
 * browser's prompt (`prompt`), or can't work (`denied`, `unavailable`). Never prompts by itself.
 */
export async function locationPermission(): Promise<LocationPermission> {
  if (!canUseDeviceLocation()) return "unavailable";
  if (failedThisVisit) return "denied";
  try {
    const status = await navigator.permissions.query({ name: "geolocation" });
    if (status.state === "granted" || status.state === "denied") return status.state;
  } catch {
    // this browser can't tell: treat it as "not asked yet"
  }
  return "prompt";
}

export class NoDeviceLocation extends Error {
  /** Set when we stopped waiting: resolves if the location still arrives (e.g. the prompt was answered late). */
  late?: Promise<{ lat: number; lng: number }>;
}

/**
 * The device's location rounded to 2 decimals (~1 km), so nothing more precise ever leaves the
 * browser. Shows the browser's prompt if permission hasn't been given yet, so call it only right
 * after a tap. Gives up after 5 s.
 */
export function roughDeviceLocation(): Promise<{ lat: number; lng: number }> {
  if (!canUseDeviceLocation()) return Promise.reject(new NoDeviceLocation("unavailable"));
  const position = new Promise<{ lat: number; lng: number }>((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        failedThisVisit = false;
        resolve({ lat: roughly(coords.latitude), lng: roughly(coords.longitude) });
      },
      (err) => {
        failedThisVisit = true;
        reject(new NoDeviceLocation(err.message));
      },
      { enableHighAccuracy: false, maximumAge: 10 * 60_000, timeout: WAIT_MS },
    );
  });
  // The browser's own timeout doesn't count the time its permission prompt is open, so we also stop the clock ourselves.
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
      failedThisVisit = true;
      const gaveUp = new NoDeviceLocation("timeout");
      gaveUp.late = position;
      position.catch(() => undefined); // a late refusal is already handled above
      reject(gaveUp);
    }, WAIT_MS);
    position.then(
      (place) => { window.clearTimeout(timer); resolve(place); },
      (err) => { window.clearTimeout(timer); reject(err); },
    );
  });
}
