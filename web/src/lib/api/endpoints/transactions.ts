import { call, http } from "../client";
import { notMocked } from "../mock";
import type { ID, Review, ReviewCreate, Transaction, TxActionBody } from "../types";

export interface TransactionListQuery { role?: "owner" | "borrower" | "all"; state?: "active" | "past" | "all" }

export const transactions = {
  list: (query: TransactionListQuery = {}) =>
    call("transactions", () => http<Transaction[]>("GET", "/transactions", { query: { ...query } }), () => notMocked<Transaction[]>("transactions.list")),
  get: (id: ID) => call("transactions", () => http<Transaction>("GET", `/transactions/${id}`), () => notMocked<Transaction>("transactions.get")),
  action: (id: ID, body: TxActionBody) =>
    call("transactions", () => http<Transaction>("POST", `/transactions/${id}/actions`, { body }), () => notMocked<Transaction>("transactions.action")),
  review: (id: ID, body: ReviewCreate) =>
    call("transactions", () => http<Review>("POST", `/transactions/${id}/review`, { body }), () => notMocked<Review>("transactions.review")),
};
