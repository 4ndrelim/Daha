"use client";

import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Award, Bell, CheckCheck, Gift, HandHelping, Inbox, MessageCircle, Search, Sparkles, Star } from "lucide-react";
import { api } from "@/lib/api";
import type { Notification, NotificationType } from "@/lib/api/types";
import { timeAgo } from "@/lib/format";
import { EmptyState, ErrorState } from "@/components/daha/states";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const ICON: Record<NotificationType, { icon: typeof Bell; cls: string }> = {
  match: { icon: Search, cls: "bg-emerald-50 text-emerald-700" },
  private_match: { icon: Sparkles, cls: "bg-amber-50 text-amber-700" },
  offer: { icon: Gift, cls: "bg-sky-50 text-sky-700" },
  borrow_request: { icon: HandHelping, cls: "bg-violet-50 text-violet-700" },
  tx_update: { icon: MessageCircle, cls: "bg-emerald-50 text-emerald-700" },
  review: { icon: Star, cls: "bg-amber-50 text-amber-700" },
  badge: { icon: Award, cls: "bg-amber-50 text-amber-700" },
  system: { icon: Inbox, cls: "bg-stone-100 text-stone-600" },
};

export default function NotificationsPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["notifications"], queryFn: () => api.notifications.list({ limit: 50 }), refetchInterval: 20_000 });
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["notifications"] });
    qc.invalidateQueries({ queryKey: ["unread"] });
  };
  const markAll = useMutation({ mutationFn: () => api.notifications.markRead({ all: true }), onSuccess: refresh });

  const open = (n: Notification) => {
    if (!n.read) {
      qc.setQueryData<Notification[]>(["notifications"], (prev) => prev?.map((x) => (x.id === n.id ? { ...x, read: true } : x)));
      api.notifications.markRead({ ids: [n.id] }).then(refresh).catch(() => {});
    }
    router.push(n.link);
  };

  const unread = list.data?.filter((n) => !n.read).length ?? 0;

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h1 className="text-[22px] leading-7 font-semibold">Notifications</h1>
        {unread > 0 && (
          <button type="button" onClick={() => markAll.mutate()} disabled={markAll.isPending}
            className="flex h-10 items-center gap-1.5 rounded-full px-3 text-[13px] font-semibold text-primary active:bg-muted">
            <CheckCheck className="size-4" /> Mark all read
          </button>
        )}
      </div>
      {list.isPending && <div className="space-y-2">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-16 rounded-2xl" />)}</div>}
      {list.isError && <ErrorState onRetry={() => list.refetch()} />}
      {list.data?.length === 0 && (
        <EmptyState emoji="🔔" title="All quiet" body="We'll tell you when someone needs something you have, or replies to you." />
      )}
      <ul className="-mx-4 divide-y divide-border/60">
        {list.data?.map((n) => {
          const { icon: Icon, cls } = ICON[n.type] ?? ICON.system;
          return (
            <li key={n.id} className={cn(!n.read && "bg-primary-soft/40")}>
              <button type="button" onClick={() => open(n)} className="flex min-h-16 w-full items-start gap-3 px-4 py-3 text-left active:bg-muted">
                <span className={cn("mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-full", cls)}><Icon className="size-5" /></span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-baseline gap-2">
                    <span className={cn("flex-1", n.read ? "font-medium" : "font-semibold")}>{n.title}</span>
                    <span className="shrink-0 text-[12px] text-muted-foreground">{timeAgo(n.created_at)}</span>
                  </span>
                  {n.body && <span className="mt-0.5 block text-[14px] text-muted-foreground">{n.body}</span>}
                  {n.type === "private_match" && (
                    <span className="mt-2 inline-flex h-10 items-center rounded-full bg-primary px-4 text-[14px] font-semibold text-primary-foreground">
                      Help anonymously
                    </span>
                  )}
                </span>
                {!n.read && <span className="mt-2 size-2.5 shrink-0 rounded-full bg-primary" aria-label="Unread" />}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
