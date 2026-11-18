"use client";

import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { cn } from "@/lib/utils";

/** Installed (full-screen) apps have no browser back button, so detail pages bring their own. */
export function BackButton({ fallback = "/home", className, floating = false }: { fallback?: string; className?: string; floating?: boolean }) {
  const router = useRouter();
  return (
    <button
      type="button"
      aria-label="Back"
      onClick={() => (window.history.length > 1 ? router.back() : router.push(fallback))}
      className={cn(
        "flex size-11 items-center justify-center rounded-full",
        floating ? "bg-card/90 shadow-md ring-1 ring-border/60 backdrop-blur" : "-ml-2 active:bg-muted",
        className,
      )}
    >
      <ArrowLeft className="size-5" />
    </button>
  );
}
