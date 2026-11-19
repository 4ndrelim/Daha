"use client";

import { X } from "lucide-react";
import { parseValue } from "@/lib/value";
import { cn } from "@/lib/utils";

/** Optional "Value" in whole US dollars. `estimate` marks a number the AI suggested and nobody changed. */
export function ValueInput({ id, value, onChange, estimate = false, className }: {
  id?: string; value: number | null; onChange: (v: number | null) => void; estimate?: boolean; className?: string;
}) {
  return (
    <span className={cn("relative inline-flex min-w-0 items-center", className)}>
      <span className="pointer-events-none absolute left-3 text-base text-muted-foreground" aria-hidden>$</span>
      <input
        id={id}
        type="text"
        inputMode="numeric"
        autoComplete="off"
        enterKeyHint="done"
        value={value === null ? "" : String(value)}
        onChange={(e) => onChange(parseValue(e.target.value))}
        placeholder="Value"
        aria-label={estimate ? "Value in US dollars, an AI estimate you can change" : "Value in US dollars (optional)"}
        className={cn(
          "h-11 w-full min-w-0 rounded-xl border border-input bg-card pl-6 text-base outline-none tabular-nums placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30",
          value !== null ? "pr-10" : "pr-3",
        )}
      />
      {estimate && value !== null && (
        <span className="pointer-events-none absolute -top-2 left-2.5 rounded-full bg-muted px-1.5 text-[11px] leading-4 font-semibold text-muted-foreground ring-2 ring-card">estimate</span>
      )}
      {value !== null && (
        <button type="button" onClick={() => onChange(null)} aria-label="Clear the value"
          className="absolute right-0 flex size-11 items-center justify-center text-muted-foreground">
          <X className="size-4" />
        </button>
      )}
    </span>
  );
}
