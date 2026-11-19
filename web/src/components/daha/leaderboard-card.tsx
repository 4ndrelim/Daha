"use client";

import Link from "next/link";
import { useQueries } from "@tanstack/react-query";
import { ChevronRight, Trophy } from "lucide-react";
import { getLeaderboard, type LeaderboardPeriod } from "@/lib/api/leaderboard";
import { AwardBadge } from "./award-badge";

const PERIODS: LeaderboardPeriod[] = ["week", "all"];

/**
 * Your own profile: any podium award you hold, plus the way into the leaderboard.
 * Only shown to you: the board uses nicknames, so putting awards on public profiles
 * (which show real names) would reveal who is behind each nickname.
 */
export function LeaderboardCard() {
  const boards = useQueries({ queries: PERIODS.map((period) => ({ queryKey: ["leaderboard", period], queryFn: () => getLeaderboard(period) })) });
  const awards = boards.flatMap((b, i) => (b.data?.me.award ? [{ award: b.data.me.award, period: PERIODS[i] }] : []));
  const me = boards[0].data?.me;
  return (
    <section className="space-y-2.5">
      {awards.map((a) => <AwardBadge key={a.period} award={a.award} period={a.period} showQuip />)}
      <Link href="/leaderboard" className="flex min-h-14 items-center gap-3 rounded-2xl bg-card px-4 ring-1 ring-border/60 active:bg-muted">
        <Trophy className="size-5 text-reward-600" />
        <span className="min-w-0 flex-1">
          <span className="block font-semibold">Leaderboard</span>
          <span className="block truncate text-[13px] text-muted-foreground">
            {me?.opted_in ? (me.rank ? `#${me.rank} this week as ${me.nickname}` : `You're on as ${me.nickname}`) : "See who's sharing most · you're hidden until you join"}
          </span>
        </span>
        <ChevronRight className="size-5 text-muted-foreground" />
      </Link>
    </section>
  );
}
