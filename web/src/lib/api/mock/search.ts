import { http } from "../client";
import type { SearchQuery } from "../endpoints/search";
import type {
  CommercialOffer, CommercialSearchBody, CommercialSearchResponse, Community, ParsedQuery, SearchResponse,
} from "../types";
import { categoryInfo, TX_TYPE_LABEL } from "@/lib/categories";
import { getPool, guessCategory, itemScore, latency, overlap, tokens } from "./pool";

export const mockSearch = {
  async search(query: SearchQuery): Promise<SearchResponse> {
    const text = (query.q ?? "").trim();
    const lower = text.toLowerCase();
    const q = tokens(text);
    const near = /\bnear (me|by)\b|\bnearby\b/.test(lower);
    const parsedScope = /\bin my dorm\b|\bmy dorm\b/.test(lower) ? "dorm" : null;
    const parsed: ParsedQuery = {
      text,
      category: query.category ?? (text ? guessCategory(text) : null),
      scope: query.scope ?? parsedScope,
      near_me: near,
      available_from: null,
      available_until: null,
      transaction_type: query.transaction_type ?? null,
      chips: [],
    };
    if (parsed.category) parsed.chips.push(categoryInfo(parsed.category).label);
    if (parsed.scope === "dorm") parsed.chips.push("My dorm");
    if (near) parsed.chips.push("Near you");
    if (/this weekend/.test(lower)) parsed.chips.push("This weekend");
    if (parsed.transaction_type) parsed.chips.push(TX_TYPE_LABEL[parsed.transaction_type]);

    const [pool, communities] = await Promise.all([
      getPool(),
      query.kind === "items" || query.kind === "requests" || !text
        ? Promise.resolve([] as Community[])
        : http<Community[]>("GET", "/communities", { query: { q: text } }).catch(() => [] as Community[]),
      latency(),
    ]);

    let items = pool.items.filter((i) => {
      if (query.available_only !== false && i.status !== "available") return false;
      if (parsed.scope === "dorm" && !i.same_dorm) return false;
      if (query.max_walk_min && (i.distance_min === null || i.distance_min > query.max_walk_min)) return false;
      if (query.transaction_type && i.transaction_type !== query.transaction_type) return false;
      if (query.condition && i.condition !== query.condition) return false;
      if (query.category && i.category !== query.category) return false;
      return true;
    });
    if (q.length) {
      items = items
        .map((i) => ({ i, s: itemScore(i, q) + (!query.category && parsed.category === i.category ? 0.5 : 0) }))
        .filter(({ s }) => s >= 1)
        .sort((a, b) => b.s - a.s || Number(b.i.same_dorm) - Number(a.i.same_dorm) || (a.i.distance_min ?? 99) - (b.i.distance_min ?? 99))
        .map(({ i, s }) => ({ ...i, match_score: Math.min(1, 0.4 + s * 0.2), match_reason: i.same_dorm ? "Same dorm" : null }));
    } else {
      items.sort((a, b) => Number(b.same_dorm) - Number(a.same_dorm) || b.created_at.localeCompare(a.created_at));
    }

    const requests = pool.requests
      .filter((r) => r.status === "open" && (!q.length || overlap(tokens(`${r.title} ${r.raw_text}`), q) > 0))
      .filter((r) => !query.category || r.category === query.category)
      .sort((a, b) => Number(b.same_dorm) - Number(a.same_dorm) || b.created_at.localeCompare(a.created_at));

    const offset = query.offset ?? 0;
    const limit = query.limit ?? 20;
    const wantItems = query.kind !== "requests" && query.kind !== "communities";
    const wantRequests = query.kind !== "items" && query.kind !== "communities";
    const pageItems = wantItems ? items.slice(offset, offset + limit) : [];
    const pageRequests = wantRequests ? requests.slice(offset, offset + limit) : [];
    const more = (wantItems && offset + limit < items.length) || (wantRequests && offset + limit < requests.length);
    return { parsed, items: pageItems, requests: pageRequests, communities, next_offset: more ? offset + limit : null };
  },

  /** Sample store offers on example.com, cheapest first, like the backend's mock provider. */
  async commercial(body: CommercialSearchBody): Promise<CommercialSearchResponse> {
    await latency();
    const words = tokens(body.q).join(" ") || body.q.trim();
    const thing = words.charAt(0).toUpperCase() + words.slice(1);
    const base = 8 + ([...words].reduce((n, ch) => n + ch.charCodeAt(0), 0) % 60);
    const place = body.place?.trim() || null;
    const dollars = (n: number) => `$${n.toFixed(2).replace(/\.00$/, "")}`;
    const offer = (title: string, price: number, seller: string, extra: Partial<CommercialOffer> = {}): CommercialOffer => ({
      title, price, currency: "USD", price_text: dollars(price), price_unit: "each", offer_type: "buy", seller,
      location: place ?? "Palo Alto", url: `https://example.com/search?q=${encodeURIComponent(words)}`,
      image_url: null, ...extra,
    });
    const rent = Math.max(3, Math.round(base * 15) / 100);
    const offers = [
      offer(`${thing} rental`, rent, "Sample Rentals", { offer_type: "rent", price_unit: "day", price_text: `${dollars(rent)}/day` }),
      offer(`${thing} (used, good)`, Math.round(base * 55) / 100, "Sample Marketplace"),
      offer(`${thing} (new)`, base + 0.99, "Sample Store"),
      offer(`${thing} (ships in 2 days)`, base + 6.49, "Sample Online Shop", { location: null }),
    ].sort((a, b) => (a.price ?? 0) - (b.price ?? 0));
    const device = body.lat != null && body.lng != null;
    return {
      query: words,
      near: place ?? (device ? (body.pinned ? "the pin" : "your location") : "Stanford campus"),
      near_source: place ? "place" : device ? (body.pinned ? "pin" : "device") : "campus",
      offers, provider: "mock", cached: false, fetched_at: new Date().toISOString(),
    };
  },
};
