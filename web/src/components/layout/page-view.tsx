"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { track } from "@/lib/api/endpoints/events";

/** Sends one `page_view` per route change (PLAN.md §7.6). Path only: the query string can hold typed text. */
export function PageView() {
  const path = usePathname();
  useEffect(() => {
    track("page_view", { path });
  }, [path]);
  return null;
}
