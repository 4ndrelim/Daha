"use client";

import { useRef } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, Check, CircleCheck, Eye, FlaskConical, Loader2, MessageCircle, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import type { ConditionCheck, ConditionPhotos, ConditionSlot, ConditionStage, Transaction } from "@/lib/api/types";
import { CONDITION_CHECK } from "@/lib/condition";
import { firstName } from "@/lib/format";
import { downscaleImage } from "@/lib/image";
import { cn } from "@/lib/utils";

/** The same 3 shots every time, so before and after line up. */
const SHOTS: { slot: ConditionSlot; label: string; hint: string }[] = [
  { slot: "front", label: "Front", hint: "Whole item, straight on" },
  { slot: "back", label: "Back", hint: "Turn it around" },
  { slot: "marks", label: "Marks", hint: "Close-up of any existing marks" },
];

function useConditionMutation<T>(fn: (v: T) => Promise<Transaction>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (tx) => qc.setQueryData(["transaction", tx.id], tx),
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : "Didn't work. Try again?"),
  });
}

function PhotoSlot({ label, hint, url, guide, editable, busy, onPick }: {
  label: string; hint: string; url: string | null; guide?: string | null; editable: boolean; busy: boolean; onPick: (f: File) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const shown = url ?? guide ?? null;
  const body = (
    <>
      <span className="relative block aspect-square w-full overflow-hidden rounded-xl bg-muted ring-1 ring-border/60">
        {shown && (
          // eslint-disable-next-line @next/next/no-img-element -- local uploads, already small
          <img src={shown} alt={url ? `${label} photo` : ""} className={cn("size-full object-cover", !url && "opacity-35")} />
        )}
        <span className="absolute inset-0 flex items-center justify-center">
          {busy ? <Loader2 className="size-5 animate-spin" />
            : url ? (editable && <span className="rounded-full bg-card/90 px-2 py-0.5 text-[11px] font-semibold shadow-sm">Retake</span>)
            : editable ? <span className="flex size-9 items-center justify-center rounded-full bg-primary text-primary-foreground shadow"><Camera className="size-4" /></span>
            : <span className="text-[11px] text-muted-foreground">Not yet</span>}
        </span>
        {url && <Check className="absolute top-1.5 right-1.5 size-4 rounded-full bg-primary p-0.5 text-primary-foreground" strokeWidth={3} aria-hidden />}
      </span>
      <span className="mt-1 block text-[12px] font-semibold">{label}</span>
      <span className="block text-[11px] leading-tight text-muted-foreground">{hint}</span>
    </>
  );
  if (!editable) return <div className="min-w-0">{body}</div>;
  return (
    <button type="button" disabled={busy} onClick={() => input.current?.click()} className="min-w-0 text-left disabled:opacity-70"
      aria-label={`${url ? "Retake" : "Take"} the ${label.toLowerCase()} photo: ${hint}`}>
      {body}
      <input ref={input} type="file" accept="image/*" capture="environment" hidden
        onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) onPick(f); }} />
    </button>
  );
}

function PhotoRow({ tx, stage, photos, guide, editable }: {
  tx: Transaction; stage: ConditionStage; photos: ConditionPhotos; guide?: ConditionPhotos; editable: boolean;
}) {
  const upload = useConditionMutation(async ({ slot, file }: { slot: ConditionSlot; file: File }) =>
    api.transactions.conditionPhoto(tx.id, stage, slot, await downscaleImage(file)));
  return (
    <div className="grid grid-cols-3 gap-2.5">
      {SHOTS.map((s) => (
        <PhotoSlot key={s.slot} label={s.label} hint={s.hint} url={photos[s.slot]} guide={guide?.[s.slot]} editable={editable}
          busy={upload.isPending && upload.variables?.slot === s.slot} onPick={(file) => upload.mutate({ slot: s.slot, file })} />
      ))}
    </div>
  );
}

function count(p: ConditionPhotos) {
  return SHOTS.filter((s) => p[s.slot]).length;
}

function focusComposer(tx: Transaction, push: (href: string) => void) {
  const box = document.querySelector<HTMLTextAreaElement>('textarea[aria-label="Message"]');
  if (box) {
    box.focus();
    box.scrollIntoView({ block: "center", behavior: "smooth" });
  } else {
    push(`/messages/${tx.conversation_id}`);
  }
}

