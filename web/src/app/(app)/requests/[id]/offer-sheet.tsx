"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Lock, Plus } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError, track } from "@/lib/api";
import type { ID, ItemCreate, OfferCreate, RequestDetail } from "@/lib/api/types";
import { categoryInfo } from "@/lib/categories";
import { firstName } from "@/lib/format";
import { overlap, tokens } from "@/lib/text";
import { invalidatePool } from "@/lib/api/mock/pool";
import { Field, fieldClass, PrimaryButton } from "@/components/daha/form";
import { ItemThumb } from "@/components/daha/item-thumb";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

const NEW = "new" as const;

/** "I can help": offer one of my items (best matches first, private ones included) or one I haven't listed yet. */
export function OfferSheet({ request, open, onOpenChange, preselect }: {
  request: RequestDetail; open: boolean; onOpenChange: (o: boolean) => void; preselect: ID | null;
}) {
  const router = useRouter();
  const qc = useQueryClient();
  const mine = useQuery({ queryKey: ["my-items"], queryFn: () => api.items.mine(), enabled: open });
  const [picked, setPicked] = useState<ID | typeof NEW | null>(preselect);
  const [name, setName] = useState(request.item_name ?? request.title);
  const [share, setShare] = useState(true);
  const [message, setMessage] = useState("");

  const options = useMemo(() => {
    const q = tokens(`${request.item_name ?? ""} ${request.title}`);
    return (mine.data ?? [])
      .filter((i) => i.status === "available")
      .map((i) => ({ i, s: overlap(tokens(i.name), q) + (request.category && i.category === request.category ? 0.5 : 0) }))
      .sort((a, b) => b.s - a.s || Number(b.i.id === preselect) - Number(a.i.id === preselect))
      .map(({ i, s }) => ({ item: i, match: s >= 1 }));
  }, [mine.data, request, preselect]);
  const selected = picked ?? (options[0]?.match ? options[0].item.id : null);

  const offer = useMutation({
    mutationFn: () => {
      let body: OfferCreate;
      if (selected === NEW) {
        const cat = request.category ?? "other";
        const newItem: ItemCreate = {
          name: name.trim(), category: cat,
          transaction_type: request.transaction_type ?? (cat === "services" || cat === "consumables" ? "give" : "lend"),
          visibility: share ? (request.visibility === "groups" ? "campus" : request.visibility) : "private",
        };
        body = { new_item: newItem, message: message.trim() || null };
      } else {
        body = { item_id: selected as ID, message: message.trim() || null };
      }
      return api.requests.offer(request.id, body);
    },
    onSuccess: (tx) => {
      const chosen = options.find((o) => o.item.id === selected)?.item;
      track("offer_sent", { request_id: request.id, source: selected === NEW ? "new_item" : chosen?.visibility === "private" ? "private_item" : "inventory" });
      invalidatePool();
      qc.invalidateQueries({ queryKey: ["request", request.id] });
      qc.invalidateQueries({ queryKey: ["my-items"] });
      toast.success(`Offered! ${firstName(request.requester.name)} will get a notification.`);
      router.push(`/messages/${tx.conversation_id}`);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : "Couldn't send the offer."),
  });

  const ready = selected === NEW ? name.trim().length > 0 : selected !== null;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="mx-auto max-h-[90dvh] max-w-md overflow-y-auto rounded-t-3xl pb-[calc(1rem+env(safe-area-inset-bottom))]">
        <SheetHeader><SheetTitle className="text-[17px]">Help {firstName(request.requester.name)} out</SheetTitle></SheetHeader>
        <form onSubmit={(e) => { e.preventDefault(); if (ready) offer.mutate(); }} className="space-y-4 px-4">
          <div className="space-y-2" role="radiogroup" aria-label="What to offer">
            {mine.isPending && <><Skeleton className="h-16 rounded-2xl" /><Skeleton className="h-16 rounded-2xl" /></>}
            {options.slice(0, 8).map(({ item, match }) => {
              const on = selected === item.id;
              return (
                <button key={item.id} type="button" role="radio" aria-checked={on} onClick={() => setPicked(item.id)}
                  className={cn("flex min-h-16 w-full items-center gap-3 rounded-2xl bg-card p-2.5 text-left ring-1", on ? "ring-2 ring-primary" : "ring-border/70")}>
                  <ItemThumb url={item.thumbnail_url} category={item.category} className="size-11 shrink-0 rounded-xl" emojiClassName="text-xl" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{item.name}</span>
                    <span className="flex items-center gap-1 text-[12px] text-muted-foreground">
                      {item.visibility === "private" && <><Lock className="size-3" /> Private · </>}
                      {match ? "Looks like a match" : categoryInfo(item.category).label}
                    </span>
                  </span>
                  {on && <Check className="size-5 text-primary" />}
                </button>
              );
            })}
            <div className={cn("rounded-2xl bg-card ring-1", selected === NEW ? "ring-2 ring-primary" : "ring-border/70")}>
              <button type="button" role="radio" aria-checked={selected === NEW} onClick={() => setPicked(NEW)}
                className="flex min-h-14 w-full items-center gap-3 px-3.5 text-left">
                <span className="flex size-9 items-center justify-center rounded-full bg-primary-soft text-accent-foreground"><Plus className="size-5" /></span>
                <span className="flex-1 font-medium">I have one that&apos;s not listed</span>
                {selected === NEW && <Check className="size-5 text-primary" />}
              </button>
              {selected === NEW && (
                <div className="space-y-3 px-3.5 pb-3.5">
                  <Field label="What is it?" htmlFor="new-name">
                    <input id="new-name" value={name} onChange={(e) => setName(e.target.value)} className={fieldClass} maxLength={120} />
                  </Field>
                  <label className="flex min-h-11 items-center justify-between gap-3">
                    <span className="text-[14px]">Also add to my shared stuff</span>
                    <Switch checked={share} onCheckedChange={setShare} />
                  </label>
                </div>
              )}
            </div>
          </div>
          <Field label="Message (optional)" htmlFor="offer-msg">
            <input id="offer-msg" value={message} onChange={(e) => setMessage(e.target.value)} placeholder="I'm around after 5 if that works" className={fieldClass} maxLength={500} />
          </Field>
          <PrimaryButton type="submit" disabled={!ready} loading={offer.isPending}>Offer it</PrimaryButton>
        </form>
      </SheetContent>
    </Sheet>
  );
}
