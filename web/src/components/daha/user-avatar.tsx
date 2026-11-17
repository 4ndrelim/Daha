import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import type { UserRef } from "@/lib/api/types";
import { initials } from "@/lib/format";
import { cn } from "@/lib/utils";

const COLORS = ["bg-emerald-100 text-emerald-800", "bg-amber-100 text-amber-800", "bg-sky-100 text-sky-800",
  "bg-rose-100 text-rose-800", "bg-violet-100 text-violet-800", "bg-teal-100 text-teal-800"];

export function UserAvatar({ user, className }: { user: Pick<UserRef, "id" | "name" | "avatar_url">; className?: string }) {
  return (
    <Avatar className={cn("size-8", className)}>
      {user.avatar_url && <AvatarImage src={user.avatar_url} alt="" />}
      <AvatarFallback className={cn("text-[12px] font-semibold", COLORS[user.id % COLORS.length])}>
        {initials(user.name)}
      </AvatarFallback>
    </Avatar>
  );
}
