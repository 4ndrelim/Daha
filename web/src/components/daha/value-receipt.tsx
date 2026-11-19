"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Gem, ReceiptText, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import type { Transaction } from "@/lib/api/types";
import { firstName } from "@/lib/format";
import { useMe } from "@/lib/queries/me";
import { formatUsd, NO_BONUS_TEXT, valueExchangeOn } from "@/lib/value";
import { ValueInput } from "./value-input";

function Row({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-semibold tabular-nums">{value == null ? "Not given" : `about ${formatUsd(value)}`}</dd>
    </div>
  );
}

function SwapValueField({ tx }: { tx: Transaction }) {
  const qc = useQueryClient();
  const [value, setValue] = useState<number | null>(tx.value?.swap_value_usd ?? null);
  const save = useMutation({
    mutationFn: () => api.transactions.swapValue(tx.id, value),
    onSuccess: (t) => { qc.setQueryData(["transaction", t.id], t); toast.success("Saved"); },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : "Didn't save. Try again?"),
  });
  return (
    <div className="space-y-1.5">
      <label htmlFor={`swap-${tx.id}`} className="block text-[13px] font-medium">About what is your side worth?</label>
      <div className="flex gap-2">
        <ValueInput id={`swap-${tx.id}`} value={value} onChange={setValue} className="w-36" />
        <button type="button" onClick={() => save.mutate()} disabled={save.isPending || value === (tx.value?.swap_value_usd ?? null)}
          className="h-11 rounded-full px-4 font-semibold ring-1 ring-border active:bg-muted disabled:opacity-50">Save</button>
      </div>
    </div>
  );
}

/** Value exchange in a transaction's chat: estimates only, and never a payment. */
export function ValueReceiptCard({ txId }: { txId: number }) {
  const { data: me } = useMe();
  const tx = useQuery({ queryKey: ["transaction", txId], queryFn: () => api.transactions.get(txId), enabled: valueExchangeOn(me) });
  const t = tx.data;
  const v = t?.value;
  if (!valueExchangeOn(me) || !t || !v) return null;
  if (t.status === "declined" || t.status === "cancelled") return null;

  const iOwn = t.my_role === "owner";
  const other = firstName(iOwn ? t.borrower.name : t.owner.name);
  const done = t.status === "completed";

  // Before completion: only the useful nudges (High value, the swap's second side).
  if (!done) {
    if (!v.high_value && !v.can_set_swap_value && !v.needs_condition_check) return null;
    return (
      <section className="space-y-2.5 rounded-2xl bg-card p-3.5 text-[14px] shadow-sm ring-1 ring-border/60" aria-label="Estimated value">
        {v.high_value && (
          <p className="flex items-center gap-1.5 font-semibold"><Gem className="size-4 text-primary" aria-hidden /> High value · about {formatUsd(v.value_usd!)}</p>
        )}
        {v.needs_condition_check && (
          <p className="flex items-start gap-1.5 text-[13px] text-muted-foreground">
            <ShieldCheck className="mt-0.5 size-4 shrink-0" aria-hidden />
            Hand-off unlocks once the 3 condition photos are in and {iOwn ? other : "you"} confirmed them.
          </p>
        )}
        {v.can_set_swap_value && <SwapValueField tx={t} />}
      </section>
    );
  }

  const lines =
    t.kind === "lend" ? [{ label: iOwn ? "Value you lent" : "Value you borrowed", value: v.value_usd }]
    : t.kind === "give" ? [{ label: iOwn ? "Value you gave away" : "Value you were given", value: v.value_usd }]
    : [
      { label: iOwn ? "You gave" : "You got", value: v.value_usd },
      { label: iOwn ? "You got" : "You gave", value: v.swap_value_usd },
      ...(v.difference_usd != null ? [{ label: "Difference", value: v.difference_usd }] : []),
    ];

  return (
    <section className="space-y-2.5 rounded-2xl bg-points-soft p-3.5 text-[14px] ring-1 ring-reward-200" aria-label="Value receipt">
      <h2 className="flex items-center gap-1.5 font-semibold text-reward-900">
        <ReceiptText className="size-4.5" aria-hidden /> Value receipt
        {v.high_value && <span className="ml-auto inline-flex items-center gap-1 text-[12px] font-semibold text-reward-800"><Gem className="size-3" aria-hidden /> High value</span>}
      </h2>
      <dl className="space-y-1">{lines.map((l) => <Row key={l.label} {...l} />)}</dl>
      {v.bonus_points ? (
        <p className="font-semibold text-reward-800">+{v.bonus_points} value bonus points</p>
      ) : v.no_bonus_reason && (iOwn || t.kind === "exchange") ? (
        <p className="text-[13px] text-muted-foreground">{NO_BONUS_TEXT[v.no_bonus_reason]}</p>
      ) : null}
      <p className="text-[12px] text-muted-foreground">Estimated values with {other}. No money changes hands in DAHA.</p>
    </section>
  );
}
