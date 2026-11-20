"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Minus, Plus } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import type { Category, Condition, ID, ItemCreate, ItemDetail, TransactionType, Visibility } from "@/lib/api/types";
import { CATEGORIES, categoryInfo, CONDITION_LABEL, TX_TYPE_LABEL } from "@/lib/categories";
import { datesProblem } from "@/lib/availability";
import { useMe } from "@/lib/queries/me";
import { valueExchangeOn } from "@/lib/value";
import { invalidatePool } from "@/lib/api/mock/pool";
import { AvailabilityFields } from "@/components/daha/availability-fields";
import { ChoicePills } from "@/components/daha/choice-pills";
import { Field, fieldClass, PrimaryButton } from "@/components/daha/form";
import { PhotoPicker, type PickedPhoto } from "@/components/daha/photo-picker";
import { ValueInput } from "@/components/daha/value-input";
import { VisibilityPicker } from "@/components/daha/visibility-picker";
import { ErrorState } from "@/components/daha/states";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const CATEGORY_SET = new Set<string>(CATEGORIES.map((c) => c.value));
const DEFAULT_TYPE: Record<Category, TransactionType> = {
  academic: "lend", tech: "lend", clothing: "lend", dorm: "lend", consumables: "give",
  sports: "lend", moving: "lend", events: "lend", services: "give", other: "lend",
};

interface FormState {
  name: string; description: string; category: Category | null; quantity: number; condition: Condition | null;
  type: TransactionType; maxLendDays: string; from: string; until: string;
  visibility: Visibility; groupIds: ID[]; placeId: ID | null; note: string;
  value: number | null;
}

function fromItem(i: ItemDetail): FormState {
  return {
    name: i.name, description: i.description ?? "", category: i.category, quantity: i.quantity, condition: i.condition,
    type: i.transaction_type, maxLendDays: i.max_lend_days ? String(i.max_lend_days) : "",
    from: i.available_from ?? "", until: i.available_until ?? "", visibility: i.visibility, groupIds: i.group_ids,
    placeId: i.pickup_place?.id ?? null, note: i.pickup_note ?? "", value: i.value_usd ?? null,
  };
}

export function ItemForm() {
  const params = useSearchParams();
  const editId = Number(params.get("edit")) || null;
  const existing = useQuery({ queryKey: ["item", editId], queryFn: () => api.items.get(editId!), enabled: editId !== null });

  if (editId === null) {
    const presetCat = params.get("category");
    const category = presetCat && CATEGORY_SET.has(presetCat) ? (presetCat as Category) : null;
    const initial: FormState = {
      name: params.get("name") ?? "", description: "", category, quantity: 1, condition: null,
      type: category ? DEFAULT_TYPE[category] : "lend", maxLendDays: "", from: "", until: "",
      visibility: params.get("visibility") === "private" ? "private" : "dorm", groupIds: [], placeId: null, note: "",
      value: null,
    };
    return <ItemFormBody editId={null} initial={initial} initialPhotos={[]} />;
  }
  if (existing.isPending) return <div className="space-y-3"><Skeleton className="h-8 w-1/2" /><Skeleton className="h-40" /></div>;
  if (existing.isError) return <ErrorState message="Couldn't load this item." onRetry={() => existing.refetch()} />;
  return (
    <ItemFormBody
      key={existing.data.id}
      editId={editId}
      initial={fromItem(existing.data)}
      initialPhotos={existing.data.images.map((img) => ({ key: `img-${img.id}`, preview: img.url, upload: null }))}
    />
  );
}

