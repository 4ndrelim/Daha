"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, Share2, Sparkles, XCircle } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError, track } from "@/lib/api";
import type { ItemCard as ItemCardT, RequestDetail, RequestStatus, Transaction } from "@/lib/api/types";
import { categoryInfo, TX_TYPE_LABEL } from "@/lib/categories";
import { firstName, shortDate, timeAgo } from "@/lib/format";
import { useTxAction } from "@/lib/queries/transactions";
import { invalidatePool } from "@/lib/api/mock/pool";
import { BackButton } from "@/components/daha/back-button";
import { InfoChip, TxTypeChip } from "@/components/daha/chips";
import { ItemThumb } from "@/components/daha/item-thumb";
import { PrimaryButton } from "@/components/daha/form";
import { EmptyState, ErrorState } from "@/components/daha/states";
import { actionLabel } from "@/components/daha/transaction-card";
import { UserAvatar } from "@/components/daha/user-avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { OfferSheet } from "./offer-sheet";
import { cn } from "@/lib/utils";

const STATUS: Record<RequestStatus, { label: string; cls: string }> = {
  open: { label: "Open", cls: "bg-emerald-50 text-emerald-700" },
  in_progress: { label: "Someone's helping", cls: "bg-amber-50 text-amber-700" },
  fulfilled: { label: "Done ✓", cls: "bg-stone-100 text-stone-600" },
  cancelled: { label: "Cancelled", cls: "bg-stone-100 text-stone-500" },
  expired: { label: "Expired", cls: "bg-stone-100 text-stone-500" },
};
const ASK: Record<string, string> = { lend: "Borrow", give: "Keep", exchange: "Swap" };
const TX_STATUS: Record<string, string> = {
  requested: "Waiting", offered: "Offered", accepted: "Accepted", handed_off: "Handed off", completed: "Done", declined: "Declined", cancelled: "Cancelled",
};

async function share(r: RequestDetail) {
  track("share_clicked", { request_id: r.id });
  const data = { title: "DAHA", text: r.raw_text, url: r.share_url };
  try {
    if (navigator.share) { await navigator.share(data); return; }
    await navigator.clipboard.writeText(r.share_url);
    toast.success("Link copied. Paste it in your dorm chat!");
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") return;
    toast.message(r.share_url, { description: "Copy this link to share" });
  }
}

function MatchRow({ item, onAsk, asking }: { item: ItemCardT; onAsk?: () => void; asking: boolean }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl bg-card p-2.5 ring-1 ring-border/60">
      <Link href={`/items/${item.id}`} className="flex min-w-0 flex-1 items-center gap-3">
        <ItemThumb url={item.thumbnail_url} category={item.category} className="size-14 shrink-0 rounded-xl" emojiClassName="text-2xl" />
        <span className="min-w-0">
          <span className="block truncate font-medium">{item.name}</span>
          <span className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
            <UserAvatar user={item.owner} className="size-4" /> {firstName(item.owner.name)}
            {" · "}{item.match_reason ?? (item.distance_min !== null ? `${item.distance_min} min` : item.community_label)}
          </span>
        </span>
      </Link>
      {onAsk && (
        <button type="button" onClick={onAsk} disabled={asking}
          className="h-10 shrink-0 rounded-full bg-primary-soft px-3.5 text-[14px] font-semibold text-accent-foreground disabled:opacity-60">
          Ask to borrow
        </button>
      )}
    </div>
  );
}

function OfferRow({ tx, isRequester }: { tx: Transaction; isRequester: boolean }) {
  const act = useTxAction();
  const who = isRequester ? tx.owner : tx.borrower;
  return (
    <div className="rounded-2xl bg-card p-3 ring-1 ring-border/60">
      <div className="flex items-center gap-3">
        <ItemThumb url={tx.item.thumbnail_url} category={tx.item.category} className="size-12 shrink-0 rounded-xl" emojiClassName="text-xl" />
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium">{tx.item.name}</p>
          <p className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
            <UserAvatar user={who} className="size-4" /> {isRequester ? who.name : "Your offer"} · {TX_STATUS[tx.status]}
          </p>
        </div>
        <TxTypeChip type={tx.kind} />
      </div>
      {tx.message && <p className="mt-2 rounded-xl bg-muted px-3 py-2 text-[14px]">&ldquo;{tx.message}&rdquo;</p>}
      <div className="mt-2.5 flex gap-2">
        {tx.allowed_actions.map((a) => (
          <button key={a} type="button" disabled={act.isPending} onClick={() => act.mutate({ id: tx.id, action: a })}
            className={cn("h-11 flex-1 rounded-full font-semibold disabled:opacity-60",
              a === "accept" ? "bg-primary text-primary-foreground" : "ring-1 ring-border active:bg-muted")}>
            {actionLabel(a, tx)}
          </button>
        ))}
        <Link href={`/messages/${tx.conversation_id}`} className="flex h-11 flex-1 items-center justify-center rounded-full font-semibold ring-1 ring-border active:bg-muted">
          Chat
        </Link>
      </div>
    </div>
  );
}

