import { call, http } from "../client";
import { notMocked } from "../mock";
import type {
  BorrowBody, ID, ItemCard, ItemCreate, ItemDetail, ItemsBatchBody, ItemsBatchResponse, ItemStatus, ItemUpdate, Transaction, ValueEstimate,
} from "../types";

export const items = {
  create: (body: ItemCreate) => call("items", () => http<ItemDetail>("POST", "/items", { body }), () => notMocked<ItemDetail>("items.create")),
  batch: (body: ItemsBatchBody) =>
    call("items", () => http<ItemsBatchResponse>("POST", "/items/batch", { body }), () => notMocked<ItemsBatchResponse>("items.batch")),
  get: (id: ID) => call("items", () => http<ItemDetail>("GET", `/items/${id}`), () => notMocked<ItemDetail>("items.get")),
  /** Value exchange: a starting value (a cached store price, else nothing). Never a paid call. */
  valueEstimate: (name: string) =>
    call("items", () => http<ValueEstimate>("GET", "/items/value-estimate", { query: { name } }), () => Promise.resolve<ValueEstimate>({ value_usd: null, source: null })),
  update: (id: ID, body: ItemUpdate) =>
    call("items", () => http<ItemDetail>("PATCH", `/items/${id}`, { body }), () => notMocked<ItemDetail>("items.update")),
  remove: (id: ID) => call("items", () => http<void>("DELETE", `/items/${id}`), () => notMocked<void>("items.remove")),
  mine: (query: { status?: ItemStatus } = {}) =>
    call("items", () => http<ItemCard[]>("GET", "/me/items", { query }), () => notMocked<ItemCard[]>("items.mine")),
  borrow: (id: ID, body: BorrowBody = {}) =>
    call("items", () => http<Transaction>("POST", `/items/${id}/borrow`, { body }), () => notMocked<Transaction>("items.borrow")),
};
