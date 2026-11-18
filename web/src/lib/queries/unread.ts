"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

/** Bell + chat badges: poll unread counts every 20 s. */
export function useUnread() {
  return useQuery({ queryKey: ["unread"], queryFn: () => api.notifications.unreadCount(), refetchInterval: 20_000 });
}
