import { call, http } from "../client";
import { notMocked } from "../mock";
import type { FeedEntry, FulfillableRequest, HomeFeed, ID, Page } from "../types";

export const feed = {
  home: () => call("feed", () => http<HomeFeed>("GET", "/feed/home"), () => notMocked<HomeFeed>("feed.home")),
  community: (id: ID, query: { kind?: "all" | "items" | "requests"; offset?: number; limit?: number } = {}) =>
    call("feed", () => http<Page<FeedEntry>>("GET", `/communities/${id}/feed`, { query }), () => notMocked<Page<FeedEntry>>("feed.community")),
  fulfillable: () =>
    call("feed", () => http<FulfillableRequest[]>("GET", "/me/fulfillable"), () => notMocked<FulfillableRequest[]>("feed.fulfillable")),
};
