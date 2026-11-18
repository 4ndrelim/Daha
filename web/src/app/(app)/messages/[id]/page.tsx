"use client";

import Link from "next/link";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowUp, ChevronDown, ChevronUp, RotateCcw } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { ID, Message } from "@/lib/api/types";
import { useMe } from "@/lib/queries/me";
import { UserAvatar } from "@/components/daha/user-avatar";
import { TransactionCard } from "@/components/daha/transaction-card";
import { EmptyState, ErrorState } from "@/components/daha/states";
import { Skeleton } from "@/components/ui/skeleton";
import { format, parseISO } from "date-fns";
import { cn } from "@/lib/utils";

type ChatMessage = Message & { pending?: boolean; failed?: boolean };

async function fetchAll(id: ID): Promise<ChatMessage[]> {
  const out: Message[] = [];
  let after: ID | undefined;
  for (let i = 0; i < 20; i++) {
    const page = await api.conversations.messages(id, { after_id: after, limit: 50 });
    out.push(...page);
    if (page.length < 50) break;
    after = page[page.length - 1].id;
  }
  return out;
}

function mergeNew(prev: ChatMessage[] = [], incoming: Message[]): ChatMessage[] {
  const known = new Set(prev.filter((m) => m.id > 0).map((m) => m.id));
  const fresh = incoming.filter((m) => !known.has(m.id));
  return fresh.length ? [...prev, ...fresh] : prev;
}

