"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Lock, MapPin, MessageCircle, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError, track } from "@/lib/api";
import type { ItemDetail, TransactionType } from "@/lib/api/types";
import { categoryInfo, CONDITION_LABEL } from "@/lib/categories";
import { VALUE_EXCHANGE, worthLabel } from "@/lib/value";
import { firstName, shortDate } from "@/lib/format";
import { invalidatePool } from "@/lib/api/mock/pool";
import { BackButton } from "@/components/daha/back-button";
import { CategoryChip, DistanceChip, StatusBadge, TxTypeChip, ValueChips } from "@/components/daha/chips";
import { Field, fieldClass, PrimaryButton } from "@/components/daha/form";
import { ItemThumb } from "@/components/daha/item-thumb";
import { ErrorState, EmptyState } from "@/components/daha/states";
import { UserAvatar } from "@/components/daha/user-avatar";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

const ACTION: Record<TransactionType, { cta: string; title: string; placeholder: string }> = {
  lend: { cta: "Request to borrow", title: "Ask to borrow", placeholder: "Hi! Could I borrow this for my exam on Friday?" },
  give: { cta: "Ask for it", title: "Ask for it", placeholder: "Hi! I'd love this if it's still free." },
  exchange: { cta: "Propose swap", title: "Propose a swap", placeholder: "Hi! I could swap my … for it." },
};

function Carousel({ item }: { item: ItemDetail }) {
  if (item.images.length === 0) {
    return <ItemThumb url={null} category={item.category} className="-mx-4 aspect-[4/3] rounded-none" emojiClassName="text-7xl" />;
  }
  return (
    <div className="no-scrollbar -mx-4 flex snap-x snap-mandatory overflow-x-auto">
      {item.images.map((img, i) => (
        <div key={img.id} className="relative aspect-[4/3] w-full shrink-0 snap-center bg-muted">
          {/* eslint-disable-next-line @next/next/no-img-element -- served by the backend proxy */}
          <img src={img.url} alt={i === 0 ? item.name : ""} loading={i === 0 ? "eager" : "lazy"} className="size-full object-cover" />
          {item.images.length > 1 && (
            <span className="absolute right-3 bottom-3 rounded-full bg-black/60 px-2 py-0.5 text-[12px] font-medium text-white">{i + 1}/{item.images.length}</span>
          )}
        </div>
      ))}
    </div>
  );
}

function OwnerCard({ item }: { item: ItemDetail }) {
  const owner = useQuery({ queryKey: ["user", item.owner.id], queryFn: () => api.users.get(item.owner.id) });
  return (
    <Link href={`/u/${item.owner.id}`} className="flex items-center gap-3 rounded-2xl bg-card p-3.5 ring-1 ring-border/60 active:bg-muted">
      <UserAvatar user={item.owner} className="size-11" />
      <span className="min-w-0 flex-1">
        <span className="block font-semibold">{item.owner.name}</span>
        <span className="block truncate text-[13px] text-muted-foreground">
          {item.owner.level_name}
          {item.owner.rating_avg !== null && ` · ★ ${item.owner.rating_avg.toFixed(1)}`}
          {owner.data && ` · ${owner.data.completed_count} ${owner.data.completed_count === 1 ? "handoff" : "handoffs"}`}
        </span>
      </span>
      <ChevronRight className="size-5 text-muted-foreground" />
    </Link>
  );
}

function BorrowSheet({ item, open, onOpenChange }: { item: ItemDetail; open: boolean; onOpenChange: (o: boolean) => void }) {
  const router = useRouter();
  const qc = useQueryClient();
  const a = ACTION[item.transaction_type];
  const [message, setMessage] = useState("");
  const [start, setStart] = useState("");
  const [due, setDue] = useState("");
  const borrow = useMutation({
    mutationFn: () => api.items.borrow(item.id, { message: message.trim() || null, start_date: start || null, due_date: due || null }),
    onSuccess: (tx) => {
      qc.invalidateQueries({ queryKey: ["item", item.id] });
      toast.success(`Sent! ${firstName(item.owner.name)} will get a notification.`);
      router.push(`/messages/${tx.conversation_id}`);
    },
    onError: (e) => toast.error(e instanceof ApiError && e.status === 409 ? "Someone just got there first, or you already asked." : "Couldn't send. Try again?"),
  });
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="mx-auto max-h-[90dvh] max-w-md overflow-y-auto rounded-t-3xl pb-[calc(1rem+env(safe-area-inset-bottom))]">
        <SheetHeader><SheetTitle className="text-[17px]">{a.title}: {item.name}</SheetTitle></SheetHeader>
        <form onSubmit={(e) => { e.preventDefault(); borrow.mutate(); }} className="space-y-4 px-4">
          <Field label={`Message to ${firstName(item.owner.name)}`} htmlFor="msg">
            <textarea id="msg" rows={3} value={message} onChange={(e) => setMessage(e.target.value)} placeholder={a.placeholder}
              className={cn(fieldClass, "h-auto py-3")} maxLength={500} />
          </Field>
          {item.transaction_type === "lend" && (
            <div className="grid grid-cols-2 gap-3">
              <Field label="From" htmlFor="start">
                <input id="start" type="date" value={start} onChange={(e) => setStart(e.target.value)} className={fieldClass} />
              </Field>
              <Field label="Back by" htmlFor="due" hint={item.max_lend_days ? `Up to ${item.max_lend_days} days` : undefined}>
                <input id="due" type="date" value={due} min={start || undefined} onChange={(e) => setDue(e.target.value)} className={fieldClass} />
              </Field>
            </div>
          )}
          <PrimaryButton type="submit" loading={borrow.isPending}>Send request</PrimaryButton>
        </form>
      </SheetContent>
    </Sheet>
  );
}

