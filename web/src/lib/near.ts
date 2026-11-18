"use client";

// Where "Buy or rent nearby" looks: the person's dorm (the default, no permission needed), their
// device location (opt-in, rounded to ~1 km before it leaves the browser), or a town/ZIP they type.
// The choice is remembered in this browser as a convenience; coordinates are never saved.

import { useCallback, useState } from "react";

export type NearChoice = { mode: "dorm" } | { mode: "device" } | { mode: "place"; place: string };

const KEY = "daha_buy_near";

function readChoice(): NearChoice {
  try {
    const saved = JSON.parse(window.localStorage.getItem(KEY) ?? "null") as Partial<NearChoice> | null;
    if (saved?.mode === "device") return { mode: "device" };
    if (saved?.mode === "place" && "place" in saved && typeof saved.place === "string" && saved.place.trim()) {
      return { mode: "place", place: saved.place.trim().slice(0, 60) };
    }
  } catch {
    // storage blocked or unreadable: fall back to the dorm
  }
  return { mode: "dorm" };
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

/** Browsers only share location on https (or localhost), so the option hides on plain-http LAN links. */
export function canUseDeviceLocation(): boolean {
  return typeof window !== "undefined" && window.isSecureContext && "geolocation" in navigator;
}

export class NoDeviceLocation extends Error {}

/** The device's location rounded to 2 decimals (~1 km), so nothing more precise ever leaves the browser. */
export function roughDeviceLocation(): Promise<{ lat: number; lng: number }> {
  return new Promise((resolve, reject) => {
    if (!canUseDeviceLocation()) {
      reject(new NoDeviceLocation("unavailable"));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) =>
        resolve({ lat: Math.round(coords.latitude * 100) / 100, lng: Math.round(coords.longitude * 100) / 100 }),
      (err) => reject(new NoDeviceLocation(err.message)),
      { enableHighAccuracy: false, maximumAge: 10 * 60_000, timeout: 10_000 },
    );
  });
}
