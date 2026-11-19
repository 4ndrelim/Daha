import { call, http } from "../client";
import { notMocked } from "../mock";
import type { ConditionSlot, ConditionStage, HandoffSendBody, ID, Review, ReviewCreate, Transaction, TxActionBody } from "../types";

export interface TransactionListQuery { role?: "owner" | "borrower" | "all"; state?: "active" | "past" | "all" }

export const transactions = {
  list: (query: TransactionListQuery = {}) =>
    call("transactions", () => http<Transaction[]>("GET", "/transactions", { query: { ...query } }), () => notMocked<Transaction[]>("transactions.list")),
  get: (id: ID) => call("transactions", () => http<Transaction>("GET", `/transactions/${id}`), () => notMocked<Transaction>("transactions.get")),
  action: (id: ID, body: TxActionBody) =>
    call("transactions", () => http<Transaction>("POST", `/transactions/${id}/actions`, { body }), () => notMocked<Transaction>("transactions.action")),
  conditionPhoto: (id: ID, stage: ConditionStage, slot: ConditionSlot, file: Blob) => {
    const form = new FormData();
    form.append("file", file, `${slot}.jpg`);
    return call("transactions", () => http<Transaction>("PUT", `/transactions/${id}/condition/${stage}/${slot}`, { form }), () => notMocked<Transaction>("transactions.conditionPhoto"));
  },
  /** Value exchange: the swap's borrower says about what their side is worth (null clears it). */
  swapValue: (id: ID, value_usd: number | null) =>
    call("transactions", () => http<Transaction>("POST", `/transactions/${id}/swap-value`, { body: { value_usd } }), () => notMocked<Transaction>("transactions.swapValue")),
  conditionConfirm: (id: ID) =>
    call("transactions", () => http<Transaction>("POST", `/transactions/${id}/condition/confirm`), () => notMocked<Transaction>("transactions.conditionConfirm")),
  conditionCompare: (id: ID) =>
    call("transactions", () => http<Transaction>("POST", `/transactions/${id}/condition/compare`), () => notMocked<Transaction>("transactions.conditionCompare")),
  /** "Suggest a time & place": the only call that starts the handoff agent (3 a day per transaction). */
  handoffSuggest: (id: ID) =>
    call("transactions", () => http<Transaction>("POST", `/transactions/${id}/handoff/suggest`), () => notMocked<Transaction>("transactions.handoffSuggest")),
  /** Send my draft as it is (no body), or a time and place I picked. */
  handoffSend: (id: ID, body: HandoffSendBody = {}) =>
    call("transactions", () => http<Transaction>("POST", `/transactions/${id}/handoff/send`, { body }), () => notMocked<Transaction>("transactions.handoffSend")),
  handoffAccept: (id: ID) =>
    call("transactions", () => http<Transaction>("POST", `/transactions/${id}/handoff/accept`), () => notMocked<Transaction>("transactions.handoffAccept")),
  handoffDismiss: (id: ID) =>
    call("transactions", () => http<Transaction>("DELETE", `/transactions/${id}/handoff`), () => notMocked<Transaction>("transactions.handoffDismiss")),
  review: (id: ID, body: ReviewCreate) =>
    call("transactions", () => http<Review>("POST", `/transactions/${id}/review`, { body }), () => notMocked<Review>("transactions.review")),
};
