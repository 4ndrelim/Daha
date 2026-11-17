/**
 * Stand-ins for Person C's discovery endpoints until they land (C2/C3).
 * Instead of made-up fixtures, they read A's *live* endpoints, so cards link to real items and requests
 * and respect real visibility. Keyword matching only; C's real search/matching replaces all of this.
 */
import { getToken, http } from "../client";
import type { Category, Community, ItemCard, Me, Page, RequestDetail, UserRef } from "../types";

export const latency = () => new Promise((r) => setTimeout(r, 150 + Math.random() * 250));

export interface Pool { me: Me; items: ItemCard[]; myItems: ItemCard[]; requests: RequestDetail[] }

let cache: { at: number; token: string | null; pool: Promise<Pool> } | null = null;
const MAX_REQUEST_ID = 80; // no "list requests" endpoint in A's contract, so probe ids (local dev only)

async function load(): Promise<Pool> {
  const me = await http<Me>("GET", "/me");
  const [campus, myItems] = await Promise.all([http<Community>("GET", "/communities/campus"), http<ItemCard[]>("GET", "/me/items")]);
  const members = await http<Page<UserRef>>("GET", `/communities/${campus.id}/members`, { query: { limit: 50 } })
    .catch(() => ({ items: [] as UserRef[], next_offset: null }));
  const others = members.items.filter((u) => u.id !== me.id);
  const pages = await Promise.all(
    others.map((u) => http<Page<ItemCard>>("GET", `/users/${u.id}/items`, { query: { limit: 50 } }).catch(() => null)),
  );
  const items = pages.flatMap((p) => p?.items ?? []);
  const probes = await Promise.allSettled(
    Array.from({ length: MAX_REQUEST_ID }, (_, i) => http<RequestDetail>("GET", `/requests/${i + 1}`)),
  );
  const requests = probes.flatMap((p) => (p.status === "fulfilled" ? [p.value] : []));
  return { me, items, myItems, requests };
}

export function getPool(): Promise<Pool> {
  const token = getToken();
  if (!cache || Date.now() - cache.at > 30_000 || cache.token !== token) {
    const pool = load();
    cache = { at: Date.now(), token, pool };
    pool.catch(() => { cache = null; });
  }
  return cache.pool;
}

export function invalidatePool() { cache = null; }

const STOP = new Set(["the", "and", "for", "can", "any", "anyone", "have", "does", "someone", "who", "with", "need", "borrow",
  "near", "me", "my", "dorm", "available", "this", "next", "that", "you", "your", "use", "could", "would", "please", "help",
  "looking", "want", "lend", "some", "get", "tonight", "today", "tomorrow", "weekend", "week", "in", "a", "an", "i", "of", "to"]);

function singular(t: string): string {
  if (t.length > 4 && /(x|ch|sh|ss)es$/.test(t)) return t.slice(0, -2);
  if (t.length > 3 && t.endsWith("s") && !t.endsWith("ss")) return t.slice(0, -1);
  return t;
}

export function tokens(text: string): string[] {
  return text.toLowerCase().replace(/[^a-z0-9\s-]/g, " ").split(/\s+/)
    .map(singular)
    .filter((t) => t.length >= 3 && !STOP.has(t));
}

export function overlap(a: string[], b: string[]): number {
  const set = new Set(b);
  return a.filter((t) => set.has(t)).length;
}

/** Rough keyword → category for the stand-in parser and search. */
const CATEGORY_WORDS: [Category, RegExp][] = [
  ["academic", /\b(textbook|book|calculator|binder|notebook|stationery|lab|goggle|pen|highlighter|calc)/],
  ["tech", /\b(charger|cable|adapter|monitor|keyboard|camera|hdmi|usb|laptop|mouse|headphone|speaker)/],
  ["clothing", /\b(suit|dress|jacket|blazer|costume|formal|tie|shirt|coat|clothes|interview)/],
  ["dorm", /\b(vacuum|fan|kettle|cookware|pan|pot|appliance|lamp|iron|blender|toaster|mug)/],
  ["consumables", /\b(spice|oil|food|detergent|toiletr|shampoo|snack|salt|sugar|curry)/],
  ["sports", /\b(bike|helmet|racket|camping|tent|ball|yoga|pump|hiking)/],
  ["moving", /\b(box|boxes|cart|tool|storage|bin|tape|dolly|moving)/],
  ["events", /\b(projector|decoration|party|costume|lights)/],
  ["services", /\b(tutor|photograph|repair|fix|moving help|lesson)/],
];

export function guessCategory(text: string): Category | null {
  const t = text.toLowerCase();
  if (/\b(repair|fix|tutor|help me|someone who)/.test(t)) return "services";
  for (const [cat, re] of CATEGORY_WORDS) if (re.test(t)) return cat;
  return null;
}

export function itemScore(item: ItemCard, q: string[]): number {
  return overlap(tokens(`${item.name} ${item.category}`), q);
}

export type { Community };
