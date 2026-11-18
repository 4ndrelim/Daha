import Link from "next/link";
import { Lock } from "lucide-react";
import type { ReactNode } from "react";
import type { Community } from "@/lib/api/types";
import { plural } from "@/lib/format";

export function CommunityRow({ c, action }: { c: Community; action?: ReactNode }) {
  return (
    <div className="flex min-h-16 items-center gap-3 rounded-2xl bg-card px-4 py-3 shadow-sm ring-1 ring-border/60">
      <Link href={`/communities/${c.slug}`} className="flex min-w-0 flex-1 items-center gap-3">
        <span className="text-2xl" aria-hidden>{c.emoji ?? "👥"}</span>
        <span className="min-w-0">
          <span className="flex items-center gap-1.5 font-medium">
            <span className="truncate">{c.name}</span>
            {c.is_private && <Lock className="size-3.5 shrink-0 text-muted-foreground" aria-label="Private" />}
          </span>
          <span className="block truncate text-[13px] text-muted-foreground">
            {plural(c.member_count, "member")}
            {c.is_member || !c.is_private ? ` · ${plural(c.item_count, "thing")} · ${plural(c.open_request_count, "ask")}` : ""}
          </span>
        </span>
      </Link>
      {action}
    </div>
  );
}
