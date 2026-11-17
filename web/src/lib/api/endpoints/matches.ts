import { call, http } from "../client";
import { mockMatches } from "../mock/matches";
import type { ID, MatchesResponse } from "../types";

export const matches = {
  get: (requestId: ID) =>
    call("matches", () => http<MatchesResponse>("GET", `/requests/${requestId}/matches`), () => mockMatches.get(requestId)),
};
