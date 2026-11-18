"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, ChevronRight, Lock, MessageSquareHeart, UserPlus } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError, track } from "@/lib/api";
import type { ItemCard as ItemCardT, Me, Transaction } from "@/lib/api/types";
import { STATUS_LABEL } from "@/lib/categories";
import { copyInvite, inviteUrl } from "@/lib/invite";
import { meKey, useMe } from "@/lib/queries/me";
import { invalidatePool } from "@/lib/api/mock/pool";
import { fieldClass, PrimaryButton } from "@/components/daha/form";
import { ItemThumb } from "@/components/daha/item-thumb";
import { LogoutButton } from "@/components/daha/logout-button";
import { ProfileHeader } from "@/components/daha/profile-header";
import { RequestCard } from "@/components/daha/request-card";
import { ReviewList } from "@/components/daha/review-list";
import { EmptyState, ErrorState, RequestListSkeleton, SectionHeader } from "@/components/daha/states";
import { TransactionCard } from "@/components/daha/transaction-card";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

type Tab = "inventory" | "requests" | "activity" | "reviews";
const TABS: { value: Tab; label: string }[] = [
  { value: "inventory", label: "My stuff" }, { value: "requests", label: "Requests" },
  { value: "activity", label: "Activity" }, { value: "reviews", label: "Reviews" },
];

function useUpdateItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: number; status?: "available" | "unavailable"; pings_enabled?: boolean }) => api.items.update(id, body),
    onSuccess: (item) => {
      qc.setQueryData(["item", item.id], item);
      qc.invalidateQueries({ queryKey: ["my-items"] });
      invalidatePool();
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : "Couldn't change that."),
  });
}

function InventoryRow({ item, pings }: { item: ItemCardT; pings?: boolean }) {
  const update = useUpdateItem();
  const togglable = item.status === "available" || item.status === "unavailable";
  return (
    <li className="flex min-h-16 items-center gap-3 py-2">
      <Link href={`/items/${item.id}`} className="flex min-w-0 flex-1 items-center gap-3">
        <ItemThumb url={item.thumbnail_url} category={item.category} className="size-12 shrink-0 rounded-xl" emojiClassName="text-xl" />
        <span className="min-w-0">
          <span className="block truncate font-medium">{item.name}</span>
          <span className="block text-[12px] text-muted-foreground">
            {item.visibility === "private" ? (pings === false ? "Pings off" : "We'll ping you if someone needs one") : `${STATUS_LABEL[item.status]} · ${item.community_label}`}
          </span>
        </span>
      </Link>
      {item.visibility === "private" ? (
        <label className="flex shrink-0 flex-col items-center gap-0.5 text-[11px] text-muted-foreground">
          <Switch checked={pings ?? true} disabled={pings === undefined || update.isPending}
            onCheckedChange={(v) => update.mutate({ id: item.id, pings_enabled: v })} aria-label="Ping me if someone needs it" />
          Ping me
        </label>
      ) : togglable ? (
        <label className="flex shrink-0 flex-col items-center gap-0.5 text-[11px] text-muted-foreground">
          <Switch checked={item.status === "available"} disabled={update.isPending}
            onCheckedChange={(v) => update.mutate({ id: item.id, status: v ? "available" : "unavailable" })} aria-label="Available to share" />
          Sharing
        </label>
      ) : (
        <span className="shrink-0 rounded-full bg-amber-50 px-2 py-0.5 text-[12px] font-medium text-amber-700">{STATUS_LABEL[item.status]}</span>
      )}
    </li>
  );
}

