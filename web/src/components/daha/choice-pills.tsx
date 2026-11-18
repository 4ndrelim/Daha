"use client";

import { cn } from "@/lib/utils";

export interface Choice<T> { value: T; label: string; hint?: string; disabled?: boolean }

/** Single-choice pill buttons (44 px tall). */
export function ChoicePills<T extends string | number | null>({ options, value, onChange, label, className }: {
  options: Choice<T>[]; value: T; onChange: (v: T) => void; label?: string; className?: string;
}) {
  return (
    <fieldset className={className}>
      {label && <legend className="mb-2 text-[13px] font-semibold text-muted-foreground">{label}</legend>}
      <div className="flex flex-wrap gap-2">
        {options.map((o) => {
          const on = o.value === value;
          return (
            <button
              key={String(o.value)}
              type="button"
              aria-pressed={on}
              disabled={o.disabled}
              title={o.hint}
              onClick={() => onChange(o.value)}
              className={cn(
                "h-11 rounded-full px-4 text-[15px] font-medium ring-1 transition disabled:opacity-40",
                on ? "bg-primary text-primary-foreground ring-primary" : "bg-card ring-border active:bg-muted",
              )}
            >
              {o.label}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
