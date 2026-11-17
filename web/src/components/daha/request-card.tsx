import Link from "next/link";
import type { RequestCard as RequestCardT } from "@/lib/api/types";
import { categoryInfo } from "@/lib/categories";
import { shortDate, timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";
import { InfoChip } from "./chips";
import { UserAvatar } from "./user-avatar";

/** Chat-bubble request: avatar + name + dorm + time, a bubble with the raw text, chips, and a footer. */
export function RequestCard({ request, className, showHelp = true }: {
  request: RequestCardT; className?: string; showHelp?: boolean;
}) {
  const cat = request.category ? categoryInfo(request.category) : null;
  return (
    <div className={cn("flex gap-2.5", className)}>
      <UserAvatar user={request.requester} className="mt-0.5 size-9 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="flex items-baseline gap-1.5 text-[13px]">
          <span className="truncate font-semibold text-foreground">{request.requester.name}</span>
          <span className="truncate text-muted-foreground">
            {request.requester.dorm_name ?? request.community_label} · {timeAgo(request.created_at)}
          </span>
        </p>
        <Link
          href={`/requests/${request.id}`}
          className="mt-1 block rounded-2xl rounded-tl-md bg-card px-3.5 py-2.5 text-[15px] leading-snug shadow-sm ring-1 ring-border/60 active:bg-muted"
        >
          {request.raw_text}
          {(cat || request.needed_from) && (
            <span className="mt-2 flex flex-wrap gap-1">
              {cat && <InfoChip>{cat.emoji} {request.title}</InfoChip>}
              {request.needed_from && <InfoChip>📅 {shortDate(request.needed_from)}</InfoChip>}
            </span>
          )}
        </Link>
        <div className="mt-1.5 flex items-center justify-between gap-2 px-1 text-[13px] text-muted-foreground">
          <span>
            {request.match_count > 0
              ? `${request.match_count} ${request.match_count === 1 ? "match" : "matches"} nearby`
              : request.distance_min !== null ? `${request.distance_min} min away` : request.community_label}
            {request.offer_count > 0 && ` · ${request.offer_count} ${request.offer_count === 1 ? "offer" : "offers"}`}
          </span>
          {showHelp && request.status === "open" && (
            <Link
              href={`/requests/${request.id}?help=1`}
              className="flex h-9 items-center rounded-full bg-primary-soft px-3 font-semibold text-accent-foreground active:bg-emerald-100"
            >
              I have this
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