function Inventory() {
  const items = useQuery({ queryKey: ["my-items"], queryFn: () => api.items.mine() });
  const priv = items.data?.filter((i) => i.visibility === "private") ?? [];
  const shared = items.data?.filter((i) => i.visibility !== "private") ?? [];
  // ItemCard has no pings_enabled; fetch details for the (few) private items.
  const details = useQueries({ queries: priv.map((i) => ({ queryKey: ["item", i.id], queryFn: () => api.items.get(i.id) })) });
  const pingsById = new Map(details.flatMap((d) => (d.data ? [[d.data.id, d.data.pings_enabled] as const] : [])));

  if (items.isPending) return <div className="space-y-2">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-14 rounded-2xl" />)}</div>;
  if (items.isError) return <ErrorState onRetry={() => items.refetch()} />;
  return (
    <div className="space-y-6">
      <Link href="/add/scan" className="flex min-h-14 items-center gap-3 rounded-2xl bg-primary-soft px-4 active:bg-emerald-100">
        <Camera className="size-5 text-accent-foreground" />
        <span className="flex-1 font-semibold text-accent-foreground">Snap more stuff</span>
        <ChevronRight className="size-5 text-accent-foreground" />
      </Link>
      <section>
        <SectionHeader title={`Shared (${shared.length})`} action={<Link href="/add/item" className="-my-2 inline-flex min-h-11 items-center text-[13px] font-semibold text-primary">+ List one</Link>} />
        {shared.length === 0
          ? <EmptyState emoji="📦" title="Nothing shared yet" body="Snap your desk and we'll list it in seconds." actionLabel="Snap your stuff" actionHref="/add/scan" />
          : <ul className="divide-y divide-border/60">{shared.map((i) => <InventoryRow key={i.id} item={i} />)}</ul>}
      </section>
      <section>
        <SectionHeader title={`Private (${priv.length})`} action={<Link href="/add/item?visibility=private" className="-my-2 inline-flex min-h-11 items-center px-1 text-[13px] font-semibold text-primary">+ Add</Link>} />
        <p className="mb-2 flex items-start gap-1.5 text-[13px] text-muted-foreground">
          <Lock className="mt-0.5 size-3.5 shrink-0" /> Only you see these. When someone nearby needs one, we ping you, and they never see who.
        </p>
        {priv.length === 0
          ? <p className="rounded-2xl border border-dashed border-border px-4 py-4 text-center text-[14px] text-muted-foreground">Bike pump? Tool kit? Add things you&apos;d lend if asked.</p>
          : <ul className="divide-y divide-border/60">{priv.map((i) => <InventoryRow key={i.id} item={i} pings={pingsById.get(i.id)} />)}</ul>}
      </section>
    </div>
  );
}

function Requests() {
  const reqs = useQuery({ queryKey: ["my-requests"], queryFn: () => api.requests.mine() });
  if (reqs.isPending) return <RequestListSkeleton />;
  if (reqs.isError) return <ErrorState onRetry={() => reqs.refetch()} />;
  if (reqs.data.length === 0) return <EmptyState emoji="🙋" title="You haven't asked for anything" body="Need a charger tonight? Your dorm probably has one." actionLabel="Ask for something" actionHref="/add/request" />;
  return <div className="space-y-4">{reqs.data.map((r) => <RequestCard key={r.id} request={r} showHelp={false} />)}</div>;
}

function Activity() {
  const [state, setState] = useState<"active" | "past">("active");
  const txs = useQuery({ queryKey: ["transactions", state], queryFn: () => api.transactions.list({ state, role: "all" }) });
  return (
    <div className="space-y-3">
      <div className="flex h-10 w-fit rounded-full bg-muted p-1">
        {(["active", "past"] as const).map((s) => (
          <button key={s} type="button" aria-pressed={state === s} onClick={() => setState(s)}
            className={cn("rounded-full px-4 text-[14px] font-semibold capitalize", state === s ? "bg-card shadow-sm" : "text-muted-foreground")}>{s}</button>
        ))}
      </div>
      {txs.isPending && <Skeleton className="h-36 rounded-2xl" />}
      {txs.isError && <ErrorState onRetry={() => txs.refetch()} />}
      {txs.data?.length === 0 && <EmptyState emoji="🤝" title={state === "active" ? "Nothing in progress" : "No history yet"} body="Borrows, loans and giveaways show up here." />}
      {txs.data?.map((t: Transaction) => (
        <div key={t.id} className="space-y-1">
          <p className="px-1 text-[12px] font-semibold tracking-wide text-muted-foreground uppercase">{t.my_role === "owner" ? (t.kind === "lend" ? "Lending" : "Giving") : "Borrowing"}</p>
          <TransactionCard tx={t} compact />
          <Link href={`/messages/${t.conversation_id}`} className="flex h-10 items-center justify-end gap-1 px-1 text-[13px] font-semibold text-primary">Open chat <ChevronRight className="size-4" /></Link>
        </div>
      ))}
    </div>
  );
}

function Reviews({ me }: { me: Me }) {
  const reviews = useQuery({ queryKey: ["reviews", me.id], queryFn: () => api.users.reviews(me.id) });
  if (reviews.isPending) return <Skeleton className="h-20 rounded-2xl" />;
  if (reviews.isError) return <ErrorState onRetry={() => reviews.refetch()} />;
  return <ReviewList reviews={reviews.data} emptyBody="After your first handoff, people can review you here." />;
}

