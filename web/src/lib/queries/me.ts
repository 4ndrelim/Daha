"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export const meKey = ["me"] as const;

export function useMe() {
  return useQuery({ queryKey: meKey, queryFn: () => api.me.get() });
}
