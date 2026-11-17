import { call, http } from "../client";
import { notMocked } from "../mock";
import type { Category, Condition, ID, SearchResponse, TransactionType } from "../types";

export interface SearchQuery {
  q?: string; kind?: "all" | "items" | "requests" | "communities"; category?: Category; community_id?: ID;
  scope?: "campus" | "dorm"; max_walk_min?: number; transaction_type?: TransactionType; condition?: Condition;
  available_only?: boolean; offset?: number; limit?: number;
}

export const search = {
  search: (query: SearchQuery) =>
    call("search", () => http<SearchResponse>("GET", "/search", { query: { ...query } }), () => notMocked<SearchResponse>("search.search")),
};
