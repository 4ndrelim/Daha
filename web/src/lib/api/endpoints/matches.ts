import { ApiError, call, http } from "../client";
import { mockMatches } from "../mock/matches";
import type { ID, MatchesResponse, MutualMatchesResponse } from "../types";

export const matches = {
  get: (requestId: ID) =>
    call("matches", () => http<MatchesResponse>("GET", `/requests/${requestId}/matches`), () => mockMatches.get(requestId)),
  /** Mutual matches; `null` when the server has the feature switched off (404), so the card just hides. */
  mutual: () =>
    call<MutualMatchesResponse | null>(
      "matches",
      () =>
        http<MutualMatchesResponse>("GET", "/me/mutual-matches").catch((err: unknown) => {
          if (err instanceof ApiError && err.status === 404) return null;
          throw err;
        }),
      () => mockMatches.mutual(),
    ),
};
