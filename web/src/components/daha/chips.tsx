import { Footprints, Gem } from "lucide-react";
import type { Category, ItemStatus, TransactionType } from "@/lib/api/types";
import { categoryInfo, STATUS_LABEL, TX_TYPE_LABEL } from "@/lib/categories";
import { cn } from "@/lib/utils";
import { worthChip } from "@/lib/value";

const chip = "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[12px] font-medium leading-5 whitespace-nowrap";

const TX_STYLE: Record<TransactionType, string> = {
  lend: "bg-brand-50 text-brand-700",
  give: "bg-reward-50 text-reward-700",
  exchange: "bg-sky-50 text-sky-700",
};

export function TxTypeChip({ type, className }: { type: TransactionType; className?: string }) {
  return <span className={cn(chip, TX_STYLE[type], className)}>{TX_TYPE_LABEL[type]}</span>;
}

const STATUS_STYLE: Record<ItemStatus, string> = {
  available: "bg-brand-50 text-brand-700",
  reserved: "bg-reward-50 text-reward-700",
  borrowed: "bg-stone-100 text-stone-600",
  unavailable: "bg-stone-100 text-stone-500",
};

export function StatusBadge({ status, className }: { status: ItemStatus; className?: string }) {
  return <span className={cn(chip, STATUS_STYLE[status], className)}>{STATUS_LABEL[status]}</span>;
}

export function DistanceChip({ min, label, className }: { min: number | null; label?: string; className?: string }) {
  if (min === null && !label) return null;
  return (
    <span className={cn("inline-flex items-center gap-1 text-[13px] text-muted-foreground", className)}>
      {min !== null && <Footprints className="size-3.5" aria-hidden />}
      {[min !== null ? `${min} min` : null, label].filter(Boolean).join(" · ")}
    </span>
  );
}

export function CategoryChip({ category, className }: { category: Category | null; className?: string }) {
  const c = categoryInfo(category);
  return <span className={cn(chip, "bg-muted text-foreground", className)}>{c.emoji} {c.label}</span>;
}

/** Neutral chip for parsed attributes ("black binder", "Wed Nov 25", "Borrow"). */
export function InfoChip({ children, className }: { children: React.ReactNode; className?: string }) {
  return <span className={cn(chip, "bg-primary-soft text-accent-foreground", className)}>{children}</span>;
}

/** Value exchange: "Worth about $X" (always an estimate) and, at $100+, "High value". */
export function ValueChips({ value, high, className }: { value: number | null | undefined; high?: boolean; className?: string }) {
  if (value == null) return null;
  return (
    <span className={cn("flex flex-wrap items-center gap-1", className)}>
      <span className={cn(chip, "bg-reward-50 text-reward-800 tabular-nums")}>{worthChip(value)}</span>
      {high && <span className={cn(chip, "bg-brand-50 text-brand-700")}><Gem className="size-3" aria-hidden /> High value</span>}
    </span>
  );
}
