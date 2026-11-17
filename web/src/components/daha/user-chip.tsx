import Link from "next/link";
import type { UserRef } from "@/lib/api/types";
import { UserAvatar } from "./user-avatar";

export function UserChip({ user, link = true }: { user: UserRef; link?: boolean }) {
  const body = (
    <span className="inline-flex items-center gap-2">
      <UserAvatar user={user} className="size-7" />
      <span className="text-[15px] font-medium">{user.name}</span>
      {user.rating_avg !== null && <span className="text-[13px] text-muted-foreground">★ {user.rating_avg.toFixed(1)}</span>}
    </span>
  );
  return link ? <Link href={`/u/${user.id}`}>{body}</Link> : body;
}