function ItemFormBody({ editId, initial, initialPhotos }: { editId: ID | null; initial: FormState; initialPhotos: PickedPhoto[] }) {
  const router = useRouter();
  const { data: me } = useMe();
  const qc = useQueryClient();
  const places = useQuery({ queryKey: ["places"], queryFn: () => api.places.list() });
  const [f, setF] = useState<FormState>(initial);
  const [photos, setPhotos] = useState<PickedPhoto[]>(initialPhotos);
  const [errors, setErrors] = useState<{ name?: string; category?: string; groups?: string }>({});

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => setF((s) => ({ ...s, [k]: v }));
  const exchange = valueExchangeOn(me);
  // Value exchange: a starting value from a cached store price (never a paid call). Owner can change it.
  const [estimateFrom, setEstimateFrom] = useState<"store" | "ai" | null>(null);
  const suggestValue = async () => {
    if (!exchange || editId !== null || f.value !== null || f.name.trim().length < 3) return;
    try {
      const est = await api.items.valueEstimate(f.name.trim());
      if (est.value_usd === null) return;
      setF((s) => (s.value === null ? { ...s, value: est.value_usd } : s));
      setEstimateFrom(est.source);
    } catch { /* no estimate: the field stays empty */ }
  };

  const pickCategory = (c: Category) => setF((s) => ({
    ...s, category: c,
    // Services can't be lent; otherwise follow the category's usual type until the person picks one.
    type: c === "services" && s.type === "lend" ? "give" : s.type === DEFAULT_TYPE[s.category ?? "other"] ? DEFAULT_TYPE[c] : s.type,
  }));

  const save = useMutation({
    mutationFn: async (): Promise<ItemDetail> => {
      const body: ItemCreate = {
        name: f.name.trim(),
        description: f.description.trim() || null,
        category: f.category!,
        quantity: f.quantity,
        condition: f.condition,
        transaction_type: f.type,
        max_lend_days: f.type === "lend" && Number(f.maxLendDays) > 0 ? Number(f.maxLendDays) : null,
        available_from: f.from || null,
        available_until: f.until || null,
        visibility: f.visibility,
        group_ids: f.visibility === "groups" ? f.groupIds : [],
        pickup_place_id: f.placeId,
        pickup_note: f.note.trim() || null,
        ...(me?.item_value_enabled ? { value_usd: f.value } : {}),
      };
      const newUploads = photos.flatMap((p) => (p.upload ? [p.upload.id] : []));
      if (editId) {
        // Existing photos can't be re-sent as upload ids; only replace them if new ones were added.
        return api.items.update(editId, newUploads.length ? { ...body, image_upload_ids: newUploads } : body);
      }
      return api.items.create({ ...body, image_upload_ids: newUploads });
    },
    onSuccess: (item) => {
      invalidatePool();
      qc.invalidateQueries({ queryKey: ["feed"] });
      qc.invalidateQueries({ queryKey: ["me"] });
      qc.setQueryData(["item", item.id], item);
      toast.success(editId ? "Saved." : item.visibility === "private" ? "Added privately. We'll ping you if someone needs it." : "Shared! Your neighbors can see it now.");
      router.replace(`/items/${item.id}`);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : "Couldn't save. Try again?"),
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const errs: typeof errors = {};
    if (!f.name.trim()) errs.name = "What is it?";
    if (!f.category) errs.category = "Pick a category";
    if (f.visibility === "groups" && f.groupIds.length === 0) errs.groups = "Pick at least one group";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    const dates = datesProblem(f.from, f.until); // also shown under the date fields
    if (dates) { toast.error(dates); return; }
    if (photos.some((p) => !p.upload && !p.key.startsWith("img-"))) {
      toast.message("Wait a sec, photos are still uploading.");
      return;
    }
    save.mutate();
  }

  const typeOptions = (Object.keys(TX_TYPE_LABEL) as TransactionType[]).map((t) => ({
    value: t, label: TX_TYPE_LABEL[t], disabled: t === "lend" && f.category === "services",
  }));

  return (
    <form onSubmit={submit} className="space-y-6 pb-4" noValidate>
      <h1 className="text-[22px] leading-7 font-semibold">{editId ? "Edit item" : "List an item"}</h1>

      <section className="space-y-2">
        <PhotoPicker photos={photos} onChange={setPhotos} />
        <p className="text-[13px] text-muted-foreground">Optional. Up to 6; the first is the cover. No faces or documents, please.</p>
      </section>

      <Field label="What is it?" htmlFor="name" error={errors.name}>
        <input id="name" value={f.name} onChange={(e) => set("name", e.target.value)} onBlur={suggestValue} placeholder="e.g. TI-84 calculator"
          className={fieldClass} aria-invalid={!!errors.name} maxLength={120} />
      </Field>

      <fieldset>
        <legend className="mb-2 text-[13px] font-medium">Category</legend>
        <div className="grid grid-cols-2 gap-2">
          {CATEGORIES.map((c) => (
            <button
              key={c.value}
              type="button"
              aria-pressed={f.category === c.value}
              onClick={() => pickCategory(c.value)}
              className={cn("flex h-12 items-center gap-2 rounded-xl px-3 text-left text-[14px] font-medium ring-1",
                f.category === c.value ? "bg-primary-soft text-accent-foreground ring-2 ring-primary" : "bg-card ring-border")}
            >
              <span aria-hidden>{c.emoji}</span> {c.label}
            </button>
          ))}
        </div>
        {errors.category && <p className="mt-1.5 text-[13px] text-destructive">{errors.category}</p>}
      </fieldset>

      {me?.item_value_enabled && (
        <Field label={exchange ? "Estimated value (optional)" : "Value (optional)"} htmlFor="value"
          hint={exchange ? "About what it costs new, in US dollars. An estimate only: no money changes hands."
            : "About what it costs new, in US dollars. Just so people know; it never changes points."}>
          <ValueInput id="value" value={f.value} onChange={(v) => { set("value", v); setEstimateFrom(null); }}
            estimate={estimateFrom !== null} estimateLabel={estimateFrom === "store" ? "store price" : "estimate"}
            className="w-full max-w-48" />
        </Field>
      )}

      <Field label="Description" htmlFor="desc" hint="Size, color, anything people should know.">
        <textarea id="desc" value={f.description} onChange={(e) => set("description", e.target.value)} rows={3}
          className={cn(fieldClass, "h-auto py-3")} maxLength={1000} />
      </Field>

      <div className="flex items-center justify-between">
        <span className="text-[13px] font-medium">How many?</span>
        <div className="flex items-center gap-1 rounded-full bg-card ring-1 ring-border">
          <button type="button" aria-label="Fewer" onClick={() => set("quantity", Math.max(1, f.quantity - 1))} className="flex size-11 items-center justify-center rounded-full active:bg-muted"><Minus className="size-4" /></button>
          <span className="w-6 text-center font-semibold" aria-live="polite">{f.quantity}</span>
          <button type="button" aria-label="More" onClick={() => set("quantity", Math.min(99, f.quantity + 1))} className="flex size-11 items-center justify-center rounded-full active:bg-muted"><Plus className="size-4" /></button>
        </div>
      </div>

      <ChoicePills<Condition | null>
        label="Condition"
        value={f.condition}
        onChange={(v) => set("condition", v)}
        options={[{ value: null, label: "Skip" }, ...(Object.keys(CONDITION_LABEL) as Condition[]).map((c) => ({ value: c, label: CONDITION_LABEL[c] }))]}
      />

      <div className="space-y-2">
        <ChoicePills<TransactionType> label="How do you want to share it?" value={f.type} onChange={(v) => set("type", v)} options={typeOptions} />
        <p className="text-[13px] text-muted-foreground">
          {f.type === "lend" ? "You get it back." : f.type === "give" ? "Free, they keep it." : "Trade it for something of theirs."}
          {f.category === "services" && " Services can be free or a swap."}
        </p>
      </div>

      {f.type === "lend" && (
        <Field label="Longest you'd lend it (days)" htmlFor="days" hint="Optional.">
          <input id="days" type="number" inputMode="numeric" min={1} max={365} value={f.maxLendDays}
            onChange={(e) => set("maxLendDays", e.target.value)} placeholder="e.g. 7" className={fieldClass} />
        </Field>
      )}

      <AvailabilityFields idPrefix="item" from={f.from} until={f.until} onChange={(patch) => setF((prev) => ({ ...prev, ...patch }))} />

      <section className="space-y-2">
        <h2 className="text-[13px] font-medium">Who can see it?</h2>
        <VisibilityPicker
          value={f.visibility}
          onChange={(v) => set("visibility", v)}
          groupIds={f.groupIds}
          onGroupIds={(ids) => set("groupIds", ids)}
          groups={me?.groups ?? []}
          dormName={me?.dorm?.name}
        />
        {errors.groups && <p className="text-[13px] text-destructive">{errors.groups}</p>}
      </section>

      {f.visibility !== "private" && (
        <section className="space-y-4">
          <Field label="Pickup spot" htmlFor="place" hint="A public place. Leave empty to hand off at your dorm.">
            <select id="place" value={f.placeId ?? ""} onChange={(e) => set("placeId", e.target.value ? Number(e.target.value) : null)}
              className={cn(fieldClass, "appearance-none")}>
              <option value="">At my dorm</option>
              {places.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </Field>
          <Field label="Private pickup note" htmlFor="note" hint="🔒 Only shared after you accept someone, e.g. &quot;Room 214, text me first&quot;.">
            <input id="note" value={f.note} onChange={(e) => set("note", e.target.value)} className={fieldClass} maxLength={300} />
          </Field>
        </section>
      )}

      <div className="pb-safe sticky bottom-[calc(5.5rem+env(safe-area-inset-bottom))] z-10 -mx-4 bg-gradient-to-t from-background via-background to-transparent px-4 pt-4">
        <PrimaryButton type="submit" loading={save.isPending}>
          {editId ? "Save changes" : f.visibility === "private" ? "Add privately" : `Share ${f.category ? categoryInfo(f.category).emoji : ""}`.trim()}
        </PrimaryButton>
      </div>
    </form>
  );
}
