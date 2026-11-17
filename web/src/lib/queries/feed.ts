"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useHomeFeed() {
  return useQuery({ queryKey: ["feed", "home"], queryFn: () => api.feed.home() });
}
