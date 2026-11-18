"use client";

import { Check, Lock, MapPin } from "lucide-react";
import type { ID, Me, Place, Visibility } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { NativeSelect, Segmented, type SegmentOption } from "./controls";
import type { Defaults, DefaultType } from "./review-model";
import { TYPE_OPTIONS } from "./review-row";

export function DefaultsBar({ me, places, defaults, onChange }: {
  me: Me | undefined; places: Place[] | undefined; defaults: Defaults; onChange: (patch: Partial<Defaults>) => void;
}) {
  const groups = me?.groups ?? [];
  const visOptions: SegmentOption<Visibility>[] = [
    ...(me?.dorm ? [{ value: "dorm" as const, label: "My dorm" }] : []),
    { value: "campus", label: "Campus" },
    ...(groups.length > 0 ? [{ value: "groups" as const, label: "Groups" }] : []),
    { value: "private", label: <><Lock className="size-3.5" aria-hidden />Private</> },
  ];
  const typeOptions: SegmentOption<DefaultType>[] = [{ value: "auto", label: "Suggested" }, ...TYPE_OPTIONS];

  function toggleGroup(id: ID) {
    const has = defaults.groupIds.includes(id);
    onChange({ groupIds: has ? defaults.groupIds.filter((g) => g !== id) : [...defaults.groupIds, id] });
  }

  return (
    <section className="space-y-3 rounded-2xl bg-card p-3.5 shadow-sm ring-1 ring-border/60" aria-label="Sharing defaults">
      <div>
        <p className="mb-1.5 text-[13px] font-medium">Share with</p>
        <Segmented size="sm" label="Share with" className="flex w-full" value={defaults.visibility}
          options={visOptions} onChange={(visibility) => onChange({ visibility })} />
        {defaults.visibility === "dorm" && me?.dorm && (
          <p className="mt-1.5 text-[13px] text-muted-foreground">Everyone in {me.dorm.name.split(" (")[0]} can see and ask.</p>
        )}
        {defaults.visibility === "campus" && <p className="mt-1.5 text-[13px] text-muted-foreground">Anyone at Stanford on DAHA can see and ask.</p>}
        {defaults.visibility === "private" && (
          <p className="mt-1.5 text-[13px] text-muted-foreground">
            <span className="font-medium text-foreground">Ping me only.</span> Nobody sees these. When someone nearby needs one, we&apos;ll ask you quietly.
          </p>
        )}
        {defaults.visibility === "groups" && (
          <div className="mt-2 flex flex-wrap gap-2">
            {groups.map((gr) => {
              const on = defaults.groupIds.includes(gr.id);
              return (
                <button key={gr.id} type="button" aria-pressed={on} onClick={() => toggleGroup(gr.id)}
                  className={cn(
                    "inline-flex h-10 items-center gap-1.5 rounded-full px-3 text-[13px] font-medium ring-1",
                    on ? "bg-primary-soft text-accent-foreground ring-primary" : "ring-border",
                  )}>
                  <span aria-hidden>{gr.emoji ?? "👥"}</span>{gr.name}{on && <Check className="size-3.5" aria-hidden />}
                </button>
              );
            })}
            {defaults.groupIds.length === 0 && <p className="w-full text-[13px] text-destructive">Pick at least one group.</p>}
          </div>
        )}
      </div>

      <div>
        <p className="mb-1.5 text-[13px] font-medium">Default type</p>
        <Segmented size="sm" label="Default type" className="flex w-full" value={defaults.type}
          options={typeOptions} onChange={(type) => onChange({ type })} />
      </div>

      <div>
        <label htmlFor="pickup" className="mb-1.5 flex items-center gap-1 text-[13px] font-medium">
          <MapPin className="size-3.5" aria-hidden /> Pickup spot <span className="font-normal text-muted-foreground">(optional)</span>
        </label>
        <NativeSelect id="pickup" className="w-full" value={defaults.pickupPlaceId ?? ""}
          onChange={(e) => onChange({ pickupPlaceId: e.target.value ? Number(e.target.value) : null })}>
          <option value="">Decide later, in chat</option>
          {(places ?? []).map((p) => (
            <option key={p.id} value={p.id}>{p.name}{p.distance_min !== null ? ` · ${p.distance_min} min` : ""}</option>
          ))}
        </NativeSelect>
      </div>
    </section>
  );
}
