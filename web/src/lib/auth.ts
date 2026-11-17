"use client";

import type { QueryClient } from "@tanstack/react-query";
import { setToken } from "@/lib/api";
import type { AuthResponse } from "@/lib/api/types";
import { meKey } from "@/lib/queries/me";
import { invalidatePool } from "@/lib/api/mock/pool";

/** Only follow same-site paths from ?next= (never an external URL). */
export function safeNext(next: string | null | undefined, fallback = "/home"): string {
  if (!next || !next.startsWith("/") || next.startsWith("//")) return fallback;
  return next;
}

export function startSession(qc: QueryClient, res: AuthResponse) {
  qc.clear();
  invalidatePool();
  setToken(res.token);
  qc.setQueryData(meKey, res.user);
}

export function endSession(qc: QueryClient) {
  setToken(null);
  invalidatePool();
  qc.clear();
}
