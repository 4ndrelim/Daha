"use client";

import { useQuery } from "@tanstack/react-query";
import { ReceiptText } from "lucide-react";
import { api } from "@/lib/api";
import { firstName } from "@/lib/format";
import { useMe } from "@/lib/queries/me";
import { formatUsd, NO_BONUS_TEXT, valueExchangeOn } from "@/lib/value";

/** Value exchange: a receipt in a completed exchange's chat. An estimate, never a payment. */
export function ValueReceiptCard({ txId }: { txId: number }) {
  const { data: me } = useMe();
  const on = valueExchangeOn(me);
  const tx = useQuery({ queryKey: ["transaction", txId], queryFn: () => api.transactions.get(txId), enabled: on });
  const t = tx.data;
  const v = t?.value;
  if (!on || !t || !v || t.status !== "completed" || v.value_usd == null) return null;
  const iOwn = t.my_role === "owner";
  const other = firstName(iOwn ? t.borrower.name : t.owner.name);

  return (
    <section className="space-y-1.5 rounded-2xl bg-points-soft p-3.5 text-[14px] ring-1 ring-reward-200" aria-label="Value receipt">
      <p className="flex items-center gap-1.5 font-semibold text-reward-900">
        <ReceiptText className="size-4.5 shrink-0" aria-hidden />
        Value exchanged: about {formatUsd(v.value_usd)}
      </p>
      {v.bonus_points > 0 ? (
        <p className="font-semibold text-reward-800">+{v.bonus_points} karma bonus points</p>
      ) : v.no_bonus_reason && (iOwn || t.kind === "exchange") ? (
        <p className="text-[13px] text-muted-foreground">{NO_BONUS_TEXT[v.no_bonus_reason]}</p>
      ) : null}
      <p className="text-[12px] text-muted-foreground">An estimated value, with {other}. No money changes hands in DAHA.</p>
    </section>
  );
}
