"use client";

import { useMemo, useState } from "react";
import { Check, Lock } from "lucide-react";
import { toast } from "sonner";
import { ApiError } from "@/lib/api";
import type { ItemCreate } from "@/lib/api/types";
import { useMyItems, useSaveHaves } from "@/lib/queries/scans";
import { PrimaryButton } from "@/components/daha/form";
import { cn } from "@/lib/utils";
import { COMMON_HAVES } from "./commonHaves";

const norm = (s: string) => s.trim().toLowerCase();

/**
 * C5 "Tick what you have": ticked things become *private* items (only you see them) with pings on,
 * so DAHA can quietly ask you when someone nearby needs one.
 */
export function HavesChecklist({ title = "Tick what you have", onSaved, className }: {
  title?: string; onSaved?: (count: number) => void; className?: string;
}) {
  const mine = useMyItems();
  const save = useSaveHaves();
  const [picked, setPicked] = useState<Set<string>>(() => new Set());
  const [savedNow, setSavedNow] = useState<Set<string>>(() => new Set());

  const owned = useMemo(() => new Set((mine.data ?? []).map((i) => norm(i.name))), [mine.data]);
  const isOwned = (key: string, name: string) => savedNow.has(key) || owned.has(norm(name));

  function toggle(key: string) {
    setPicked((s) => {
      const next = new Set(s);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const chosen = COMMON_HAVES.filter((h) => picked.has(h.key) && !isOwned(h.key, h.name));

  function submit() {
    if (chosen.length === 0 || save.isPending) return;
    const items: ItemCreate[] = chosen.map((h) => ({
      name: h.name, category: h.category, transaction_type: h.type, quantity: 1,
      visibility: "private", pings_enabled: true, image_upload_ids: [],
    }));
    save.mutate(items, {
      onSuccess: (res) => {
        const n = res.items.length;
        setSavedNow((s) => new Set([...s, ...chosen.map((h) => h.key)]));
        setPicked(new Set());
        toast.success(`Saved ${n} ${n === 1 ? "thing" : "things"} privately. We'll ping you if someone nearby needs one.`);
        onSaved?.(n);
      },
      onError: (e) => toast.error(e instanceof ApiError ? e.detail : "Couldn't save. Try again?"),
    });
  }

  return (
    <section className={cn("rounded-3xl bg-card p-4 shadow-sm ring-1 ring-border/60", className)}>
      <h2 className="text-[17px] font-semibold">{title}</h2>
      <p className="mt-1 flex items-start gap-1.5 text-[13px] text-muted-foreground">
        <Lock className="mt-0.5 size-3.5 shrink-0" aria-hidden />
        Private: only you see this list. When someone nearby needs one, we&apos;ll ask you quietly. They won&apos;t know it&apos;s you unless you offer.
      </p>
      <ul className="mt-3 flex flex-wrap gap-2">
        {COMMON_HAVES.map((h) => {
          const has = isOwned(h.key, h.name);
          const on = has || picked.has(h.key);
          return (
            <li key={h.key}>
              <button
                type="button"
                disabled={has}
                aria-pressed={on}
                onClick={() => toggle(h.key)}
                className={cn(
                  "inline-flex h-11 items-center gap-1.5 rounded-full px-3.5 text-[14px] font-medium ring-1 transition active:scale-[0.98]",
                  on ? "bg-primary-soft text-accent-foreground ring-primary" : "bg-card text-foreground ring-border",
                  has && "opacity-70",
                )}
              >
                <span aria-hidden>{h.emoji}</span>
                {h.name}
                {on && <Check className="size-4" aria-hidden />}
              </button>
            </li>
          );
        })}
      </ul>
      <PrimaryButton type="button" className="mt-4" disabled={chosen.length === 0} loading={save.isPending} onClick={submit}>
        {chosen.length === 0 ? "Tick the things you have" : `Save ${chosen.length} privately`}
      </PrimaryButton>
    </section>
  );
}