export default function ChatPage() {
  const { id } = useParams<{ id: string }>();
  const convId = Number(id);
  const qc = useQueryClient();
  const { data: me } = useMe();
  const key = ["messages", convId];

  const conv = useQuery({ queryKey: ["conversation", convId], queryFn: () => api.conversations.get(convId) });
  const txId = conv.data?.transaction?.id;
  const tx = useQuery({ queryKey: ["transaction", txId], queryFn: () => api.transactions.get(txId!), enabled: !!txId, refetchInterval: 15_000 });
  const messages = useQuery({ queryKey: key, queryFn: () => fetchAll(convId) });

  // Poll for new messages every 3 s with after_id; a new system message means the transaction moved.
  useQuery({
    queryKey: ["messages-poll", convId],
    enabled: messages.isSuccess,
    refetchInterval: 3000,
    queryFn: async () => {
      const cur = qc.getQueryData<ChatMessage[]>(key) ?? [];
      const lastId = cur.reduce((m, x) => (x.id > m ? x.id : m), 0);
      const fresh = await api.conversations.messages(convId, { after_id: lastId || undefined, limit: 50 });
      if (fresh.length) {
        qc.setQueryData<ChatMessage[]>(key, (prev) => mergeNew(prev, fresh));
        if (fresh.some((m) => m.kind === "system")) qc.invalidateQueries({ queryKey: ["transaction", txId] });
        api.conversations.markRead(convId).catch(() => {});
      }
      return fresh.length;
    },
  });

  // Mark read on open, and refresh the unread badges.
  useEffect(() => {
    api.conversations.markRead(convId).then(() => {
      qc.invalidateQueries({ queryKey: ["me"] });
      qc.invalidateQueries({ queryKey: ["unread"] });
      qc.invalidateQueries({ queryKey: ["conversations"] });
    }).catch(() => {});
  }, [convId, qc]);

  const [text, setText] = useState("");
  const send = useMutation({
    mutationFn: ({ body }: { body: string; tempId: number }) => api.conversations.send(convId, { body }),
    onMutate: ({ body, tempId }) => {
      const temp: ChatMessage = {
        id: tempId, conversation_id: convId, kind: "text", body, created_at: new Date().toISOString(), pending: true,
        sender: me ? { id: me.id, name: me.name, avatar_url: me.avatar_url, dorm_name: me.dorm_name, level_name: me.level_name, rating_avg: me.rating_avg } : null,
      };
      qc.setQueryData<ChatMessage[]>(key, (prev = []) => [...prev, temp]);
    },
    onSuccess: (msg, { tempId }) => {
      qc.setQueryData<ChatMessage[]>(key, (prev = []) => {
        const withoutTemp = prev.filter((m) => m.id !== tempId);
        return withoutTemp.some((m) => m.id === msg.id) ? withoutTemp : [...withoutTemp, msg];
      });
      qc.invalidateQueries({ queryKey: ["conversations"] });
    },
    onError: (_e, { tempId }) => {
      qc.setQueryData<ChatMessage[]>(key, (prev = []) => prev.map((m) => (m.id === tempId ? { ...m, pending: false, failed: true } : m)));
    },
  });
  const tempSeq = useRef(0);
  const submit = (body: string) => {
    const b = body.trim();
    if (!b) return;
    tempSeq.current += 1;
    send.mutate({ body: b, tempId: -tempSeq.current });
  };
  const retry = (m: ChatMessage) => {
    qc.setQueryData<ChatMessage[]>(key, (prev = []) => prev.filter((x) => x.id !== m.id));
    submit(m.body);
  };

  // Keep the newest message in view.
  const bottom = useRef<HTMLDivElement>(null);
  const count = messages.data?.length ?? 0;
  useLayoutEffect(() => { bottom.current?.scrollIntoView({ block: "end" }); }, [count]);

  const [cardOpen, setCardOpen] = useState(true);

  if (conv.isError) {
    return conv.error instanceof ApiError && (conv.error.status === 404 || conv.error.status === 403)
      ? <EmptyState emoji="💬" title="This chat isn't available" actionLabel="Back to messages" actionHref="/messages" />
      : <ErrorState onRetry={() => conv.refetch()} />;
  }
  const other = conv.data?.other_user;

  return (
    <div className="-mt-4 flex min-h-[calc(100dvh-3.5rem)] flex-col">
      <div className="sticky top-[calc(3.5rem+env(safe-area-inset-top))] z-20 -mx-4 space-y-2 border-b border-border/60 bg-background/95 px-4 py-2 backdrop-blur">
        <div className="flex items-center gap-2">
          <Link href="/messages" aria-label="Back to messages" className="-ml-2 flex size-11 items-center justify-center rounded-full active:bg-muted"><ArrowLeft className="size-5" /></Link>
          {other ? (
            <Link href={`/u/${other.id}`} className="flex min-w-0 items-center gap-2">
              <UserAvatar user={other} className="size-8" />
              <span className="min-w-0">
                <span className="block truncate font-semibold">{other.name}</span>
                <span className="block truncate text-[12px] text-muted-foreground">{other.dorm_name ?? ""}{other.rating_avg !== null ? ` · ★ ${other.rating_avg.toFixed(1)}` : ""}</span>
              </span>
            </Link>
          ) : <Skeleton className="h-8 w-40" />}
          {tx.data && (
            <button type="button" onClick={() => setCardOpen((v) => !v)} aria-label={cardOpen ? "Hide details" : "Show details"}
              className="ml-auto flex size-11 items-center justify-center rounded-full text-muted-foreground active:bg-muted">
              {cardOpen ? <ChevronUp className="size-5" /> : <ChevronDown className="size-5" />}
            </button>
          )}
        </div>
        {tx.data && <TransactionCard tx={tx.data} compact={!cardOpen} />}
        {txId && tx.isPending && <Skeleton className="h-28 rounded-2xl" />}
      </div>

      <div className="flex-1 space-y-1.5 py-4 pb-24">
        {messages.isPending && <div className="space-y-3">{[60, 40, 70].map((w) => <Skeleton key={w} className="h-10 rounded-2xl" style={{ width: `${w}%` }} />)}</div>}
        {messages.isError && <ErrorState message="Couldn't load messages." onRetry={() => messages.refetch()} />}
        {messages.data?.length === 0 && <p className="py-10 text-center text-muted-foreground">Say hi 👋 and sort out a time to meet.</p>}
        {messages.data?.map((m, i) => {
          if (m.kind === "system") {
            return <p key={m.id} className="mx-auto max-w-[85%] py-1.5 text-center text-[12px] text-muted-foreground">{m.body}</p>;
          }
          const mine = m.sender?.id === me?.id;
          const prev = messages.data![i - 1];
          const grouped = prev && prev.kind === "text" && prev.sender?.id === m.sender?.id;
          return (
            <div key={m.id} className={cn("flex flex-col", mine ? "items-end" : "items-start", !grouped && "pt-1.5")}>
              <div className={cn("max-w-[80%] px-3.5 py-2 text-[15px] leading-snug whitespace-pre-wrap break-words",
                mine ? "rounded-2xl rounded-br-md bg-primary text-primary-foreground" : "rounded-2xl rounded-bl-md bg-card ring-1 ring-border/60",
                m.pending && "opacity-70")}>
                {m.body}
              </div>
              {m.failed ? (
                <button type="button" onClick={() => retry(m)} className="mt-0.5 flex h-8 items-center gap-1 text-[12px] font-medium text-destructive">
                  <RotateCcw className="size-3" /> Not sent. Tap to retry
                </button>
              ) : !messages.data![i + 1] || messages.data![i + 1].sender?.id !== m.sender?.id ? (
                <span className="mt-0.5 px-1 text-[11px] text-muted-foreground">{m.pending ? "Sending…" : format(parseISO(m.created_at), "h:mm a")}</span>
              ) : null}
            </div>
          );
        })}
        <div ref={bottom} />
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); submit(text); setText(""); }}
        className="pb-safe fixed inset-x-0 bottom-0 z-30 border-t border-border/60 bg-background/95 backdrop-blur"
      >
        <div className="mx-auto flex max-w-md items-end gap-2 px-4 py-2.5">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(text); setText(""); } }}
            rows={1}
            placeholder="Message"
            aria-label="Message"
            className="max-h-32 min-h-11 flex-1 resize-none rounded-3xl bg-card px-4 py-2.5 text-base ring-1 ring-border outline-none [field-sizing:content] focus-visible:ring-2 focus-visible:ring-ring"
          />
          <button type="submit" aria-label="Send" disabled={!text.trim()}
            className="flex size-11 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground disabled:opacity-40">
            <ArrowUp className="size-5" strokeWidth={2.5} />
          </button>
        </div>
      </form>
    </div>
  );
}
