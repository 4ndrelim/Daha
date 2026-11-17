import { http } from "../client";
import type { ID, MatchesResponse, RequestDetail } from "../types";
import { getPool, itemScore, latency, tokens } from "./pool";

export const mockMatches = {
  async get(requestId: ID): Promise<MatchesResponse> {
    const [pool, request] = await Promise.all([getPool(), http<RequestDetail>("GET", `/requests/${requestId}`), latency()]);
    const q = tokens(`${request.item_name ?? ""} ${request.title}`);
    const items = pool.items
      .filter((i) => i.owner.id !== request.requester.id && i.status !== "unavailable")
      .map((i) => ({ i, s: itemScore(i, q) }))
      .filter(({ s }) => s > 0)
      .sort((a, b) => b.s - a.s || Number(b.i.same_dorm) - Number(a.i.same_dorm) || (a.i.distance_min ?? 99) - (b.i.distance_min ?? 99))
      .slice(0, 10)
      .map(({ i, s }) => ({
        ...i,
        match_score: Math.min(1, 0.5 + s * 0.2),
        match_reason: [i.same_dorm ? "Same dorm" : null, i.distance_min !== null ? `${i.distance_min} min walk` : null].filter(Boolean).join(" · ") || null,
      }));
    return { matching_status: "done", items, private_pinged_count: 0 };
  },
};
