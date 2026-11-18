"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import { UserAvatar } from "@/components/daha/user-avatar";
import { EmptyState, ErrorState } from "@/components/daha/states";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const TX_LABEL: Record<string, string> = {
  requested: "Requested", offered: "Offered", accepted: "Accepted", handed_off: "Handed off",
  completed: "Done", declined: "Declined", cancelled: "Cancelled",
};

export default function MessagesPage() {
  const convs = useQuery({ queryKey: ["conversations"], queryFn: () => api.conversations.list(), refetchInterval: 10_000 });
  return (
    <div>
      <h1 className="mb-3 text-[22px] leading-7 font-semibold">Messages</h1>
      {convs.isPending && <div className="space-y-2">{Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-16 rounded-2xl" />)}</div>}
      {convs.isError && <ErrorState onRetry={() => convs.refetch()} />}
      {convs.data?.length === 0 && (
        <EmptyState emoji="💬" title="No chats yet" body="When you borrow, lend, or offer something, the chat shows up here." actionLabel="Find something nearby" actionHref="/explore" />
      )}
      <ul className="-mx-4 divide-y divide-border/60">
        {convs.data?.map((c) => {
          const unread = c.unread_count > 0;
          const last = c.last_message;
          return (
            <li key={c.id}>
              <Link href={`/messages/${c.id}`} className="flex min-h-[72px] items-center gap-3 px-4 py-2.5 active:bg-muted">
                <UserAvatar user={c.other_user} className="size-12" />
                <span className="min-w-0 flex-1">
                  <span className="flex items-baseline gap-2">
                    <span className={cn("truncate", unread ? "font-bold" : "font-semibold")}>{c.other_user.name}</span>
                    <span className="ml-auto shrink-0 text-[12px] text-muted-foreground">{timeAgo(c.updated_at)}</span>
                  </span>
                  {c.transaction && (
                    <span className="mt-0.5 flex items-center gap-1.5 text-[12px]">
                      <span className="truncate rounded-full bg-primary-soft px-2 font-medium text-accent-foreground">{c.transaction.item_name}</span>
                      <span className="shrink-0 text-muted-foreground">{TX_LABEL[c.transaction.status]}</span>
                    </span>
                  )}
                  <span className={cn("mt-0.5 block truncate text-[14px]", unread ? "font-medium text-foreground" : "text-muted-foreground")}>
                    {last ? (last.kind === "system" ? `· ${last.body}` : last.body) : "Say hi 👋"}
                  </span>
                </span>
                {unread && <span className="size-2.5 shrink-0 rounded-full bg-primary" aria-label={`${c.unread_count} unread`} />}
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
