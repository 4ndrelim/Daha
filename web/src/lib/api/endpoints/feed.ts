import { call, http } from "../client";
import { mockFeed } from "../mock/feed";
import type { FeedEntry, FulfillableRequest, HomeFeed, ID, Page } from "../types";

export const feed = {
  home: () => call("feed", () => http<HomeFeed>("GET", "/feed/home"), () => mockFeed.home()),
  community: (id: ID, query: { kind?: "all" | "items" | "requests"; offset?: number; limit?: number } = {}) =>
    call("feed", () => http<Page<FeedEntry>>("GET", `/communities/${id}/feed`, { query }), () => mockFeed.community(id, query)),
  fulfillable: () =>
    call("feed", () => http<FulfillableRequest[]>("GET", "/me/fulfillable"), () => mockFeed.fulfillable()),
};
