"use client";

import { Check, Globe, Home, Lock, Users } from "lucide-react";
import type { CommunityRef, ID, Visibility } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const OPTIONS: { value: Visibility; label: string; hint: string; icon: typeof Home }[] = [
  { value: "dorm", label: "My dorm", hint: "Only people in your dorm", icon: Home },
  { value: "campus", label: "Campus", hint: "Anyone at Stanford on DAHA", icon: Globe },
  { value: "groups", label: "Groups", hint: "Only the groups you pick", icon: Users },
  { value: "private", label: "Private: only me", hint: "Nobody sees it. We quietly ping you if someone needs one", icon: Lock },
];

export function VisibilityPicker({ value, onChange, groupIds, onGroupIds, groups, dormName, allowPrivate = true }: {
  value: Visibility; onChange: (v: Visibility) => void; groupIds: ID[]; onGroupIds: (ids: ID[]) => void;
  groups: CommunityRef[]; dormName?: string | null; allowPrivate?: boolean;
}) {
  const options = OPTIONS.filter((o) => (allowPrivate || o.value !== "private") && (o.value !== "groups" || groups.length > 0));
  return (
    <div className="space-y-2" role="radiogroup" aria-label="Who can see this">
      {options.map((o) => {
        const on = o.value === value;
        const Icon = o.icon;
        return (
          <div key={o.value} className={cn("rounded-2xl bg-card ring-1 transition", on ? "ring-2 ring-primary" : "ring-border/70")}>
            <button
              type="button"
              role="radio"
              aria-checked={on}
              onClick={() => onChange(o.value)}
              className="flex min-h-14 w-full items-center gap-3 px-4 py-2.5 text-left"
            >
              <Icon className={cn("size-5 shrink-0", on ? "text-primary" : "text-muted-foreground")} />
              <span className="flex-1">
                <span className="block font-medium">{o.value === "dorm" && dormName ? `My dorm · ${dormName}` : o.label}</span>
                <span className="block text-[13px] text-muted-foreground">{o.hint}</span>
              </span>
              {on && <Check className="size-5 text-primary" />}
            </button>
            {on && o.value === "groups" && (
              <div className="flex flex-wrap gap-2 px-4 pb-3">
                {groups.map((g) => {
                  const sel = groupIds.includes(g.id);
                  return (
                    <button
                      key={g.id}
                      type="button"
                      aria-pressed={sel}
                      onClick={() => onGroupIds(sel ? groupIds.filter((x) => x !== g.id) : [...groupIds, g.id])}
                      className={cn("h-10 rounded-full px-3.5 text-[14px] font-medium ring-1",
                        sel ? "bg-primary-soft text-accent-foreground ring-primary/50" : "ring-border")}
                    >
                      {g.emoji ?? "👥"} {g.name}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
