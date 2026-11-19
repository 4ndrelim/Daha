import type { Review } from "@/lib/api/types";
import { timeAgo } from "@/lib/format";
import { UserAvatar } from "./user-avatar";
import { EmptyState } from "./states";

export function ReviewList({ reviews, emptyBody }: { reviews: Review[]; emptyBody: string }) {
  if (reviews.length === 0) return <EmptyState emoji="⭐" title="No reviews yet" body={emptyBody} />;
  return (
    <ul className="space-y-3">
      {reviews.map((r) => (
        <li key={r.id} className="rounded-2xl bg-card p-3.5 ring-1 ring-border/60">
          <div className="flex items-center gap-2">
            <UserAvatar user={r.reviewer} className="size-7" />
            <span className="font-medium">{r.reviewer.name}</span>
            <span className="ml-auto text-[13px] text-reward-600" aria-label={`${r.rating} stars`}>{"★".repeat(r.rating)}<span className="text-border">{"★".repeat(5 - r.rating)}</span></span>
          </div>
          {r.body && <p className="mt-2 text-[14px]">{r.body}</p>}
          <p className="mt-1 text-[12px] text-muted-foreground">{timeAgo(r.created_at)}</p>
        </li>
      ))}
    </ul>
  );
}
