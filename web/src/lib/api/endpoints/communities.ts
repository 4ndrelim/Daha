import { call, http } from "../client";
import { notMocked } from "../mock";
import type { Community, CommunityCreate, CommunityKind, ID, JoinBody, Page, UserRef } from "../types";

export interface CommunityListQuery { kind?: CommunityKind; q?: string; mine?: boolean }

export const communities = {
  list: (query: CommunityListQuery = {}) =>
    call("communities", () => http<Community[]>("GET", "/communities", { query: { ...query } }), () => notMocked<Community[]>("communities.list")),
  create: (body: CommunityCreate) =>
    call("communities", () => http<Community>("POST", "/communities", { body }), () => notMocked<Community>("communities.create")),
  get: (idOrSlug: ID | string) =>
    call("communities", () => http<Community>("GET", `/communities/${idOrSlug}`), () => notMocked<Community>("communities.get")),
  join: (id: ID, body: JoinBody = {}) =>
    call("communities", () => http<Community>("POST", `/communities/${id}/join`, { body }), () => notMocked<Community>("communities.join")),
  leave: (id: ID) =>
    call("communities", () => http<void>("POST", `/communities/${id}/leave`), () => notMocked<void>("communities.leave")),
  members: (id: ID, query: { offset?: number; limit?: number } = {}) =>
    call("communities", () => http<Page<UserRef>>("GET", `/communities/${id}/members`, { query }), () => notMocked<Page<UserRef>>("communities.members")),
};
