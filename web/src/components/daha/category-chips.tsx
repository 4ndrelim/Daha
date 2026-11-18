"use client";

import type { Category } from "@/lib/api/types";
import { CATEGORIES } from "@/lib/categories";
import { cn } from "@/lib/utils";

/** Horizontal, scrollable category toggles. Tapping the active one clears it. */
export function CategoryChips({ value, onChange, className }: {
  value: Category | null; onChange: (c: Category | null) => void; className?: string;
}) {
  return (
    <div className={cn("no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4", className)}>
      {CATEGORIES.map((c) => {
        const on = c.value === value;
        return (
          <button
            key={c.value}
            type="button"
            aria-pressed={on}
            onClick={() => onChange(on ? null : c.value)}
            className={cn(
              "flex h-10 shrink-0 items-center gap-1.5 rounded-full px-3.5 text-[14px] font-medium ring-1 transition",
              on ? "bg-foreground text-background ring-foreground" : "bg-card ring-border active:bg-muted",
            )}
          >
            <span aria-hidden>{c.emoji}</span>
            {c.label}
          </button>
        );
      })}
    </div>
  );
}
