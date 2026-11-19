"use client";

import Link from "next/link";
import { useState } from "react";
import { AlertTriangle, CalendarClock, Check, Lock, MapPin, Star } from "lucide-react";
import { format, parseISO } from "date-fns";
import type { Transaction, TxAction, TxStatus } from "@/lib/api/types";
import { firstName, shortDate } from "@/lib/format";
import { useTxAction } from "@/lib/queries/transactions";
import { ItemThumb } from "./item-thumb";
import { TxTypeChip } from "./chips";
import { ReviewSheet } from "./review-sheet";
import { cn } from "@/lib/utils";

export function actionLabel(action: TxAction, tx: Transaction): string {
  switch (action) {
    case "accept": return "Accept";
    case "decline": return "Decline";
    case "cancel": return "Cancel";
    case "hand_off": return tx.kind === "lend" ? "Mark handed off" : "Mark given";
    case "mark_returned": return "Got it back";
  }
}

const PRIMARY: TxAction[] = ["accept", "hand_off", "mark_returned"];

function steps(tx: Transaction): string[] {
  const first = tx.initiated_by === "owner" ? "Offered" : "Requested";
  return tx.kind === "lend" ? [first, "Accepted", "Handed off", "Returned"] : [first, "Accepted", tx.kind === "give" ? "Given" : "Swapped"];
}

function stepIndex(status: TxStatus, kind: Transaction["kind"]): number {
  if (status === "accepted") return 1;
  if (status === "handed_off") return 2;
  if (status === "completed") return kind === "lend" ? 3 : 2;
  return 0;
}

function statusLine(tx: Transaction): string {
  const other = firstName(tx.my_role === "owner" ? tx.borrower.name : tx.owner.name);
  const iOwn = tx.my_role === "owner";
  switch (tx.status) {
    case "requested": return iOwn ? `${other} wants this. Accept?` : `Waiting for ${other} to accept`;
    case "offered": return iOwn ? `Waiting for ${other} to accept your offer` : `${other} offered this. Accept?`;
    case "accepted": return tx.kind === "lend" ? "Accepted! Meet up and hand it over" : "Accepted! Meet up to hand it over";
    case "handed_off": return iOwn ? `${other} has it. Tap "Got it back" when it's returned` : `You have it${tx.due_date ? `, back by ${shortDate(tx.due_date)}` : ""}`;
    case "completed": return "All done 🎉";
    case "declined": return "Declined";
    case "cancelled": return "Cancelled";
  }
}

/** Pinned at the top of a transaction chat: item, progress stepper, pickup info, and one button per allowed action. */
export function TransactionCard({ tx, compact = false }: { tx: Transaction; compact?: boolean }) {
  const act = useTxAction();
  const [review, setReview] = useState(false);
  const labels = steps(tx);
  const idx = stepIndex(tx.status, tx.kind);
  const ended = tx.status === "declined" || tx.status === "cancelled";
  const other = tx.my_role === "owner" ? tx.borrower : tx.owner;

  return (
    <div className="rounded-2xl bg-card p-3.5 shadow-sm ring-1 ring-border/60">
      <div className="flex items-center gap-3">
        <Link href={`/items/${tx.item.id}`} className="shrink-0" aria-label={`Open ${tx.item.name}`}>
          <ItemThumb url={tx.item.thumbnail_url} category={tx.item.category} className="size-12 rounded-xl" emojiClassName="text-2xl" />
        </Link>
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-1.5">
            <span className="truncate font-semibold">{tx.item.name}</span>
            <TxTypeChip type={tx.kind} />
          </p>
          <p className="truncate text-[13px] text-muted-foreground">
            {tx.my_role === "owner" ? `To ${other.name}` : `From ${other.name}`}
            {tx.start_date && ` · ${shortDate(tx.start_date)}`}
            {tx.due_date && ` → ${shortDate(tx.due_date)}`}
          </p>
        </div>
      </div>

      {!ended && (
        <ol className="mt-3.5 flex items-center" aria-label="Progress">
          {labels.map((label, i) => {
            const done = i < idx || tx.status === "completed";
            const current = i === idx && tx.status !== "completed";
            return (
              <li key={label} className="flex flex-1 items-center last:flex-none">
                <span className="flex flex-col items-center gap-1">
                  <span className={cn("flex size-6 items-center justify-center rounded-full text-[11px] font-bold",
                    done ? "bg-primary text-primary-foreground" : current ? "bg-primary-soft text-accent-foreground ring-2 ring-primary" : "bg-muted text-muted-foreground")}>
                    {done ? <Check className="size-3.5" strokeWidth={3} /> : i + 1}
                  </span>
                  <span className={cn("text-[11px] whitespace-nowrap", done || current ? "font-semibold text-foreground" : "text-muted-foreground")}>{label}</span>
                </span>
                {i < labels.length - 1 && <span className={cn("mx-1 mb-4 h-0.5 flex-1 rounded", i < idx ? "bg-primary" : "bg-border")} />}
              </li>
            );
          })}
        </ol>
      )}

      <p className={cn("mt-3 text-[14px] font-medium", ended && "text-muted-foreground")}>{statusLine(tx)}</p>

      {tx.is_overdue && (
        <p className="mt-2 flex items-center gap-1.5 rounded-xl bg-rose-50 px-3 py-2 text-[13px] font-medium text-rose-700">
          <AlertTriangle className="size-4" /> Overdue{tx.due_date ? ` since ${shortDate(tx.due_date)}` : ""}
        </p>
      )}

      {!compact && (tx.pickup_place || tx.pickup_note || tx.pickup_at) && (
        <div className="mt-3 space-y-1 rounded-xl bg-muted px-3 py-2 text-[13px]">
          {tx.pickup_at && <p className="flex items-center gap-1.5 font-medium"><CalendarClock className="size-3.5" /> {format(parseISO(tx.pickup_at), "EEE, MMM d 'at' h:mm a")}</p>}
          {tx.pickup_place && <p className="flex items-center gap-1.5"><MapPin className="size-3.5" /> {tx.pickup_place.name}</p>}
          {tx.pickup_note && <p className="flex items-start gap-1.5"><Lock className="mt-0.5 size-3.5 shrink-0" /> {tx.pickup_note}</p>}
        </div>
      )}

      {(tx.allowed_actions.length > 0 || tx.can_review) && (
        <div className="mt-3 flex flex-wrap gap-2">
          {tx.allowed_actions.map((a) => (
            <button
              key={a}
              type="button"
              disabled={act.isPending}
              onClick={() => act.mutate({ id: tx.id, action: a })}
              className={cn("h-11 flex-1 rounded-full px-4 text-[15px] font-semibold whitespace-nowrap disabled:opacity-60",
                PRIMARY.includes(a) ? "bg-primary text-primary-foreground active:bg-primary-hover" : "ring-1 ring-border active:bg-muted")}
            >
              {actionLabel(a, tx)}
            </button>
          ))}
          {tx.can_review && (
            <button type="button" onClick={() => setReview(true)}
              className="flex h-11 flex-1 items-center justify-center gap-1.5 rounded-full bg-points-soft px-4 font-semibold text-reward-800 ring-1 ring-reward-200">
              <Star className="size-4 fill-points text-points" /> Review {firstName(other.name)}
            </button>
          )}
        </div>
      )}
      {tx.can_review && <ReviewSheet tx={tx} open={review} onOpenChange={setReview} />}
    </div>
  );
}