function Settings({ me }: { me: Me }) {
  const qc = useQueryClient();
  const [radius, setRadius] = useState(me.walking_radius_min);
  const [feedback, setFeedback] = useState("");
  const dorms = useQuery({ queryKey: ["communities", { kind: "dorm" }], queryFn: () => api.communities.list({ kind: "dorm" }) });
  const save = useMutation({
    mutationFn: (body: { walking_radius_min?: number; dorm_id?: number }) => api.me.update(body),
    onSuccess: (next, body) => {
      qc.setQueryData(meKey, next);
      if (body.dorm_id) {
        qc.invalidateQueries({ queryKey: ["communities"] });
        qc.invalidateQueries({ queryKey: ["feed"] });
        invalidatePool();
        toast.success(`Moved to ${next.dorm?.name ?? "your new dorm"}.`);
      }
    },
    onError: () => toast.error("Couldn't save that."),
  });
  return (
    <section className="space-y-5 rounded-3xl bg-card p-4 ring-1 ring-border/60">
      <h2 className="text-[17px] font-semibold">Settings</h2>
      <div className="space-y-2">
        <label htmlFor="radius" className="flex justify-between text-[14px]">
          <span className="font-medium">How far you&apos;ll walk</span>
          <span className="text-muted-foreground">{radius} min</span>
        </label>
        <input id="radius" type="range" min={5} max={30} step={5} value={radius} onChange={(e) => setRadius(Number(e.target.value))}
          onPointerUp={() => radius !== me.walking_radius_min && save.mutate({ walking_radius_min: radius })}
          onKeyUp={() => radius !== me.walking_radius_min && save.mutate({ walking_radius_min: radius })}
          className="h-11 w-full accent-primary" />
      </div>
      <div className="space-y-1.5">
        <label htmlFor="dorm" className="text-[14px] font-medium">Your dorm</label>
        <select id="dorm" value={me.dorm?.id ?? ""} disabled={save.isPending}
          onChange={(e) => e.target.value && save.mutate({ dorm_id: Number(e.target.value) })} className={cn(fieldClass, "appearance-none")}>
          {!me.dorm && <option value="">Pick your dorm</option>}
          {dorms.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
      </div>
      <button type="button" onClick={() => copyInvite(inviteUrl(me.dorm ? { kind: "dorm", slug: me.dorm.slug } : null, me.id), "profile")}
        className="flex min-h-12 w-full items-center gap-3 rounded-2xl bg-primary-soft px-4 text-left font-semibold text-accent-foreground">
        <UserPlus className="size-5" /> Invite your hallmates
      </button>
      <form onSubmit={(e) => {
        e.preventDefault();
        if (!feedback.trim()) return;
        track("feedback_submitted", { text: feedback.trim().slice(0, 1000), page: "profile" });
        setFeedback("");
        toast.success("Thanks! We read every one.");
      }} className="space-y-2">
        <label htmlFor="fb" className="flex items-center gap-1.5 text-[14px] font-medium"><MessageSquareHeart className="size-4" /> Feedback</label>
        <textarea id="fb" rows={2} value={feedback} onChange={(e) => setFeedback(e.target.value)} placeholder="What's confusing, missing, or great?"
          className={cn(fieldClass, "h-auto py-3")} maxLength={1000} />
        <PrimaryButton type="submit" disabled={!feedback.trim()} className="h-11">Send feedback</PrimaryButton>
      </form>
      <LogoutButton />
    </section>
  );
}

export default function ProfilePage() {
  const me = useMe();
  const [tab, setTab] = useState<Tab>("inventory");
  if (me.isPending) return <Skeleton className="h-64 rounded-3xl" />;
  if (me.isError) return <ErrorState onRetry={() => me.refetch()} />;
  return (
    <div className="space-y-5">
      <ProfileHeader user={me.data} dormName={me.data.dorm?.name} />
      <div className="sticky top-[calc(3.5rem+env(safe-area-inset-top))] z-10 -mx-4 flex gap-5 overflow-x-auto border-b border-border bg-background/95 px-4 backdrop-blur" role="tablist">
        {TABS.map((t) => (
          <button key={t.value} type="button" role="tab" aria-selected={tab === t.value} onClick={() => setTab(t.value)}
            className={cn("-mb-px h-11 shrink-0 border-b-2 text-[15px] font-semibold", tab === t.value ? "border-primary text-foreground" : "border-transparent text-muted-foreground")}>
            {t.label}
          </button>
        ))}
      </div>
      {tab === "inventory" && <Inventory />}
      {tab === "requests" && <Requests />}
      {tab === "activity" && <Activity />}
      {tab === "reviews" && <Reviews me={me.data} />}
      <Settings me={me.data} />
    </div>
  );
}
