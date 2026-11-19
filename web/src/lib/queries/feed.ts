"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

/** Mutual matches for Home; `null` = the feature is off on this server. */
export function useMutualMatches() {
  return useQuery({ queryKey: ["feed", "mutual"], queryFn: () => api.matches.mutual(), retry: false });
}

export function useHomeFeed() {
  return useQuery({ queryKey: ["feed", "home"], queryFn: () => api.feed.home() });
}
