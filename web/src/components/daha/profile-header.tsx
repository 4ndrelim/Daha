import type { UserPublic } from "@/lib/api/types";
import { Progress } from "@/components/ui/progress";
import { formatUsd } from "@/lib/value";
import { UserAvatar } from "./user-avatar";

export function LevelBar({ user }: { user: UserPublic }) {
  const { level, points } = user;
  if (level.next_level_points === null) {
    return <p className="text-[13px] font-medium text-reward-700">🏆 Top level reached · {points} points</p>;
  }
  const span = level.next_level_points - level.min_points;
  const pct = Math.max(4, Math.min(100, Math.round(((points - level.min_points) / span) * 100)));
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-[12px]">
        <span className="font-semibold">{level.name}</span>
        <span className="text-muted-foreground">{level.next_level_points - points} pts to {level.next_level_name}</span>
      </div>
      <Progress value={pct} aria-label={`${pct}% to ${level.next_level_name}`} className="h-2 [&_[data-slot=progress-indicator]]:bg-points" />
    </div>
  );
}

export function ProfileHeader({ user, dormName }: { user: UserPublic; dormName?: string | null }) {
  return (
    <header className="space-y-4 rounded-3xl bg-card p-4 shadow-sm ring-1 ring-border/60">
      <div className="flex items-center gap-3.5">
        <UserAvatar user={user} className="size-16 text-lg" />
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-[22px] leading-7 font-semibold">{user.name}</h1>
          <p className="truncate text-[13px] text-muted-foreground">{dormName ?? user.dorm_name ?? "No dorm yet"} · {user.level.name}</p>
        </div>
        <div className="shrink-0 rounded-2xl bg-points-soft px-3 py-2 text-center">
          <p className="text-[18px] leading-5 font-bold text-reward-700">{user.points}</p>
          <p className="text-[11px] font-medium text-reward-800">points</p>
        </div>
      </div>
      {user.bio && <p className="text-[14px]">{user.bio}</p>}
      <dl className="grid grid-cols-3 gap-2 text-center">
        <div className="rounded-xl bg-muted py-2"><dt className="text-[11px] text-muted-foreground">Rating</dt><dd className="font-semibold">{user.rating_avg !== null ? `★ ${user.rating_avg.toFixed(1)}` : "—"}<span className="text-[11px] font-normal text-muted-foreground">{user.rating_count ? ` (${user.rating_count})` : ""}</span></dd></div>
        <div className="rounded-xl bg-muted py-2"><dt className="text-[11px] text-muted-foreground">Handoffs</dt><dd className="font-semibold">{user.completed_count}</dd></div>
        <div className="rounded-xl bg-muted py-2"><dt className="text-[11px] text-muted-foreground">Sharing</dt><dd className="font-semibold">{user.items_shared_count}</dd></div>
      </dl>
      {user.value_shared_usd != null && (
        <p className="flex items-baseline justify-between gap-2 rounded-xl bg-muted px-3 py-2 text-[13px]">
          <span><span className="font-medium">Value shared</span> <span className="text-muted-foreground">· completed exchanges</span></span>
          <span className="font-semibold tabular-nums">{formatUsd(user.value_shared_usd)}</span>
        </p>
      )}
      <LevelBar user={user} />
      {user.badges.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="Badges">
          {user.badges.map((b) => (
            <li key={b.code} title={b.description} className="flex items-center gap-1.5 rounded-full bg-points-soft px-3 py-1 text-[13px] font-medium text-reward-900 ring-1 ring-reward-200">
              <span aria-hidden>{b.emoji}</span> {b.name}
            </li>
          ))}
        </ul>
      )}
    </header>
  );
}
