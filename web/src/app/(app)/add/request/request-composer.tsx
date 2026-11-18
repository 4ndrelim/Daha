"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { addDays, format, parseISO } from "date-fns";
import { ChevronDown, Gift, Loader2, Pencil } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError, track } from "@/lib/api";
import type { Category, ID, ParsedRequest, TransactionType, Visibility } from "@/lib/api/types";
import { CATEGORIES, categoryInfo, TX_TYPE_LABEL } from "@/lib/categories";
import { shortDate } from "@/lib/format";
import { useMe } from "@/lib/queries/me";
import { invalidatePool } from "@/lib/api/mock/pool";
import { InfoChip } from "@/components/daha/chips";
import { ChoicePills } from "@/components/daha/choice-pills";
import { Field, fieldClass, PrimaryButton } from "@/components/daha/form";
import { VisibilityPicker } from "@/components/daha/visibility-picker";
import { cn } from "@/lib/utils";

const EXAMPLES = [
  "Can I borrow a black binder next Wednesday?",
  "need a phone charger (usb-c) for tonight",
  "anyone have spices I could use? making curry",
  "Does anyone have a vacuum?",
];

const ASK_LABEL: Record<TransactionType, string> = { lend: "Borrow", give: "Keep (free)", exchange: "Swap" };

type Overrides = Partial<Pick<ParsedRequest, "item_name" | "category" | "needed_from" | "duration_days" | "transaction_type">>;