function OwnerControls({ item }: { item: ItemDetail }) {
  const router = useRouter();
  const qc = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  const toggle = useMutation({
    mutationFn: (available: boolean) => api.items.update(item.id, { status: available ? "available" : "unavailable" }),
    onSuccess: (next) => { qc.setQueryData(["item", item.id], next); invalidatePool(); },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : "Couldn't change that."),
  });
  const remove = useMutation({
    mutationFn: () => api.items.remove(item.id),
    onSuccess: () => { invalidatePool(); qc.invalidateQueries({ queryKey: ["feed"] }); toast.success("Removed."); router.replace("/profile"); },
    onError: (e) => toast.error(e instanceof ApiError && e.status === 409 ? "It's in the middle of a handoff. Finish that first." : "Couldn't remove it."),
  });
  const canToggle = item.status === "available" || item.status === "unavailable";
  return (
    <section className="space-y-3 rounded-2xl bg-card p-4 ring-1 ring-border/60">
      <p className="text-[13px] font-semibold text-muted-foreground">This is yours</p>
      {canToggle ? (
        <label className="flex min-h-11 items-center justify-between">
          <span className="font-medium">Available to share</span>
          <Switch checked={item.status === "available"} disabled={toggle.isPending} onCheckedChange={(v) => toggle.mutate(v)} />
        </label>
      ) : (
        <p className="text-[14px]">It&apos;s {item.status === "borrowed" ? "lent out" : "reserved"} right now.</p>
      )}
      <div className="flex gap-2">
        <Link href={`/add/item?edit=${item.id}`} className="flex h-11 flex-1 items-center justify-center gap-1.5 rounded-full font-semibold ring-1 ring-border active:bg-muted">
          <Pencil className="size-4" /> Edit
        </Link>
        <button type="button" onClick={() => setConfirm(true)} className="flex h-11 flex-1 items-center justify-center gap-1.5 rounded-full font-semibold text-destructive ring-1 ring-rose-200 active:bg-rose-50">
          <Trash2 className="size-4" /> Delete
        </button>
      </div>
      <Dialog open={confirm} onOpenChange={setConfirm}>
        <DialogContent className="max-w-sm rounded-3xl">
          <DialogHeader>
            <DialogTitle>Remove {item.name}?</DialogTitle>
            <DialogDescription>People won&apos;t be able to find or ask for it anymore.</DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex-row gap-2">
            <button type="button" onClick={() => setConfirm(false)} className="h-11 flex-1 rounded-full font-semibold ring-1 ring-border">Keep it</button>
            <button type="button" onClick={() => remove.mutate()} disabled={remove.isPending}
              className="h-11 flex-1 rounded-full bg-destructive font-semibold text-white disabled:opacity-60">Remove</button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}

