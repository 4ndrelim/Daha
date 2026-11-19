import { AWARDS, type PodiumAward } from "@/lib/api/leaderboard";
import { cn } from "@/lib/utils";

/** A podium award: always medal emoji + medal word + title, so it never depends on color. */
export function AwardBadge({ award, period, showQuip = false, className }: {
  award: PodiumAward; period?: "week" | "all"; showQuip?: boolean; className?: string;
}) {
  const a = AWARDS[award];
  return (
    <div className={cn("flex items-start gap-3 rounded-2xl bg-points-soft px-3.5 py-3 ring-1 ring-reward-200", className)}>
      <span className="text-2xl leading-none" aria-hidden>{a.emoji}</span>
      <div className="min-w-0">
        <p className="text-[12px] font-semibold tracking-wide text-reward-800 uppercase">
          {a.medal}{period ? ` · ${period === "week" ? "this week" : "all time"}` : ""}
        </p>
        <p className="font-semibold text-reward-900">{a.title}</p>
        {showQuip && <p className="mt-0.5 text-[13px] text-reward-800">{a.quip}</p>}
      </div>
    </div>
  );
}
