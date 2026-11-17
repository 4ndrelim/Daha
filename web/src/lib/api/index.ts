import { ai } from "./endpoints/ai";
import { auth } from "./endpoints/auth";
import { communities } from "./endpoints/communities";
import { conversations } from "./endpoints/conversations";
import { events } from "./endpoints/events";
import { feed } from "./endpoints/feed";
import { items } from "./endpoints/items";
import { matches } from "./endpoints/matches";
import { notifications } from "./endpoints/notifications";
import { places } from "./endpoints/places";
import { requests } from "./endpoints/requests";
import { search } from "./endpoints/search";
import { transactions } from "./endpoints/transactions";
import { uploads } from "./endpoints/uploads";
import { me, users } from "./endpoints/users";

// Scans (C) live in ./endpoints/scans.ts, owned by Person C.
export const api = {
  auth, me, users, communities, places, uploads, items, requests, transactions,
  conversations, notifications, events, search, feed, matches, ai,
};

export { ApiError, getToken, setToken, isMocked } from "./client";
export { track } from "./endpoints/events";
export type * from "./types";
