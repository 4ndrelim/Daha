"use client";

// Handoff coordinator (docs/plans/handoff-coordinator.md): "Suggest a time & place" in a
// transaction's chat. An agent reads the last few messages of THIS chat and proposes a time and
// an exchange spot. It only ever runs when someone taps the button. The person who asked sees a
// draft ("Send" / "Change"); the other person confirms with one tap.

import { useId, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Check, FlaskConical, Loader2, MapPin, Sparkles, X } from "lucide-react";
import { format, parseISO } from "date-fns";
import { toast } from "sonner";
import { api, ApiError, track } from "@/lib/api";
import type { HandoffSuggestion, Transaction } from "@/lib/api/types";
import { HANDOFF_COORDINATOR } from "@/lib/handoff";
import { firstName } from "@/lib/format";
import { cn } from "@/lib/utils";

const primary = "flex min-h-11 flex-1 items-center justify-center gap-1.5 rounded-full bg-primary px-4 font-semibold text-primary-foreground active:bg-primary-hover disabled:opacity-60";
const secondary = "flex min-h-11 flex-1 items-center justify-center gap-1.5 rounded-full px-4 font-semibold ring-1 ring-border active:bg-muted disabled:opacity-60";

function useHandoffMutation<T>(fn: (v: T) => Promise<Transaction>, onDone?: () => void) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (tx) => {
      qc.setQueryData(["transaction", tx.id], tx);
      qc.invalidateQueries({ queryKey: ["messages-poll", tx.conversation_id] });
      onDone?.();
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : "Didn't work. Try again?"),
  });
}

function when(iso: string): string {
  return format(parseISO(iso), "EEE, MMM d 'at' h:mm a");
}

/** "2026-11-19T16:30" for a datetime-local input, in the phone's own time zone. */
function localInput(d: Date): string {
  return format(d, "yyyy-MM-dd'T'HH:mm");
}

function WhenWhere({ s }: { s: HandoffSuggestion }) {
  return (
    <dl className="space-y-1 text-[15px]">
      <div className="flex items-start gap-2">
        <dt className="sr-only">Time</dt>
        <CalendarClock className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
        <dd className="font-semibold">{s.start_time ? when(s.start_time) : "No time yet"}</dd>
      </div>
      <div className="flex items-start gap-2">
        <dt className="sr-only">Place</dt>
        <MapPin className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
        <dd className="min-w-0 break-words">{s.place?.name ?? "No place yet"}</dd>
      </div>
    </dl>
  );
}

/** "Change": pick a time and one of the campus exchange spots by hand. */
function ChangeForm({ tx, start, onDone }: { tx: Transaction; start: HandoffSuggestion | null; onDone: () => void }) {
  const ids = useId();
  const places = useQuery({ queryKey: ["places"], queryFn: () => api.places.list(), staleTime: 60 * 60_000 });
  const [time, setTime] = useState(() => localInput(start?.start_time ? parseISO(start.start_time) : new Date(Date.now() + 2 * 60 * 60_000)));
  const [placeId, setPlaceId] = useState<number | "">(start?.place?.id ?? tx.pickup_place?.id ?? "");
  const send = useHandoffMutation(
    () => api.transactions.handoffSend(tx.id, { start_time: new Date(time).toISOString(), place_id: Number(placeId) }),
    () => { track("handoff_sent", { changed: true }); onDone(); },
  );
  const [late, setLate] = useState(false); // the picked time is not in the future (checked on submit)
  const valid = !!time && placeId !== "";
  const submit = () => {
    if (!valid) return;
    if (new Date(time).getTime() <= Date.now()) { setLate(true); return; }
    send.mutate(undefined);
  };
  const field = "h-12 w-full min-w-0 rounded-xl bg-card px-3 text-base ring-1 ring-border outline-none focus-visible:ring-2 focus-visible:ring-ring";
  return (
    <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); submit(); }}>
      <div className="space-y-1">
        <label htmlFor={`${ids}-time`} className="block text-[13px] font-medium">Time</label>
        <input id={`${ids}-time`} type="datetime-local" required value={time} min={localInput(new Date())}
          aria-invalid={late} onChange={(e) => { setTime(e.target.value); setLate(false); }} className={field} />
      </div>
      <div className="space-y-1">
        <label htmlFor={`${ids}-place`} className="block text-[13px] font-medium">Place</label>
        <select id={`${ids}-place`} required value={placeId} onChange={(e) => setPlaceId(e.target.value ? Number(e.target.value) : "")} className={cn(field, "appearance-none")}>
          <option value="">{places.isPending ? "Loading places…" : "Pick an exchange spot"}</option>
          {places.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </div>
      {late && <p role="alert" className="text-[13px] text-destructive">Pick a time in the future.</p>}
      <div className="flex flex-wrap gap-2">
        <button type="submit" disabled={!valid || send.isPending} className={primary}>
          {send.isPending && <Loader2 className="size-4 animate-spin" aria-hidden />} Send
        </button>
        <button type="button" onClick={onDone} className={secondary}>Cancel</button>
      </div>
    </form>
  );
}

