import { http } from "../client";
import type { FeedEntry, FulfillableRequest, HomeFeed, ID, ItemCard, Page, RequestCard, RequestDetail } from "../types";
import { getPool, itemScore, latency, tokens } from "./pool";

const newest = <T extends { created_at: string }>(a: T, b: T) => b.created_at.localeCompare(a.created_at);
const dormFirst = <T extends { same_dorm: boolean; created_at: string }>(a: T, b: T) =>
  Number(b.same_dorm) - Number(a.same_dorm) || newest(a, b);

function toCard(r: RequestDetail): RequestCard {
  const { id, title, raw_text, category, status, requester, needed_from, needed_until, visibility, community_label,
    distance_min, same_dorm, offer_count, match_count, created_at } = r;
  return { id, title, raw_text, category, status, requester, needed_from, needed_until, visibility, community_label,
    distance_min, same_dorm, offer_count, match_count, created_at };
}

function fulfillable(myItems: ItemCard[], requests: RequestDetail[]): FulfillableRequest[] {
  const shareable = myItems.filter((i) => i.status === "available");
  return requests
    .filter((r) => r.status === "open" && !r.is_mine)
    .map((r) => {
      const q = tokens(`${r.item_name ?? ""} ${r.title}`);
      const mine = shareable.filter((i) => itemScore(i, q) > 0 || (r.category && i.category === r.category && itemScore(i, q) > 0));
      return { request: toCard(r), my_matching_items: mine };
    })
    .filter((f) => f.my_matching_items.length > 0)
    .sort((a, b) => dormFirst(a.request, b.request));
}

export const mockFeed = {
  async home(): Promise<HomeFeed> {
    const [pool] = await Promise.all([getPool(), latency()]);
    const { me, items, myItems, requests } = pool;
    const mineShared = myItems.filter((i) => i.visibility !== "private");
    const open = requests.filter((r) => r.status === "open" && !r.is_mine);
    return {
      dorm: me.dorm,
      my_item_count: mineShared.length,
      show_scan_cta: mineShared.length < 3,
      you_can_help: fulfillable(myItems, requests).slice(0, 5),
      requests_nearby: open.map(toCard).sort(dormFirst).slice(0, 10),
      new_nearby: items.filter((i) => i.status === "available").sort(dormFirst).slice(0, 12),
      stats: {
        dorm_items: items.filter((i) => i.same_dorm).length + mineShared.length,
        campus_items: items.length + mineShared.length,
        open_requests: open.length,
      },
    };
  },

  async community(id: ID, query: { kind?: "all" | "items" | "requests"; offset?: number; limit?: number } = {}): Promise<Page<FeedEntry>> {
    const [pool] = await Promise.all([getPool(), latency()]);
    const members = await http<Page<{ id: ID }>>("GET", `/communities/${id}/members`, { query: { limit: 50 } }).catch(() => ({ items: [] }));
    const memberIds = new Set(members.items.map((m) => m.id));
    const kind = query.kind ?? "all";
    const entries: FeedEntry[] = [];
    if (kind !== "requests") {
      for (const item of [...pool.items, ...pool.myItems.filter((i) => i.visibility !== "private")]) {
        if (memberIds.has(item.owner.id)) entries.push({ kind: "item", created_at: item.created_at, item });
      }
    }
    if (kind !== "items") {
      for (const r of pool.requests) {
        if (memberIds.has(r.requester.id) && r.status === "open") entries.push({ kind: "request", created_at: r.created_at, request: toCard(r) });
      }
    }
    entries.sort(newest);
    const offset = query.offset ?? 0;
    const limit = query.limit ?? 20;
    const page = entries.slice(offset, offset + limit);
    return { items: page, next_offset: offset + limit < entries.length ? offset + limit : null };
  },

  async fulfillable(): Promise<FulfillableRequest[]> {
    const [pool] = await Promise.all([getPool(), latency()]);
    return fulfillable(pool.myItems, pool.requests).slice(0, 20);
  },
};
