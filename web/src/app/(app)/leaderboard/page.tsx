"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical, Info } from "lucide-react";
import { toast } from "sonner";
import { ApiError } from "@/lib/api";
import {
  AWARDS, getLeaderboard, saveLeaderboardSettings,
  type Leaderboard, type LeaderboardEntry, type LeaderboardPeriod,
} from "@/lib/api/leaderboard";
import { useMe } from "@/lib/queries/me";
import { shortCommunityName } from "@/lib/format";
import { BackButton } from "@/components/daha/back-button";
import { fieldClass, PrimaryButton } from "@/components/daha/form";
import { EmptyState, ErrorState, SectionHeader } from "@/components/daha/states";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

const PERIODS: { value: LeaderboardPeriod; label: string }[] = [
  { value: "week", label: "This week" },
  { value: "all", label: "All time" },
];

function dorm(name: string | null) {
  return name ? shortCommunityName(name) : "No dorm";
}

function Podium({ people }: { people: LeaderboardEntry[] }) {
  const top = people.filter((p) => p.award);
  if (top.length === 0) return null;
  return (
    <ol className="space-y-2.5" aria-label="Podium">
      {top.map((p) => {
        const a = AWARDS[p.award!];
        return (
          <li key={p.rank} className={cn(
            "rounded-3xl bg-card p-4 ring-1 ring-border/60",
            p.rank === 1 && "bg-gradient-to-br from-brand-500 via-brand-600 to-brand-deep text-white ring-0 shadow-lg shadow-brand-600/20",
          )}>
            <div className="flex items-center gap-3">
              <span className="text-3xl leading-none" aria-hidden>{a.emoji}</span>
              <div className="min-w-0 flex-1">
                <p className={cn("text-[12px] font-semibold tracking-wide uppercase", p.rank === 1 ? "text-brand-50" : "text-reward-800")}>
                  #{p.rank} · {a.medal} · {a.title}
                </p>
                <p className="truncate text-[17px] font-semibold">
                  {p.nickname}{p.is_me && <span className="ml-1.5 text-[13px] font-medium">(you)</span>}
                </p>
                <p className={cn("text-[13px]", p.rank === 1 ? "text-brand-50" : "text-muted-foreground")}>{dorm(p.dorm_name)}</p>
              </div>
              <p className="shrink-0 text-right">
                <span className="block text-[20px] leading-6 font-bold">{p.points}</span>
                <span className={cn("text-[11px]", p.rank === 1 ? "text-brand-50" : "text-muted-foreground")}>points</span>
              </p>
            </div>
            <p className={cn("mt-2 text-[13px]", p.rank === 1 ? "text-white" : "text-muted-foreground")}>{a.quip}</p>
          </li>
        );
      })}
    </ol>
  );
}

function RankList({ people }: { people: LeaderboardEntry[] }) {
  const rest = people.filter((p) => !p.award);
  if (rest.length === 0) return null;
  return (
    <ol className="divide-y divide-border/60 rounded-2xl bg-card ring-1 ring-border/60" aria-label="Ranks 4 to 10">
      {rest.map((p) => (
        <li key={p.rank} className={cn("flex min-h-14 items-center gap-3 px-3.5 py-2", p.is_me && "bg-primary-soft")}>
          <span className="w-7 shrink-0 text-center font-semibold text-muted-foreground">#{p.rank}</span>
          <span className="min-w-0 flex-1">
            <span className="block truncate font-medium">{p.nickname}{p.is_me && " (you)"}</span>
            <span className="block truncate text-[13px] text-muted-foreground">{dorm(p.dorm_name)} · {p.exchanges} exchanges</span>
          </span>
          <span className="shrink-0 font-semibold">{p.points} <span className="text-[12px] font-normal text-muted-foreground">pts</span></span>
        </li>
      ))}
    </ol>
  );
}

function DormRanking({ board }: { board: Leaderboard }) {
  if (board.dorms.length === 0) return null;
  const max = Math.max(...board.dorms.map((d) => d.points), 1);
  return (
    <section>
      <SectionHeader title="Dorm vs dorm" />
      <ol className="space-y-2" aria-label="Dorm ranking">
        {board.dorms.map((d) => (
          <li key={d.community_id} className="rounded-2xl bg-card px-3.5 py-3 ring-1 ring-border/60">
            <div className="flex items-center gap-2">
              <span className="w-7 shrink-0 font-semibold text-muted-foreground">#{d.rank}</span>
              <span aria-hidden>{d.emoji ?? "🏠"}</span>
              <span className="min-w-0 flex-1 truncate font-medium">{shortCommunityName(d.dorm_name)}</span>
              <span className="shrink-0 font-semibold">{d.points} <span className="text-[12px] font-normal text-muted-foreground">pts</span></span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden>
              <div className="h-full rounded-full bg-points" style={{ width: `${Math.max(4, (d.points / max) * 100)}%` }} />
            </div>
          </li>
        ))}
      </ol>
      <p className="mt-2 text-[12px] text-muted-foreground">Dorm totals add up everyone&apos;s exchanges, so nobody is named.</p>
    </section>
  );
}

