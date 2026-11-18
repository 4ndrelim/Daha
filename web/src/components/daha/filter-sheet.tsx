"use client";

import { useState } from "react";
import { SlidersHorizontal } from "lucide-react";
import { Sheet, SheetContent, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import type { Condition, TransactionType } from "@/lib/api/types";
import { CONDITION_LABEL, TX_TYPE_LABEL } from "@/lib/categories";
import { cn } from "@/lib/utils";

export interface Filters {
  max_walk_min: number | null;
  transaction_type: TransactionType | null;
  condition: Condition | null;
  available_only: boolean;
}

export const DEFAULT_FILTERS: Filters = { max_walk_min: null, transaction_type: null, condition: null, available_only: true };

export function activeFilterCount(f: Filters): number {
  return [f.max_walk_min !== null, f.transaction_type !== null, f.condition !== null, !f.available_only].filter(Boolean).length;
}

function Pills<T extends string | number>({ options, value, onChange, label }: {
  options: { value: T | null; label: string }[]; value: T | null; onChange: (v: T | null) => void; label: string;
}) {
  return (
    <fieldset>
      <legend className="mb-2 text-[13px] font-semibold text-muted-foreground">{label}</legend>
      <div className="flex flex-wrap gap-2">
        {options.map((o) => {
          const on = o.value === value;
          return (
            <button
              key={String(o.value)}
              type="button"
              aria-pressed={on}
              onClick={() => onChange(o.value)}
              className={cn(
                "h-11 rounded-full px-4 text-[15px] font-medium ring-1 transition",
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

export function FilterSheet({ value, onApply }: { value: Filters; onApply: (f: Filters) => void }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Filters>(value);
  const count = activeFilterCount(value);

  return (
    <>
      <button
        type="button"
        onClick={() => { setDraft(value); setOpen(true); }}
        className={cn(
          "relative flex h-10 items-center gap-1.5 rounded-full px-3.5 text-[14px] font-semibold ring-1",
          count ? "bg-primary-soft text-accent-foreground ring-primary/40" : "bg-card ring-border",
        )}
      >
        <SlidersHorizontal className="size-4" /> Filters{count ? ` · ${count}` : ""}
      </button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="bottom" className="mx-auto max-h-[85dvh] max-w-md overflow-y-auto rounded-t-3xl pb-[calc(1rem+env(safe-area-inset-bottom))]">
          <SheetHeader>
            <SheetTitle className="text-[17px]">Filters</SheetTitle>
          </SheetHeader>
          <div className="space-y-6 px-4">
            <Pills
              label="Walking distance"
              value={draft.max_walk_min}
              onChange={(v) => setDraft({ ...draft, max_walk_min: v })}
              options={[{ value: 5, label: "5 min" }, { value: 10, label: "10 min" }, { value: 15, label: "15 min" },
                { value: 30, label: "30 min" }, { value: null, label: "Any" }]}
            />
            <Pills
              label="Type"
              value={draft.transaction_type}
              onChange={(v) => setDraft({ ...draft, transaction_type: v })}
              options={[{ value: null, label: "Any" },
                ...(Object.keys(TX_TYPE_LABEL) as TransactionType[]).map((t) => ({ value: t, label: TX_TYPE_LABEL[t] }))]}
            />
            <Pills
              label="Condition"
              value={draft.condition}
              onChange={(v) => setDraft({ ...draft, condition: v })}
              options={[{ value: null, label: "Any" },
                ...(Object.keys(CONDITION_LABEL) as Condition[]).map((c) => ({ value: c, label: CONDITION_LABEL[c] }))]}
            />
            <label className="flex min-h-12 items-center justify-between gap-3">
              <span>
                <span className="block font-medium">Available now only</span>
                <span className="block text-[13px] text-muted-foreground">Hide things that are lent out or reserved</span>
              </span>
              <Switch checked={draft.available_only} onCheckedChange={(v) => setDraft({ ...draft, available_only: v })} />
            </label>
          </div>
          <SheetFooter className="flex-row gap-2 px-4">
            <button type="button" onClick={() => setDraft(DEFAULT_FILTERS)} className="h-12 flex-1 rounded-full font-semibold ring-1 ring-border active:bg-muted">
              Reset
            </button>
            <button
              type="button"
              onClick={() => { onApply(draft); setOpen(false); }}
              className="h-12 flex-[2] rounded-full bg-primary font-semibold text-primary-foreground active:bg-primary-hover"
            >
              Show results
            </button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </>
  );
}