export default function ItemPage() {
  const { id } = useParams<{ id: string }>();
  const itemId = Number(id);
  const router = useRouter();
  const item = useQuery({ queryKey: ["item", itemId], queryFn: () => api.items.get(itemId), enabled: itemId > 0 });
  const activeTx = useQuery({
    queryKey: ["transaction", item.data?.active_transaction_id],
    queryFn: () => api.transactions.get(item.data!.active_transaction_id!),
    enabled: !!item.data?.active_transaction_id && !item.data.is_mine,
  });
  const [sheet, setSheet] = useState(false);
  const viewed = useRef(0);
  useEffect(() => {
    if (item.data && viewed.current !== item.data.id) {
      viewed.current = item.data.id;
      track("item_viewed", { item_id: item.data.id, category: item.data.category, same_dorm: item.data.same_dorm });
    }
  }, [item.data]);

  const message = useMutation({
    mutationFn: () => api.conversations.direct({ user_id: item.data!.owner.id }),
    onSuccess: (c) => router.push(`/messages/${c.id}`),
    onError: () => toast.error("Couldn't open the chat."),
  });

  if (item.isPending) {
    return <div className="space-y-4"><Skeleton className="-mx-4 aspect-[4/3] rounded-none" /><Skeleton className="h-7 w-2/3" /><Skeleton className="h-20" /></div>;
  }
  if (item.isError) {
    return item.error instanceof ApiError && item.error.status === 404
      ? <EmptyState emoji="🔍" title="This item isn't here" body="It may have been removed, or it's only visible to another dorm." actionLabel="Search for something similar" actionHref="/explore" />
      : <ErrorState message="Couldn't load this item." onRetry={() => item.refetch()} />;
  }

  const i = item.data;
  const a = ACTION[i.transaction_type];
  const cat = categoryInfo(i.category);

  return (
    <div className="-mt-4 space-y-5 pb-20">
      <div className="relative">
        <BackButton floating className="absolute top-3 left-0 z-10" />
        <Carousel item={i} />
      </div>

      <div className="space-y-2">
        {VALUE_EXCHANGE && <ValueChips value={i.value_usd} />}
        <div className="flex flex-wrap items-center gap-1.5">
          <TxTypeChip type={i.transaction_type} />
          <StatusBadge status={i.status} />
          <CategoryChip category={i.category} />
          {i.condition && <span className="text-[13px] text-muted-foreground">· {CONDITION_LABEL[i.condition]}</span>}
        </div>
        <h1 className="text-[22px] leading-7 font-semibold">
          {i.quantity > 1 && <span className="text-muted-foreground">{i.quantity}× </span>}{i.name}
        </h1>
        {!VALUE_EXCHANGE && i.value_usd != null && <p className="text-[14px] text-muted-foreground">{worthLabel(i.value_usd)}</p>}
        <DistanceChip min={i.distance_min} label={i.community_label} />
        {i.visibility === "private" && (
          <p className="flex items-center gap-1.5 rounded-xl bg-muted px-3 py-2 text-[13px]">
            <Lock className="size-4" /> Only you can see this. {i.pings_enabled ? "We'll quietly ping you if someone nearby needs one." : "Pings are off."}
          </p>
        )}
      </div>

      {!i.is_mine && <OwnerCard item={i} />}

      {i.description && <p className="leading-relaxed whitespace-pre-line">{i.description}</p>}

      <dl className="space-y-2.5 rounded-2xl bg-card p-4 text-[14px] ring-1 ring-border/60">
        <div className="flex justify-between gap-3">
          <dt className="text-muted-foreground">Available</dt>
          <dd className="text-right">
            {i.available_from || i.available_until
              ? `${i.available_from ? shortDate(i.available_from) : "Now"} – ${i.available_until ? shortDate(i.available_until) : "whenever"}`
              : "Anytime"}
          </dd>
        </div>
        {i.transaction_type === "lend" && i.max_lend_days && (
          <div className="flex justify-between gap-3"><dt className="text-muted-foreground">Lend for up to</dt><dd>{i.max_lend_days} days</dd></div>
        )}
        <div className="flex justify-between gap-3">
          <dt className="text-muted-foreground">Pickup</dt>
          <dd className="flex items-center gap-1 text-right"><MapPin className="size-3.5" />{i.pickup_place?.name ?? (i.owner.dorm_name ? `Near ${i.owner.dorm_name}` : "Ask the owner")}</dd>
        </div>
        {i.pickup_note && (
          <div className="rounded-xl bg-primary-soft px-3 py-2">
            <dt className="flex items-center gap-1 text-[12px] font-semibold text-accent-foreground"><Lock className="size-3" /> Pickup note {i.is_mine ? "(only shared after you accept)" : ""}</dt>
            <dd className="mt-0.5">{i.pickup_note}</dd>
          </div>
        )}
      </dl>

      {i.is_mine && <OwnerControls item={i} />}

      {!i.is_mine && (
        <div className="fixed inset-x-0 bottom-[calc(5.5rem+env(safe-area-inset-bottom))] z-20">
          <div className="mx-auto flex max-w-md gap-2 rounded-full px-4">
            <button type="button" aria-label={`Message ${firstName(i.owner.name)}`} onClick={() => message.mutate()} disabled={message.isPending}
              className="flex size-12 shrink-0 items-center justify-center rounded-full bg-card shadow-md ring-1 ring-border active:bg-muted">
              <MessageCircle className="size-5" />
            </button>
            {i.can_borrow ? (
              <PrimaryButton type="button" className="shadow-lg shadow-primary/30" onClick={() => setSheet(true)}>{cat.emoji} {a.cta}</PrimaryButton>
            ) : activeTx.data ? (
              <Link href={`/messages/${activeTx.data.conversation_id}`} className="flex h-12 flex-1 items-center justify-center rounded-full bg-primary-soft font-semibold text-accent-foreground">
                You already asked · open chat
              </Link>
            ) : (
              <span className="flex h-12 flex-1 items-center justify-center rounded-full bg-muted font-semibold text-muted-foreground">
                {i.status === "available" ? "Not available to you" : i.status === "borrowed" ? "Lent out right now" : i.status === "reserved" ? "Reserved" : "Not available"}
              </span>
            )}
          </div>
        </div>
      )}
      {!i.is_mine && i.can_borrow && <BorrowSheet item={i} open={sheet} onOpenChange={setSheet} />}
    </div>
  );
}
