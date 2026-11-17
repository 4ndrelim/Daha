import { call, http } from "../client";
import { notMocked } from "../mock";
import type { ID, ItemCard, Me, MeUpdate, Page, Review, UserPublic } from "../types";

export const me = {
  get: () => call("users", () => http<Me>("GET", "/me"), () => notMocked<Me>("me.get")),
  update: (body: MeUpdate) => call("users", () => http<Me>("PATCH", "/me", { body }), () => notMocked<Me>("me.update")),
};

export const users = {
  get: (id: ID) => call("users", () => http<UserPublic>("GET", `/users/${id}`), () => notMocked<UserPublic>("users.get")),
  items: (id: ID, query: { offset?: number; limit?: number } = {}) =>
    call("users", () => http<Page<ItemCard>>("GET", `/users/${id}/items`, { query }), () => notMocked<Page<ItemCard>>("users.items")),
  reviews: (id: ID) => call("users", () => http<Review[]>("GET", `/users/${id}/reviews`), () => notMocked<Review[]>("users.reviews")),
};
