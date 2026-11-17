"use client";

import Link from "next/link";
import { Bell, MessageCircle } from "lucide-react";
import { useMe } from "@/lib/queries/me";
import { cn } from "@/lib/utils";

function CountBadge({ count }: { count: number }) {
  if (count <= 0) return null;
  return (
    <span className="absolute -top-0.5 -right-0.5 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-destructive px-1 text-[11px] font-semibold leading-none text-white">
      {count > 9 ? "9+" : count}
    </span>
  );
}

export function TopBar() {
  const { data: me } = useMe();
  const iconBtn = "relative flex size-11 items-center justify-center rounded-full text-foreground hover:bg-muted";
  return (
    <header className="pt-safe sticky top-0 z-30 border-b border-border/60 bg-background/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-md items-center gap-2 px-4">
        <Link href="/home" className="text-[22px] font-extrabold tracking-tight text-primary">
          daha
        </Link>
        {me?.dorm && (
          <Link
            href={`/communities/${me.dorm.slug}`}
            className="ml-1 truncate rounded-full bg-primary-soft px-3 py-1 text-[13px] font-medium text-accent-foreground"
          >
            {me.dorm.emoji ?? "🏠"} {me.dorm.name}
          </Link>
        )}
        <div className="ml-auto flex items-center">
          <Link href="/notifications" aria-label="Notifications" className={cn(iconBtn)}>
            <Bell className="size-[22px]" />
            <CountBadge count={me?.unread_notifications ?? 0} />
          </Link>
          <Link href="/messages" aria-label="Messages" className={cn(iconBtn)}>
            <MessageCircle className="size-[22px]" />
            <CountBadge count={me?.unread_messages ?? 0} />
          </Link>
        </div>
      </div>
    </header>
  );
}
