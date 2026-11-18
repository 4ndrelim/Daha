"use client";

import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { scans } from "@/lib/api/endpoints/scans";
import { invalidatePool } from "@/lib/api/mock/pool";
import type { ID, ItemCreate, ScanPublishBody } from "@/lib/api/types";

export const POLL_MS = 1500;
/** Stop polling after this long; the UI offers "Check again" and the photos that already finished. */
export const POLL_GIVE_UP_MS = 3 * 60_000;

export const scanKey = (id: ID) => ["scans", id] as const;
export const myItemsKey = ["me", "items"] as const;

/** Polls GET /scans/{id} every 1.5 s while processing. React Query stops on unmount, done, or failed. */
export function useScan(id: ID | null, startedAt: number | null) {
  return useQuery({
    queryKey: scanKey(id ?? 0),
    queryFn: () => scans.get(id!),
    enabled: id !== null,
    staleTime: 0,
    refetchOnWindowFocus: false,
    retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 3,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && data.status !== "processing") return false;
      if (startedAt !== null && Date.now() - startedAt > POLL_GIVE_UP_MS) return false;
      return POLL_MS;
    },
  });
}

export function usePlaces() {
  return useQuery({ queryKey: ["places"], queryFn: () => api.places.list(), staleTime: 5 * 60_000 });
}

export function useMyItems() {
  return useQuery({ queryKey: myItemsKey, queryFn: () => api.items.mine() });
}

/** Everything that shows "my stuff": me (counts, points, onboarded), feeds, item lists, search. */
export function invalidateAfterSharing(qc: QueryClient) {
  invalidatePool();
  for (const key of [["me"], ["feed"], ["items"], ["users"], ["search"], ["communities"]]) {
    void qc.invalidateQueries({ queryKey: key });
  }
}

export function usePublishScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: ID; body: ScanPublishBody }) => scans.publish(id, body),
    onSuccess: () => invalidateAfterSharing(qc),
  });
}

export function useSaveHaves() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (items: ItemCreate[]) => api.items.batch({ items }),
    onSuccess: () => invalidateAfterSharing(qc),
  });
}