function Result({ tx, c }: { tx: Transaction; c: ConditionCheck }) {
  const retry = useConditionMutation(() => api.transactions.conditionCompare(tx.id));
  const router = useRouter();
  if (c.status === "checking") {
    return (
      <p className="flex items-center gap-2 rounded-2xl bg-muted px-3.5 py-3 text-[14px] font-medium" role="status">
        <Loader2 className="size-4 animate-spin" /> Comparing the before and after photos…
      </p>
    );
  }
  if (c.status !== "done" && c.status !== "failed") return null;
  const same = c.status === "done" && c.result === "no_changes";
  return (
    <div className={cn("rounded-2xl px-3.5 py-3 ring-1", same ? "bg-points-soft ring-reward-200" : "bg-card ring-border")} role="status">
      {c.sample && (
        <p className="mb-2 inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
          <FlaskConical className="size-3" /> Sample result, not a real check
        </p>
      )}
      <p className="flex items-center gap-2 font-semibold">
        {c.status === "failed" ? <Eye className="size-5" /> : same ? <CircleCheck className="size-5 text-reward-700" /> : <Eye className="size-5 text-primary" />}
        {c.status === "failed" ? "Couldn't compare this time" : same ? "No changes spotted" : "Possible changes"}
      </p>
      {c.note && <p className="mt-1 text-[14px]">{c.note}</p>}
      {c.status === "done" && !same && <p className="mt-1 text-[13px] text-muted-foreground">An AI guess from photos. Look together and decide.</p>}
      <div className="mt-3 flex flex-wrap gap-2">
        {c.status === "failed" && !c.photos_deleted && (
          <button type="button" onClick={() => retry.mutate(undefined)} disabled={retry.isPending}
            className="h-11 flex-1 rounded-full bg-primary px-4 font-semibold text-primary-foreground disabled:opacity-60">Try again</button>
        )}
        <button type="button" onClick={() => focusComposer(tx, router.push)}
          className="flex h-11 flex-1 items-center justify-center gap-1.5 rounded-full px-4 font-semibold ring-1 ring-border active:bg-muted">
          <MessageCircle className="size-4" /> Disagree? Message them
        </button>
      </div>
      <p className="mt-2 text-[12px] text-muted-foreground">Doesn&apos;t change anyone&apos;s points or reviews.</p>
    </div>
  );
}

/** Condition check for a loan: guided photos at handoff and return, then one shared result. */
export function ConditionCheckCard({ txId }: { txId: number }) {
  const tx = useQuery({
    queryKey: ["transaction", txId],
    queryFn: () => api.transactions.get(txId),
    // Poll quickly only while the comparison runs.
    refetchInterval: (q) => (q.state.data?.condition?.status === "checking" ? 2500 : false),
  });
  const confirm = useConditionMutation(() => api.transactions.conditionConfirm(txId));
  const t = tx.data;
  const c = t?.condition;
  if (!CONDITION_CHECK || !t || !c) return null;
  if (t.status === "requested" || t.status === "offered" || ((t.status === "declined" || t.status === "cancelled") && !c.result)) return null;

  const iOwn = t.my_role === "owner";
  const lender = firstName(t.owner.name), borrower = firstName(t.borrower.name);
  const handoffCount = count(c.handoff_photos), returnCount = count(c.return_photos);
  const showReturn = t.status === "handed_off" || returnCount > 0 || c.status !== "waiting";

  return (
    <section className="space-y-3 rounded-2xl bg-card p-3.5 shadow-sm ring-1 ring-border/60" aria-label="Condition check">
      <div>
        <h2 className="flex items-center gap-1.5 font-semibold"><ShieldCheck className="size-4.5 text-primary" /> Condition check</h2>
        <p className="text-[13px] text-muted-foreground">Same 3 photos at handoff and at return, so you both know how it started.</p>
      </div>

      {c.photos_deleted ? (
        <p className="text-[13px] text-muted-foreground">The photos were deleted when the loan ended. Only the result is kept.</p>
      ) : (
        <>
          <p className="rounded-xl bg-muted px-3 py-2 text-[12px] text-muted-foreground">
            📷 Photos of the item only: no faces, room numbers or documents. They&apos;re deleted when the loan ends.
          </p>

          <div className="space-y-2">
            <p className="text-[13px] font-semibold">
              At handoff · {iOwn ? "you snap" : `${lender} snaps`} <span className="font-normal text-muted-foreground">({handoffCount}/3)</span>
            </p>
            <PhotoRow tx={t} stage="handoff" photos={c.handoff_photos} editable={c.can_add_handoff_photos} />
            {c.handoff_confirmed_at ? (
              <p className="flex items-center gap-1.5 text-[13px] font-medium text-reward-800"><Check className="size-4" /> {iOwn ? `${borrower} confirmed` : "You confirmed"} the starting condition</p>
            ) : c.can_confirm ? (
              <button type="button" onClick={() => confirm.mutate(undefined)} disabled={confirm.isPending}
                className="flex h-11 w-full items-center justify-center gap-1.5 rounded-full bg-primary font-semibold text-primary-foreground disabled:opacity-60">
                <Check className="size-4" /> This looks right
              </button>
            ) : handoffCount === 3 ? (
              <p className="text-[13px] text-muted-foreground">Waiting for {borrower} to confirm the photos.</p>
            ) : !iOwn ? (
              <p className="text-[13px] text-muted-foreground">{lender} takes these when handing it over.</p>
            ) : null}
          </div>

          {showReturn && handoffCount === 3 && (
            <div className="space-y-2">
              <p className="text-[13px] font-semibold">
                At return · {iOwn ? `${borrower} snaps` : "you snap"} the same 3 <span className="font-normal text-muted-foreground">({returnCount}/3)</span>
              </p>
              <PhotoRow tx={t} stage="return" photos={c.return_photos} guide={c.handoff_photos} editable={c.can_add_return_photos} />
            </div>
          )}
        </>
      )}

      <Result tx={t} c={c} />
    </section>
  );
}