export function RequestComposer() {
  const router = useRouter();
  const params = useSearchParams();
  const qc = useQueryClient();
  const { data: me } = useMe();

  const [text, setText] = useState(params.get("text") ?? "");
  const [debounced, setDebounced] = useState(text.trim());
  const [overrides, setOverrides] = useState<Overrides>({});
  const [editing, setEditing] = useState(false);
  const [showVisibility, setShowVisibility] = useState(false);

  const communityId = Number(params.get("community")) || null;
  const [visibility, setVisibility] = useState<Visibility | null>(null);
  const [groupIds, setGroupIds] = useState<ID[] | null>(null);
  // ?community=<id> presets the audience once we know which kind of community it is.
  const preset = useMemo((): { v: Visibility; g: ID[] } => {
    if (communityId && me?.groups.some((g) => g.id === communityId)) return { v: "groups", g: [communityId] };
    if (communityId && me?.dorm?.id !== communityId && me) return { v: "campus", g: [] };
    return { v: "dorm", g: [] };
  }, [communityId, me]);
  const vis = visibility ?? (me && !me.dorm ? "campus" : preset.v);
  const groups = groupIds ?? preset.g;

  const opened = useRef(false);
  useEffect(() => {
    if (opened.current) return;
    opened.current = true;
    track("request_composer_opened", { prefilled: !!params.get("text"), community_id: communityId });
  }, [params, communityId]);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(text.trim()), 400);
    return () => clearTimeout(t);
  }, [text]);

  const parse = useQuery({
    queryKey: ["parse", debounced],
    queryFn: () => api.ai.parseRequest({ text: debounced }),
    enabled: debounced.length >= 3,
    placeholderData: (prev) => prev,
    staleTime: Infinity,
  });
  const parsed = debounced.length >= 3 ? parse.data : undefined;
  const eff = parsed ? { ...parsed, ...overrides } : null;

  const neededUntil = eff?.needed_from && eff.duration_days ? format(addDays(parseISO(eff.needed_from), eff.duration_days), "yyyy-MM-dd") : parsed?.needed_until ?? null;
  const title = eff?.item_name ? eff.item_name.charAt(0).toUpperCase() + eff.item_name.slice(1) : parsed?.title || text.trim().slice(0, 80);

  const post = useMutation({
    mutationFn: () => api.requests.create({
      raw_text: text.trim(),
      title,
      item_name: eff?.item_name ?? null,
      category: eff?.category ?? null,
      attributes: parsed?.attributes ?? {},
      quantity: parsed?.quantity ?? 1,
      needed_from: eff?.needed_from ?? null,
      needed_until: neededUntil,
      duration_days: eff?.duration_days ?? null,
      transaction_type: eff?.transaction_type ?? null,
      visibility: vis,
      group_ids: vis === "groups" ? groups : [],
    }),
    onSuccess: (r) => {
      track("request_posted", { request_id: r.id, category: r.category, visibility: r.visibility, edited_chips: Object.keys(overrides).length });
      invalidatePool();
      qc.invalidateQueries({ queryKey: ["feed"] });
      toast.success("Posted! We're finding people who have one.");
      router.replace(`/requests/${r.id}`);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : "Couldn't post. Try again?"),
  });

  const canPost = text.trim().length >= 3 && !(vis === "groups" && groups.length === 0);
  const visLabel = vis === "dorm" ? `My dorm${me?.dorm ? ` · ${me.dorm.name}` : ""}` : vis === "campus" ? "Campus"
    : `${groups.length} ${groups.length === 1 ? "group" : "groups"}`;

  return (
    <form onSubmit={(e) => { e.preventDefault(); if (canPost) post.mutate(); }} className="space-y-5 pb-4">
      <h1 className="text-[22px] leading-7 font-semibold">What do you need?</h1>

      <div className="rounded-3xl bg-card p-1 shadow-sm ring-1 ring-border focus-within:ring-2 focus-within:ring-ring">
        <textarea
          autoFocus
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={4}
          maxLength={500}
          placeholder="Ask like you would in the dorm chat…"
          aria-label="What do you need?"
          className="w-full resize-none bg-transparent px-3.5 py-3 text-[17px] leading-snug outline-none placeholder:text-muted-foreground"
        />
      </div>

      {!text && (
        <div className="space-y-2">
          <p className="text-[13px] font-semibold text-muted-foreground">For example</p>
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((ex) => (
              <button key={ex} type="button" onClick={() => setText(ex)}
                className="rounded-2xl bg-card px-3 py-2 text-left text-[14px] ring-1 ring-border active:bg-muted">
                {ex}
              </button>
            ))}
          </div>
        </div>
      )}

      {eff?.kind === "offer" && (
        <Link
          href={`/add/item?name=${encodeURIComponent(eff.item_name ?? "")}${eff.category ? `&category=${eff.category}` : ""}`}
          className="flex items-center gap-3 rounded-2xl bg-points-soft px-4 py-3 ring-1 ring-amber-200"
        >
          <Gift className="size-5 shrink-0 text-amber-600" />
          <span className="flex-1 text-[14px]"><span className="font-semibold">Looks like you&apos;re offering something.</span> List it instead? People can find it in search.</span>
        </Link>
      )}

      {text.trim().length >= 3 && (
        <section className="space-y-2" aria-live="polite">
          <div className="flex items-center justify-between">
            <p className="flex items-center gap-1.5 text-[13px] font-semibold text-muted-foreground">
              We understood {parse.isFetching && <Loader2 className="size-3.5 animate-spin" />}
            </p>
            {eff && (
              <button type="button" onClick={() => setEditing((v) => !v)} className="-my-1 flex h-11 items-center gap-1 rounded-full px-3 text-[13px] font-semibold text-primary active:bg-muted">
                <Pencil className="size-3.5" /> {editing ? "Done" : "Edit"}
              </button>
            )}
          </div>
          {eff && (
            <button type="button" onClick={() => setEditing(true)} aria-label="Edit what we understood" className="flex min-h-11 flex-wrap items-center gap-1.5 text-left">
              <InfoChip>{eff.item_name ? eff.item_name : "Something"}</InfoChip>
              {eff.category && <InfoChip>{categoryInfo(eff.category).emoji} {categoryInfo(eff.category).label}</InfoChip>}
              {eff.needed_from && <InfoChip>📅 {shortDate(eff.needed_from)}</InfoChip>}
              {eff.duration_days && <InfoChip>⏱ {eff.duration_days} {eff.duration_days === 1 ? "day" : "days"}</InfoChip>}
              {eff.transaction_type && <InfoChip>{ASK_LABEL[eff.transaction_type]}</InfoChip>}
            </button>
          )}

          {eff && editing && (
            <div className="space-y-4 rounded-2xl bg-card p-4 ring-1 ring-border">
              <Field label="Item" htmlFor="item">
                <input id="item" value={eff.item_name ?? ""} onChange={(e) => setOverrides((o) => ({ ...o, item_name: e.target.value || null }))} className={fieldClass} />
              </Field>
              <Field label="Category" htmlFor="cat">
                <select id="cat" value={eff.category ?? ""} className={cn(fieldClass, "appearance-none")}
                  onChange={(e) => setOverrides((o) => ({ ...o, category: (e.target.value || null) as Category | null }))}>
                  <option value="">Not sure</option>
                  {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.emoji} {c.label}</option>)}
                </select>
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Needed on" htmlFor="date">
                  <input id="date" type="date" value={eff.needed_from ?? ""} className={fieldClass}
                    onChange={(e) => setOverrides((o) => ({ ...o, needed_from: e.target.value || null }))} />
                </Field>
                <Field label="For (days)" htmlFor="dur">
                  <input id="dur" type="number" inputMode="numeric" min={1} max={60} value={eff.duration_days ?? ""} className={fieldClass}
                    onChange={(e) => setOverrides((o) => ({ ...o, duration_days: Number(e.target.value) > 0 ? Number(e.target.value) : null }))} />
                </Field>
              </div>
              <ChoicePills<TransactionType | null>
                label="You want to"
                value={eff.transaction_type}
                onChange={(v) => setOverrides((o) => ({ ...o, transaction_type: v }))}
                options={[{ value: null, label: "Any" }, ...(Object.keys(TX_TYPE_LABEL) as TransactionType[]).map((t) => ({ value: t, label: ASK_LABEL[t] }))]}
              />
            </div>
          )}
        </section>
      )}

      <section className="space-y-2">
        <button type="button" onClick={() => setShowVisibility((v) => !v)}
          className="flex min-h-12 w-full items-center justify-between gap-2 rounded-2xl bg-card px-4 py-2 text-left ring-1 ring-border">
          <span className="text-[14px]"><span className="text-muted-foreground">Who sees it: </span><span className="font-semibold">{visLabel}</span></span>
          <ChevronDown className={cn("size-5 text-muted-foreground transition", showVisibility && "rotate-180")} />
        </button>
        {showVisibility && (
          <VisibilityPicker
            value={vis}
            onChange={setVisibility}
            groupIds={groups}
            onGroupIds={setGroupIds}
            groups={me?.groups ?? []}
            dormName={me?.dorm?.name}
            allowPrivate={false}
          />
        )}
      </section>

      <div className="sticky bottom-[calc(5.5rem+env(safe-area-inset-bottom))] z-10 -mx-4 bg-gradient-to-t from-background via-background to-transparent px-4 pt-4">
        <PrimaryButton type="submit" disabled={!canPost} loading={post.isPending}>Post</PrimaryButton>
      </div>
    </form>
  );
}
