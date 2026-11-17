"use client";

import { use, useEffect, type ReactNode } from "react";
import { browser } from "react-dom";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/api";

/** Renders children only when a login token exists; otherwise sends you to /login?next=<here>. */
export function AuthGate({ children }: { children: ReactNode }) {
  use(browser("The login token is stored in localStorage."));
  const router = useRouter();
  const token = getToken();

  useEffect(() => {
    if (!token) {
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      router.replace(`/login?next=${next}`);
    }
  }, [token, router]);

  if (!token) return null;
  return <>{children}</>;
}
