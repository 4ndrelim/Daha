"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Star } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import type { ReviewCreate, Transaction } from "@/lib/api/types";
import { firstName } from "@/lib/format";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { fieldClass, PrimaryButton } from "./form";
import { cn } from "@/lib/utils";

const WORDS = ["", "Not great", "Okay", "Good", "Great", "Amazing"];

export function ReviewSheet({ tx, open, onOpenChange }: { tx: Transaction; open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient();
  const other = tx.my_role === "owner" ? tx.borrower : tx.owner;
  const [rating, setRating] = useState<ReviewCreate["rating"] | 0>(0);
  const [body, setBody] = useState("");
  const send = useMutation({
    mutationFn: () => api.transactions.review(tx.id, { rating: rating as ReviewCreate["rating"], body: body.trim() || null }),
    onSuccess: () => {
      qc.setQueryData<Transaction>(["transaction", tx.id], (t) => (t ? { ...t, can_review: false } : t));
      qc.invalidateQueries({ queryKey: ["transaction", tx.id] });
      qc.invalidateQueries({ queryKey: ["me"] });
      toast.success(`Thanks! ${firstName(other.name)} will see your review.`);
      onOpenChange(false);
    },
    onError: (e) => toast.error(e instanceof ApiError && e.status === 409 ? "You already reviewed this one." : "Couldn't send. Try again?"),
  });
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="mx-auto max-w-md rounded-t-3xl pb-[calc(1rem+env(safe-area-inset-bottom))]">
        <SheetHeader><SheetTitle className="text-[17px]">How was it with {firstName(other.name)}?</SheetTitle></SheetHeader>
        <form onSubmit={(e) => { e.preventDefault(); if (rating) send.mutate(); }} className="space-y-4 px-4">
          <div className="flex flex-col items-center gap-1">
            <div className="flex gap-1" role="radiogroup" aria-label="Rating">
              {([1, 2, 3, 4, 5] as const).map((n) => (
                <button key={n} type="button" role="radio" aria-checked={rating === n} aria-label={`${n} star${n > 1 ? "s" : ""}`}
                  onClick={() => setRating(n)} className="flex size-12 items-center justify-center">
                  <Star className={cn("size-9 transition", n <= rating ? "fill-points text-points" : "text-border")} />
                </button>
              ))}
            </div>
            <p className="h-5 text-[13px] text-muted-foreground">{WORDS[rating]}</p>
          </div>
          <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={3} maxLength={500}
            placeholder="Optional: on time, item as described, friendly…" aria-label="Review" className={cn(fieldClass, "h-auto py-3")} />
          <PrimaryButton type="submit" disabled={!rating} loading={send.isPending}>Send review</PrimaryButton>
        </form>
      </SheetContent>
    </Sheet>
  );
}
