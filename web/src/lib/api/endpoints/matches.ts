import { call, http } from "../client";
import { notMocked } from "../mock";
import type { ID, MatchesResponse } from "../types";

export const matches = {
  get: (requestId: ID) =>
    call("matches", () => http<MatchesResponse>("GET", `/requests/${requestId}/matches`), () => notMocked<MatchesResponse>("matches.get")),
};
