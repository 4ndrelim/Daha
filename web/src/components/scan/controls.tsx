"use client";

import type { ComponentProps, ReactNode } from "react";
import { ChevronDown, Minus, Plus } from "lucide-react";
import { cn } from "@/lib/utils";

/** Native <select>: the phone's own picker, 16 px text (no iOS zoom), 44 px tall. */
export function NativeSelect({ className, children, ...props }: ComponentProps<"select">) {
  return (
    <span className={cn("relative inline-flex min-w-0", className)}>
      <select
        {...props}
        className="h-11 w-full min-w-0 appearance-none truncate rounded-xl border border-input bg-card pr-8 pl-3 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30 disabled:opacity-60"
      >
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute top-1/2 right-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
    </span>
  );
}

export function Stepper({ value, onChange, min = 1, max = 99, label }: {
  value: number; onChange: (v: number) => void; min?: number; max?: number; label: string;
}) {
  const btn = "flex size-11 items-center justify-center text-foreground disabled:opacity-30 active:bg-muted";
  return (
    <div className="inline-flex h-11 shrink-0 items-center overflow-hidden rounded-xl border border-input bg-card" role="group" aria-label={label}>
      <button type="button" className={btn} onClick={() => onChange(Math.max(min, value - 1))} disabled={value <= min} aria-label="Fewer">
        <Minus className="size-4" />
      </button>
      <span className="w-6 text-center text-[15px] font-medium tabular-nums" aria-live="polite">{value}</span>
      <button type="button" className={btn} onClick={() => onChange(Math.min(max, value + 1))} disabled={value >= max} aria-label="More">
        <Plus className="size-4" />
      </button>
    </div>
  );
}

export interface SegmentOption<T extends string> { value: T; label: ReactNode; disabled?: boolean; activeClass?: string }

/** A row of pill buttons, one selected (Lend / Free / Swap, My dorm / Campus / …). */
export function Segmented<T extends string>({ value, options, onChange, label, className, size = "md" }: {
  value: T; options: SegmentOption<T>[]; onChange: (v: T) => void; label: string; className?: string; size?: "sm" | "md";
}) {
  return (
    <div role="radiogroup" aria-label={label} className={cn("inline-flex gap-1 rounded-full bg-muted p-1", className)}>
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={on}
            disabled={o.disabled}
            onClick={() => onChange(o.value)}
            className={cn(
              "flex flex-1 items-center justify-center gap-1 rounded-full font-medium whitespace-nowrap transition disabled:opacity-35",
              size === "sm" ? "h-9 px-3 text-[13px]" : "h-10 px-3.5 text-[14px]",
              on ? cn("bg-card text-foreground shadow-sm", o.activeClass) : "text-muted-foreground",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
