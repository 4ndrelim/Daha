import { http } from "../client";
import type { SearchQuery } from "../endpoints/search";
import type { Community, ParsedQuery, SearchResponse } from "../types";
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
};
