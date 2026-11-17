import { call, http } from "../client";
import { notMocked } from "../mock";
import type { ID, OfferCreate, RequestCard, RequestCreate, RequestDetail, RequestUpdate, Transaction } from "../types";

export const requests = {
  create: (body: RequestCreate) =>
    call("requests", () => http<RequestDetail>("POST", "/requests", { body }), () => notMocked<RequestDetail>("requests.create")),
  get: (id: ID) => call("requests", () => http<RequestDetail>("GET", `/requests/${id}`), () => notMocked<RequestDetail>("requests.get")),
  update: (id: ID, body: RequestUpdate) =>
    call("requests", () => http<RequestDetail>("PATCH", `/requests/${id}`, { body }), () => notMocked<RequestDetail>("requests.update")),
  mine: () => call("requests", () => http<RequestCard[]>("GET", "/me/requests"), () => notMocked<RequestCard[]>("requests.mine")),
  offer: (id: ID, body: OfferCreate) =>
    call("requests", () => http<Transaction>("POST", `/requests/${id}/offers`, { body }), () => notMocked<Transaction>("requests.offer")),
};