function JoinCard({ board, realName }: { board: Leaderboard; realName: string }) {
  const qc = useQueryClient();
  const [nickname, setNickname] = useState(board.me.nickname ?? "");
  const clean = nickname.trim();
  const looksReal = clean.length > 0 && realName.toLowerCase().split(/\s+/).some((part) => part.length > 1 && clean.toLowerCase().includes(part));
  const valid = /^[\p{L}\p{N}_\- ]{2,20}$/u.test(clean) && !looksReal;

  const save = useMutation({
    mutationFn: saveLeaderboardSettings,
    onSuccess: (_, body) => {
      qc.invalidateQueries({ queryKey: ["leaderboard"] });
      toast.success(body.opted_in ? `You're on the board as ${body.nickname}.` : "You're off the board.");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : "Couldn't save that."),
  });

  return (
    <section className="space-y-3 rounded-3xl bg-card p-4 ring-1 ring-border/60">
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="text-[17px] font-semibold">Show me on the leaderboard</h2>
          <p className="text-[13px] text-muted-foreground">
            {board.me.opted_in
              ? board.me.rank ? `You're #${board.me.rank} as ${board.me.nickname}.` : `You're on as ${board.me.nickname}. Finish an exchange to rank.`
              : valid ? "Off. Nobody sees you here until you turn it on." : "Off. Pick a nickname below to turn it on."}
          </p>
        </div>
        <Switch
          checked={board.me.opted_in}
          disabled={save.isPending || (!board.me.opted_in && !valid)}
          onCheckedChange={(v) => save.mutate({ opted_in: v, nickname: clean || null })}
          aria-label="Show me on the leaderboard"
        />
      </div>
      <div className="space-y-1.5">
        <label htmlFor="nickname" className="text-[13px] font-medium">Nickname (not your real name)</label>
        <input id="nickname" value={nickname} onChange={(e) => setNickname(e.target.value)} maxLength={20}
          placeholder="e.g. LadderLender" autoComplete="off" className={fieldClass} aria-invalid={clean.length > 0 && !valid} />
        <p className={cn("text-[13px]", clean.length > 0 && !valid ? "text-destructive" : "text-muted-foreground")}>
          {looksReal ? "That looks like your real name. Pick something else." : "2–20 letters or numbers. Only your nickname and dorm are shown."}
        </p>
      </div>
      {board.me.opted_in && clean !== (board.me.nickname ?? "") && (
        <PrimaryButton type="button" className="h-11" disabled={!valid} loading={save.isPending}
          onClick={() => save.mutate({ opted_in: true, nickname: clean })}>
          Save nickname
        </PrimaryButton>
      )}
    </section>
  );
}

export default function LeaderboardPage() {
  const [period, setPeriod] = useState<LeaderboardPeriod>("week");
  const me = useMe();
  const board = useQuery({ queryKey: ["leaderboard", period], queryFn: () => getLeaderboard(period) });

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-1">
        <BackButton fallback="/profile" className="-my-2" />
        <h1 className="text-[22px] font-semibold">Leaderboard</h1>
      </div>

      {board.data?.stand_in && (
        <p className="flex items-start gap-2 rounded-xl bg-muted px-3 py-2 text-[13px] text-muted-foreground" role="note">
          <FlaskConical className="mt-0.5 size-4 shrink-0" />
          Sample rankings for now. The real leaderboard switches on when the server supports it.
        </p>
      )}

      <div className="flex h-11 w-full rounded-full bg-muted p-1" role="tablist" aria-label="Period">
        {PERIODS.map((p) => (
          <button key={p.value} type="button" role="tab" aria-selected={period === p.value} onClick={() => setPeriod(p.value)}
            className={cn("flex-1 rounded-full text-[14px] font-semibold", period === p.value ? "bg-card shadow-sm" : "text-muted-foreground")}>
            {p.label}
          </button>
        ))}
      </div>

      {board.isPending && <div className="space-y-2.5">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-24 rounded-3xl" />)}</div>}
      {board.isError && <ErrorState onRetry={() => board.refetch()} />}
      {board.data && (
        <>
          {board.data.people.length === 0
            ? <EmptyState emoji="🏆" title="Nobody's on the board yet" body="Turn it on below, then lend, give or swap something." />
            : <><Podium people={board.data.people} /><RankList people={board.data.people} /></>}

          <p className="flex items-start gap-1.5 text-[12px] text-muted-foreground">
            <Info className="mt-0.5 size-3.5 shrink-0" />
            Only completed lends, gives and swaps count. Each different person you exchange with counts once a week, so trading back and forth with one friend won&apos;t climb the board.
          </p>

          <DormRanking board={board.data} />
          {me.data && <JoinCard key={`${board.data.me.opted_in}-${board.data.me.nickname}`} board={board.data} realName={me.data.name} />}
        </>
      )}
    </div>
  );
}
