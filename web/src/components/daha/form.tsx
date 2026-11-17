import type { ComponentProps, ReactNode } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export const fieldClass =
  "h-12 w-full rounded-xl border border-input bg-card px-3.5 text-base outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30 aria-invalid:border-destructive";

export function Field({ label, hint, error, htmlFor, children }: {
  label: string; hint?: ReactNode; error?: string; htmlFor: string; children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="text-[13px] font-medium">{label}</label>
      {children}
      {error ? <p className="text-[13px] text-destructive">{error}</p> : hint ? <p className="text-[13px] text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

export function PrimaryButton({ loading, children, className, disabled, ...props }: ComponentProps<"button"> & { loading?: boolean }) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={cn(
        "flex h-12 w-full items-center justify-center gap-2 rounded-full bg-primary px-5 text-[15px] font-semibold text-primary-foreground transition hover:bg-primary-hover active:scale-[0.99] disabled:opacity-60",
        className,
      )}
    >
      {loading && <Loader2 className="size-4 animate-spin" />}
      {children}
    </button>
  );
}