export function HandoffCoordinatorCard({ txId }: { txId: number }) {
  const tx = useQuery({
    queryKey: ["transaction", txId],
    queryFn: () => api.transactions.get(txId),
    // Poll quickly only while the agent is working.
    refetchInterval: (q) => (q.state.data?.handoff?.suggestion?.status === "thinking" ? 2000 : false),
  });
  const [changing, setChanging] = useState(false);
  const suggest = useHandoffMutation(() => api.transactions.handoffSuggest(txId), () => track("handoff_suggest_tapped", {}));
  const send = useHandoffMutation(() => api.transactions.handoffSend(txId), () => track("handoff_sent", { changed: false }));
  const accept = useHandoffMutation(() => api.transactions.handoffAccept(txId), () => track("handoff_accepted", {}));
  const dismiss = useHandoffMutation(() => api.transactions.handoffDismiss(txId));

  const t = tx.data;
  const h = t?.handoff;
  if (!HANDOFF_COORDINATOR || !t || !h) return null;
  const s = h.suggestion;
  const other = firstName(t.my_role === "owner" ? t.borrower.name : t.owner.name);
  const busy = suggest.isPending || send.isPending || accept.isPending || dismiss.isPending;

  const suggestButton = (label: string, quiet = false) => (
    <div className="space-y-1">
      <button type="button" disabled={!h.can_suggest || busy} onClick={() => suggest.mutate(undefined)} className={cn(quiet ? secondary : primary, "w-full")}>
        {suggest.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Sparkles className="size-4" aria-hidden />} {label}
      </button>
      <p className="text-center text-[12px] text-muted-foreground">
        {h.runs_left_today > 0
          ? `Reads the last few messages in this chat only. ${h.runs_left_today} left today.`
          : "That's 3 suggestions for today. Pick a time yourself."}
      </p>
    </div>
  );
  const pickButton = (
    <button type="button" onClick={() => setChanging(true)} className={cn(secondary, "w-full")}>Pick a time myself</button>
  );

  let title = "Plan the handoff";
  let body;
  if (changing) {
    title = "Pick a time and place";
    body = <ChangeForm tx={t} start={s} onDone={() => setChanging(false)} />;
  } else if (!s) {
    body = <div className="space-y-2">{suggestButton("Suggest a time & place")}{pickButton}</div>;
  } else if (s.status === "thinking") {
    body = (
      <p role="status" className="flex items-center gap-2 text-[14px] text-muted-foreground">
        <Loader2 className="size-4 animate-spin" aria-hidden /> Reading your chat for a time that works… about 10 seconds.
      </p>
    );
  } else if (s.status === "failed") {
    body = (
      <div className="space-y-3">
        <p role="status" className="text-[14px]">{s.message ?? "Couldn't find a good time — suggest one yourself"}</p>
        {pickButton}
        {h.can_suggest && suggestButton("Try again", true)}
      </div>
    );
  } else if (s.status === "draft") {
    title = "Suggested handoff";
    body = (
      <div className="space-y-3">
        <WhenWhere s={s} />
        {s.reason && (
          <p className="flex items-start gap-1.5 text-[13px] text-muted-foreground">
            {s.sample ? <FlaskConical className="mt-0.5 size-3.5 shrink-0" aria-hidden /> : <Sparkles className="mt-0.5 size-3.5 shrink-0 text-points" aria-hidden />}
            <span>{s.reason}</span>
          </p>
        )}
        <p className="text-[12px] text-muted-foreground">Only you see this until you send it to {other}.</p>
        <div className="flex flex-wrap gap-2">
          <button type="button" disabled={busy} onClick={() => send.mutate(undefined)} className={primary}>
            {send.isPending && <Loader2 className="size-4 animate-spin" aria-hidden />} Send
          </button>
          <button type="button" disabled={busy} onClick={() => setChanging(true)} className={secondary}>Change</button>
        </div>
      </div>
    );
  } else if (s.status === "sent") {
    title = s.mine ? `Waiting for ${other}` : `${other} suggested a time`;
    body = (
      <div className="space-y-3">
        <WhenWhere s={s} />
        {s.mine ? (
          <>
            <p role="status" className="text-[13px] text-muted-foreground">{other} can confirm with one tap.</p>
            <button type="button" disabled={busy} onClick={() => setChanging(true)} className={cn(secondary, "w-full")}>Change</button>
          </>
        ) : (
          <div className="flex flex-wrap gap-2">
            <button type="button" disabled={busy || !s.can_accept} onClick={() => accept.mutate(undefined)} className={primary}>
              {accept.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Check className="size-4" aria-hidden />} Accept
            </button>
            <button type="button" disabled={busy} onClick={() => setChanging(true)} className={secondary}>Change</button>
          </div>
        )}
      </div>
    );
  } else {
    title = "Handoff set";
    body = (
      <div className="space-y-3">
        <WhenWhere s={s} />
        <button type="button" disabled={busy} onClick={() => setChanging(true)} className={cn(secondary, "w-full")}>Change</button>
      </div>
    );
  }

  const dismissable = !changing && !!s && s.mine && (s.status === "draft" || s.status === "failed");
  return (
    <section aria-label="Handoff time and place" className="space-y-3 rounded-2xl bg-card p-3.5 shadow-sm ring-1 ring-border/60">
      <div className="flex items-center justify-between gap-2">
        <h2 className="flex min-w-0 items-center gap-1.5 font-semibold">
          {s?.status === "accepted" && !changing ? <Check className="size-4.5 shrink-0 text-primary" aria-hidden /> : <CalendarClock className="size-4.5 shrink-0 text-primary" aria-hidden />}
          <span className="truncate">{title}</span>
          {s?.sample && !changing && s.status !== "failed" && (
            <span className="shrink-0 rounded-full bg-points-soft px-2 py-0.5 text-[12px] font-semibold">Sample</span>
          )}
        </h2>
        {dismissable && (
          <button type="button" aria-label="Dismiss this suggestion" disabled={busy} onClick={() => dismiss.mutate(undefined)}
            className="-my-2 -mr-2 flex size-11 shrink-0 items-center justify-center rounded-full text-muted-foreground active:bg-muted">
            <X className="size-4.5" aria-hidden />
          </button>
        )}
      </div>
      {body}
    </section>
  );
}
