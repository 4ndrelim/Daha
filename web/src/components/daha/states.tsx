import Link from "next/link";
import type { ReactNode } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export function SectionHeader({ title, action, className }: { title: string; action?: ReactNode; className?: string }) {
  return (
    <div className={cn("mb-2.5 flex items-center justify-between", className)}>
      <h2 className="text-[17px] font-semibold">{title}</h2>
      {action}
    </div>
  );
}

export function EmptyState({ emoji = "🌱", title, body, actionLabel, actionHref, className }: {
  emoji?: string; title: string; body?: string; actionLabel?: string; actionHref?: string; className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center rounded-2xl border border-dashed border-border px-6 py-8 text-center", className)}>
      <span className="text-3xl" aria-hidden>{emoji}</span>
      <p className="mt-2 font-medium">{title}</p>
      {body && <p className="mt-1 text-[13px] text-muted-foreground">{body}</p>}
      {actionLabel && actionHref && (
        <Link href={actionHref} className="mt-4 flex h-11 items-center rounded-full bg-primary px-5 font-semibold text-primary-foreground">
          {actionLabel}
        </Link>
      )}
    </div>
  );
}

export function ErrorState({ message = "Couldn't load this.", onRetry, className }: {
  message?: string; onRetry?: () => void; className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center rounded-2xl bg-rose-50 px-6 py-6 text-center", className)}>
      <p className="font-medium text-rose-700">{message}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="mt-3 h-11 rounded-full bg-card px-5 font-semibold text-rose-700 ring-1 ring-rose-200">
          Try again
        </button>
      )}
    </div>
  );
}

export function ItemGridSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="overflow-hidden rounded-2xl bg-card ring-1 ring-border/60">
          <Skeleton className="aspect-square rounded-none" />
          <div className="space-y-2 p-2.5"><Skeleton className="h-4 w-3/4" /><Skeleton className="h-4 w-1/2" /></div>
        </div>
      ))}
    </div>
  );
}

export function RequestListSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-4">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="flex gap-2.5">
          <Skeleton className="size-9 rounded-full" />
          <div className="flex-1 space-y-2"><Skeleton className="h-3 w-1/3" /><Skeleton className="h-14 w-full rounded-2xl" /></div>
        </div>
      ))}
    </div>
  );
}
