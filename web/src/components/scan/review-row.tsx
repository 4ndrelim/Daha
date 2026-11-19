"use client";

import { Check, ChevronDown, ShieldAlert, Trash2 } from "lucide-react";
import type { Category, Condition, Me, TransactionType, Visibility } from "@/lib/api/types";
import { CATEGORIES, CONDITION_LABEL } from "@/lib/categories";
import { cn } from "@/lib/utils";
import { ValueInput } from "@/components/daha/value-input";
import { NativeSelect, Segmented, Stepper } from "./controls";
import { DetectionThumb } from "./thumbs";
import { NAME_MAX, type Row } from "./review-model";

export const TYPE_OPTIONS: { value: TransactionType; label: string; activeClass: string }[] = [
  { value: "lend", label: "Lend", activeClass: "text-emerald-700" },
  { value: "give", label: "Free", activeClass: "text-amber-700" },
  { value: "exchange", label: "Swap", activeClass: "text-sky-700" },
];

export function visibilityLabel(v: Visibility, me: Me | undefined): string {
  if (v === "dorm") return me?.dorm ? `My dorm (${me.dorm.name.split(" (")[0]})` : "My dorm";
  if (v === "campus") return "Campus";
  if (v === "groups") return "My groups";
  return "Private: ping me only";
}

export interface PhotoRef { url: string | null; width: number | null; height: number | null }

export function ReviewRow({ row, bbox, photo, type, visibility, defaultVisibilityText, me, problem, onChange, onRemove }: {
  row: Row;
  bbox: [number, number, number, number] | null;
  photo: PhotoRef | null;
  type: TransactionType;
  visibility: Visibility;
  defaultVisibilityText: string;
  me: Me | undefined;
  problem: string | null;
  onChange: (patch: Partial<Row>) => void;
  onRemove?: () => void;
}) {
  const id = `row-${row.key}`;
  const isService = row.category === "services";
  return (
    <li className={cn(
      "rounded-2xl bg-card p-3 ring-1 transition",
      row.checked ? "ring-border/60 shadow-sm" : "ring-border/40",
      row.sensitive && !row.checked && "bg-amber-50/60 ring-amber-200",
    )}>
      <div className="flex items-center gap-2.5">
        <button
          type="button"
          role="checkbox"
          aria-checked={row.checked}
          aria-label={row.checked ? `Don't share ${row.name || "this"}` : `Share ${row.name || "this"}`}
          onClick={() => onChange({ checked: !row.checked })}
          className="-m-1.5 flex size-11 shrink-0 items-center justify-center"
        >
          <span className={cn(
            "flex size-6 items-center justify-center rounded-md border-2 transition",
            row.checked ? "border-primary bg-primary text-primary-foreground" : "border-stone-300 bg-card",
          )}>
            {row.checked && <Check className="size-4" strokeWidth={3} />}
          </span>
        </button>
        <DetectionThumb url={photo?.url ?? null} width={photo?.width ?? null} height={photo?.height ?? null}
          bbox={bbox} category={row.category} className="size-12 rounded-xl" />
        <input
          id={id}
          value={row.name}
          maxLength={NAME_MAX}
          onChange={(e) => onChange({ name: e.target.value })}
          placeholder="What is it?"
          aria-label="Item name"
          enterKeyHint="done"
          autoFocus={row.detectionId === null && row.name === ""}
          className={cn(
            "h-11 min-w-0 flex-1 rounded-xl border border-transparent bg-transparent px-2 text-base font-medium outline-none focus-visible:border-input focus-visible:bg-card",
            !row.checked && "text-muted-foreground",
          )}
        />
        {onRemove && (
          <button type="button" onClick={onRemove} aria-label="Remove this row" className="flex size-11 shrink-0 items-center justify-center text-muted-foreground">
            <Trash2 className="size-[18px]" />
          </button>
        )}
      </div>

      {row.sensitive && (
        <p className="mt-2 flex items-start gap-1.5 rounded-lg bg-amber-100/70 px-2.5 py-1.5 text-[13px] text-amber-900">
          <ShieldAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span>{row.sensitive}. Not shared unless you tick it.</span>
        </p>
      )}

      {row.checked && (
        <>
          <div className="mt-2.5 flex flex-wrap items-center gap-2">
            <NativeSelect
              aria-label="Category"
              value={row.category}
              onChange={(e) => onChange({ category: e.target.value as Category })}
              className="min-w-0 flex-1 basis-36"
            >
              {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.emoji} {c.label}</option>)}
            </NativeSelect>
            {me?.item_value_enabled && (
              <ValueInput value={row.value} estimate={row.valueIsEstimate}
                onChange={(value) => onChange({ value, valueIsEstimate: false })} className="w-36 shrink-0" />
            )}
            <Stepper label="Quantity" value={row.quantity} onChange={(quantity) => onChange({ quantity })} />
          </div>
          <Segmented
            label="How do you want to share it?"
            className="mt-2 flex w-full"
            value={type}
            onChange={(t) => onChange({ type: t })}
            options={TYPE_OPTIONS.map((o) => ({ ...o, disabled: o.value === "lend" && isService }))}
          />
          {isService && <p className="mt-1 text-[12px] text-muted-foreground">Services are Free or Swap, never Lend.</p>}

          <button
            type="button"
            onClick={() => onChange({ open: !row.open })}
            aria-expanded={row.open}
            aria-controls={`${id}-more`}
            className="mt-1 flex h-10 items-center gap-1 text-[13px] font-medium text-muted-foreground"
          >
            <ChevronDown className={cn("size-4 transition", row.open && "rotate-180")} aria-hidden />
            {row.open ? "Less" : "Description, condition, who sees it"}
            {!row.open && row.visibility && <span className="text-primary"> · {visibilityLabel(visibility, me)}</span>}
          </button>

          {row.open && (
            <div id={`${id}-more`} className="space-y-2.5 pt-1">
              <textarea
                value={row.description}
                onChange={(e) => onChange({ description: e.target.value })}
                placeholder="Anything people should know? (size, color, how it works)"
                aria-label="Description"
                rows={2}
                maxLength={1000}
                className="w-full resize-none rounded-xl border border-input bg-card px-3 py-2.5 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30"
              />
              <div className="grid grid-cols-2 gap-2">
                <NativeSelect
                  aria-label="Condition"
                  value={row.condition ?? ""}
                  onChange={(e) => onChange({ condition: (e.target.value || null) as Condition | null })}
                >
                  <option value="">Condition: not set</option>
                  {(Object.keys(CONDITION_LABEL) as Condition[]).map((c) => <option key={c} value={c}>{CONDITION_LABEL[c]}</option>)}
                </NativeSelect>
                <NativeSelect
                  aria-label="Who sees it"
                  value={row.visibility ?? ""}
                  onChange={(e) => onChange({ visibility: (e.target.value || null) as Row["visibility"] })}
                >
                  <option value="">{defaultVisibilityText}</option>
                  {me?.dorm && <option value="dorm">{visibilityLabel("dorm", me)}</option>}
                  <option value="campus">Campus</option>
                  <option value="private">Private: ping me only</option>
                </NativeSelect>
              </div>
            </div>
          )}
        </>
      )}

      {problem && row.checked && <p className="mt-1.5 text-[13px] text-destructive">{problem}</p>}
    </li>
  );
}