export function RequestScreen() {
  const { id } = useParams<{ id: string }>();
  const reqId = Number(id);
  const params = useSearchParams();
  const router = useRouter();
  const qc = useQueryClient();

  const request = useQuery({ queryKey: ["request", reqId], queryFn: () => api.requests.get(reqId), refetchInterval: 15_000 });
  const started = useRef(0);
  const matches = useQuery({
    queryKey: ["matches", reqId],
    queryFn: () => { if (!started.current) started.current = performance.now(); return api.matches.get(reqId); },
    enabled: request.isSuccess,
    // Poll every 2 s while matching is still running, for at most 30 s.
    refetchInterval: (q) => q.state.data?.matching_status === "pending" && performance.now() - started.current < 30_000 ? 2000 : false,
  });

  const preselect = Number(params.get("offer_item")) || null;
  const [sheet, setSheet] = useState(params.get("help") === "1" || preselect !== null);

  const borrow = useMutation({
    mutationFn: (item: ItemCardT) => api.items.borrow(item.id, { request_id: reqId }),
    onSuccess: (tx) => { toast.success("Asked! They'll get a notification."); router.push(`/messages/${tx.conversation_id}`); },
    onError: (e) => toast.error(e instanceof ApiError && e.status === 409 ? "You already asked for that one." : "Couldn't send."),
  });
  const close = useMutation({
    mutationFn: (status: "fulfilled" | "cancelled") => api.requests.update(reqId, { status }),
    onSuccess: (r) => {
      qc.setQueryData(["request", reqId], r);
      invalidatePool();
      qc.invalidateQueries({ queryKey: ["feed"] });
      toast.success(r.status === "fulfilled" ? "Marked as done. Glad it worked out!" : "Request cancelled.");
    },
    onError: () => toast.error("Couldn't update the request."),
  });

  if (request.isPending) return <div className="space-y-3"><Skeleton className="h-6 w-1/3" /><Skeleton className="h-24 rounded-2xl" /><Skeleton className="h-16 rounded-2xl" /></div>;
  if (request.isError) {
    return request.error instanceof ApiError && request.error.status === 404
      ? <EmptyState emoji="🔍" title="This request isn't here" body="It may have closed, or it's only visible to another dorm or group." actionLabel="See requests near you" actionHref="/home" />
      : <ErrorState onRetry={() => request.refetch()} />;
  }

  const r = request.data;
  const st = STATUS[r.status];
  const cat = r.category ? categoryInfo(r.category) : null;
  const active = r.status === "open" || r.status === "in_progress";
  const matchItems = (matches.data?.items ?? []).filter((i) => i.owner.id !== r.requester.id);
  const pinged = matches.data?.private_pinged_count ?? 0;

  return (
    <div className="space-y-6 pb-24">
      <BackButton className="-mt-2 -mb-3" />
      <div className="flex gap-2.5">
        <UserAvatar user={r.requester} className="mt-0.5 size-10 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="flex items-baseline gap-1.5 text-[13px]">
            <Link href={`/u/${r.requester.id}`} className="-my-3 inline-flex min-h-11 items-center truncate font-semibold">{r.is_mine ? "You" : r.requester.name}</Link>
            <span className="truncate text-muted-foreground">{r.requester.dorm_name ?? r.community_label} · {timeAgo(r.created_at)}</span>
          </p>
          <div className="mt-1 rounded-2xl rounded-tl-md bg-card px-4 py-3 text-[17px] leading-snug shadow-sm ring-1 ring-border/60">
            {r.raw_text}
            <span className="mt-2.5 flex flex-wrap gap-1.5">
              {r.item_name && <InfoChip>{r.item_name}</InfoChip>}
              {cat && <InfoChip>{cat.emoji} {cat.label}</InfoChip>}
              {r.needed_from && <InfoChip>📅 {shortDate(r.needed_from)}{r.needed_until && r.needed_until !== r.needed_from ? ` – ${shortDate(r.needed_until)}` : ""}</InfoChip>}
              {r.duration_days && <InfoChip>⏱ {r.duration_days} {r.duration_days === 1 ? "day" : "days"}</InfoChip>}
              {r.transaction_type && <InfoChip>{ASK[r.transaction_type] ?? TX_TYPE_LABEL[r.transaction_type]}</InfoChip>}
            </span>
          </div>
          <div className="mt-2 flex items-center gap-2 px-1">
            <span className={cn("rounded-full px-2 py-0.5 text-[12px] font-semibold", st.cls)}>{st.label}</span>
            <span className="text-[12px] text-muted-foreground">{r.community_label}{r.distance_min !== null && !r.is_mine ? ` · ${r.distance_min} min away` : ""}</span>
            <button type="button" onClick={() => share(r)} className="ml-auto flex h-11 items-center gap-1 rounded-full px-3 text-[13px] font-semibold text-primary active:bg-muted">
              <Share2 className="size-4" /> Share
            </button>
          </div>
        </div>
      </div>

      {r.offers.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-[17px] font-semibold">{r.is_mine ? `Offers (${r.offers.length})` : "Your offer"}</h2>
          {r.offers.map((tx) => <OfferRow key={tx.id} tx={tx} isRequester={r.is_mine} />)}
        </section>
      )}

      {active && (
        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-[17px] font-semibold">Available now</h2>
            {matches.data?.matching_status === "pending" && (
              <span className="flex items-center gap-1 text-[13px] text-muted-foreground"><Loader2 className="size-3.5 animate-spin" /> Looking nearby…</span>
            )}
          </div>
          {pinged > 0 && (
            <p className="flex items-center gap-2 rounded-xl bg-points-soft px-3 py-2 text-[13px] text-amber-900">
              <Sparkles className="size-4 shrink-0 text-amber-500" />
              Quietly asked {pinged} {pinged === 1 ? "person" : "people"} nearby who said they have one.
            </p>
          )}
          {matches.isPending && <><Skeleton className="h-[76px] rounded-2xl" /><Skeleton className="h-[76px] rounded-2xl" /></>}
          {matches.isError && <ErrorState message="Couldn't look for matches." onRetry={() => matches.refetch()} />}
          {matches.data?.matching_status === "done" && matchItems.length === 0 && (
            <p className="rounded-2xl border border-dashed border-border px-4 py-5 text-center text-[14px] text-muted-foreground">
              {r.is_mine ? "Nobody's listed one yet. We've let people nearby know. Share the link to reach more." : "Nobody's listed one yet. Have one? Offer it below."}
            </p>
          )}
          <div className="space-y-2">
            {matchItems.map((i) => (
              <MatchRow key={i.id} item={i} asking={borrow.isPending}
                onAsk={r.is_mine && i.status === "available" ? () => borrow.mutate(i) : undefined} />
            ))}
          </div>
        </section>
      )}

      {r.is_mine && active && (
        <section className="flex gap-2">
          <button type="button" onClick={() => close.mutate("fulfilled")} disabled={close.isPending}
            className="flex h-11 flex-1 items-center justify-center gap-1.5 rounded-full font-semibold ring-1 ring-border active:bg-muted">
            <CheckCircle2 className="size-4 text-primary" /> Mark fulfilled
          </button>
          <button type="button" onClick={() => close.mutate("cancelled")} disabled={close.isPending}
            className="flex h-11 flex-1 items-center justify-center gap-1.5 rounded-full font-semibold text-muted-foreground ring-1 ring-border active:bg-muted">
            <XCircle className="size-4" /> Cancel
          </button>
        </section>
      )}

      {!r.is_mine && r.status === "open" && (
        <>
          <div className="fixed inset-x-0 bottom-[calc(5.5rem+env(safe-area-inset-bottom))] z-20">
            <div className="mx-auto max-w-md px-4">
              <PrimaryButton type="button" className="shadow-lg shadow-primary/30" onClick={() => setSheet(true)}>🙋 I can help</PrimaryButton>
            </div>
          </div>
          <OfferSheet request={r} open={sheet} onOpenChange={setSheet} preselect={preselect} />
        </>
      )}
    </div>
  );
}
