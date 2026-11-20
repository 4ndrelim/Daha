"use client";

// "Available from" / "Until" for a listing (docs/plans/availability-dates.md). Both optional.
// Used by the item form and by the scan review's shared defaults. Stacks on narrow phones.

import { CalendarDays } from "lucide-react";
import { campusToday, datesProblem, dayLabel } from "@/lib/availability";
import { fieldClass } from "@/components/daha/form";
import { cn } from "@/lib/utils";

export function AvailabilityFields({ idPrefix, from, until, onChange }: {
  idPrefix: string; from: string; until: string;
  onChange: (patch: { from?: string; until?: string }) => void;
}) {
  const today = campusToday();
  const problem = datesProblem(from, until, today);
  const summary = !from && !until ? "Leave empty if it's available anytime."
    : problem ? null
    : from && from > today ? `People see “Available from ${dayLabel(from)}” and can ask ahead.`
    : until ? `Shown until ${dayLabel(until)}, then it's hidden from search.`
    : "Available now.";
  const label = "block text-[13px] font-medium";
  const hintId = `${idPrefix}-dates-hint`;
  return (
    <fieldset className="min-w-0 space-y-1.5">
      <legend className="mb-1.5 flex items-center gap-1 text-[13px] font-medium">
        <CalendarDays className="size-3.5" aria-hidden /> When is it available? <span className="font-normal text-muted-foreground">(optional)</span>
      </legend>
      <div className="grid grid-cols-1 gap-3 min-[380px]:grid-cols-2">
        <div className="min-w-0 space-y-1">
          <label htmlFor={`${idPrefix}-from`} className={label}>Available from</label>
          <input id={`${idPrefix}-from`} type="date" value={from} min={today} aria-describedby={hintId}
            onChange={(e) => onChange({ from: e.target.value })} className={cn(fieldClass, "min-w-0")} />
        </div>
        <div className="min-w-0 space-y-1">
          <label htmlFor={`${idPrefix}-until`} className={label}>Until</label>
          <input id={`${idPrefix}-until`} type="date" value={until} min={from && from > today ? from : today} aria-invalid={!!problem} aria-describedby={hintId}
            onChange={(e) => onChange({ until: e.target.value })} className={cn(fieldClass, "min-w-0")} />
        </div>
      </div>
      <div id={hintId} className="flex items-start justify-between gap-2">
        {problem
          ? <p role="alert" className="text-[13px] text-destructive">{problem}</p>
          : <p className="text-[13px] text-muted-foreground">{summary}</p>}
        {(from || until) && (
          <button type="button" onClick={() => onChange({ from: "", until: "" })}
            className="-my-2 inline-flex min-h-11 shrink-0 items-center px-1 text-[13px] font-semibold text-primary">
            Clear dates
          </button>
        )}
      </div>
    </fieldset>
  );
}
