/**
 * Leaderboard (PLAN.md §2 P1 #7, "Opt-in dorm leaderboard", A + B).
 *
 * ⚠️ STAND-IN until A ships the endpoints. The types below are the PROPOSED contract
 * (docs/proposals/B-leaderboard.md); they are not in PLAN.md §7 yet, so they live here and
 * not in types.ts. Each call tries the real server first. If it answers 404 (endpoint not
 * built yet), the screen gets clearly marked sample data instead (`stand_in: true`), and
 * the opt-in choice is kept on this phone only. Once A's endpoints exist, the real data
 * shows with no web change.
 */
import { ApiError, http, isMocked } from "./client";
import { me as meApi } from "./endpoints/users";
import type { ID, ISODateTime } from "./types";

// ── Proposed contract ───────────────────────────────────────────────────────────────
export type LeaderboardPeriod = "week" | "all";
export type PodiumAward = "gold" | "silver" | "bronze";

/** One person on the board. Nickname + dorm only: no real name, no user id, no avatar. */
export interface LeaderboardEntry {
  rank: number; nickname: string; dorm_name: string | null;
  points: number; exchanges: number; award: PodiumAward | null; is_me: boolean;
}
/** Dorm vs dorm: everyone's qualifying points, added up (no individuals). */
export interface DormRank { rank: number; community_id: ID; dorm_name: string; emoji: string | null; points: number; people: number }
export interface LeaderboardMe { opted_in: boolean; nickname: string | null; rank: number | null; points: number; award: PodiumAward | null }
export interface Leaderboard {
  period: LeaderboardPeriod;
  since: ISODateTime | null;  // start of this week (Monday 00:00 campus time); null for all time
  people: LeaderboardEntry[]; // top 10 opted-in people
  dorms: DormRank[];
  me: LeaderboardMe;
  stand_in?: boolean;         // web only: true when this is sample data
}
export interface LeaderboardSettingsIn { opted_in: boolean; nickname: string | null }

// ── Awards (display copy) ───────────────────────────────────────────────────────────
export const AWARDS: Record<PodiumAward, { emoji: string; medal: string; title: string; quip: string }> = {
  gold: { emoji: "🥇", medal: "Gold", title: "The Karma GOAT", quip: "Somehow, everyone has borrowed something from you." },
  silver: {
    emoji: "🥈", medal: "Silver", title: "The Plug",
    quip: "Need a charger, a ladder, or emergency cinnamon? They know a person. They are the person.",
  },
  bronze: { emoji: "🥉", medal: "Bronze", title: "Certified Good Egg", quip: "Consistently showing up. Occasionally lending cookware." },
};
export const AWARD_FOR_RANK: Record<number, PodiumAward> = { 1: "gold", 2: "silver", 3: "bronze" };

// ── Calls ──────────────────────────────────────────────────────────────────────────
function notBuiltYet(e: unknown): boolean {
  return e instanceof ApiError && (e.status === 404 || e.status === 405);
}

export async function getLeaderboard(period: LeaderboardPeriod): Promise<Leaderboard> {
  if (!isMocked("users")) {
    try {
      return await http<Leaderboard>("GET", "/leaderboard", { query: { period } });
    } catch (e) {
      if (!notBuiltYet(e)) throw e;
    }
  }
  return standInLeaderboard(period);
}

export async function saveLeaderboardSettings(body: LeaderboardSettingsIn): Promise<void> {
  if (!isMocked("users")) {
    try {
      await http<LeaderboardMe>("PUT", "/me/leaderboard", { body });
      return;
    } catch (e) {
      if (!notBuiltYet(e)) throw e;
    }
  }
  writeStandInSettings(body);
}

// ── STAND-IN (sample data; delete once A's endpoints are merged) ─────────────────────
const SETTINGS_KEY = "daha_leaderboard_standin";

function readStandInSettings(): LeaderboardSettingsIn {
  try {
    const raw = window.localStorage.getItem(SETTINGS_KEY);
    if (raw) return JSON.parse(raw) as LeaderboardSettingsIn;
  } catch {
    // storage blocked: fall through
  }
  return { opted_in: false, nickname: null };
}
function writeStandInSettings(s: LeaderboardSettingsIn): void {
  try {
    window.localStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
  } catch {
    // storage blocked: the choice lasts for this visit only
  }
}

const SAMPLE_PEOPLE: { nickname: string; dorm: string; week: number; all: number; ex: number }[] = [
  { nickname: "LadderLender", dorm: "Wilbur Hall", week: 42, all: 318, ex: 24 },
  { nickname: "CinnamonPlug", dorm: "Florence Moore Hall (FloMo)", week: 37, all: 276, ex: 21 },
  { nickname: "PanTastic", dorm: "Stern Hall", week: 33, all: 241, ex: 18 },
  { nickname: "ChargerFairy", dorm: "Roble Hall", week: 29, all: 199, ex: 15 },
  { nickname: "BinderBuddy", dorm: "Wilbur Hall", week: 25, all: 164, ex: 13 },
  { nickname: "TapeMeasureTed", dorm: "Lagunita Court", week: 21, all: 150, ex: 11 },
  { nickname: "SnackOracle", dorm: "Branner Hall", week: 18, all: 122, ex: 9 },
  { nickname: "VacuumWhisperer", dorm: "Toyon Hall", week: 14, all: 97, ex: 8 },
  { nickname: "PumpItUp", dorm: "Stern Hall", week: 10, all: 80, ex: 6 },
  { nickname: "SpareUmbrella", dorm: "Crothers Hall", week: 7, all: 61, ex: 5 },
  { nickname: "GoodEggGreg", dorm: "Kimball Hall", week: 4, all: 43, ex: 3 },
];
const SAMPLE_DORMS: { id: number; name: string; emoji: string; week: number; all: number; people: number }[] = [
  { id: 1, name: "Wilbur Hall", emoji: "🌴", week: 96, all: 742, people: 9 },
  { id: 3, name: "Florence Moore Hall (FloMo)", emoji: "🌸", week: 81, all: 655, people: 8 },
  { id: 2, name: "Stern Hall", emoji: "⭐", week: 74, all: 590, people: 6 },
  { id: 5, name: "Roble Hall", emoji: "🌳", week: 52, all: 401, people: 4 },
  { id: 4, name: "Lagunita Court", emoji: "🦆", week: 40, all: 333, people: 3 },
];

function startOfWeek(): string {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7)); // back to Monday
  return d.toISOString();
}

async function standInLeaderboard(period: LeaderboardPeriod): Promise<Leaderboard> {
  const settings = readStandInSettings();
  const me = await meApi.get().catch(() => null);
  // Your stand-in score: a slice of your real points, so opting in moves you around the board.
  const myPoints = me ? (period === "week" ? Math.round(me.points * 0.15) : me.points) : 0;

  const rows: Omit<LeaderboardEntry, "rank" | "award">[] = SAMPLE_PEOPLE.map((p) => ({
    nickname: p.nickname, dorm_name: p.dorm, points: period === "week" ? p.week : p.all, exchanges: p.ex, is_me: false,
  }));
  if (settings.opted_in && settings.nickname) {
    rows.push({ nickname: settings.nickname, dorm_name: me?.dorm?.name ?? null, points: myPoints, exchanges: me?.completed_count ?? 0, is_me: true });
  }
  rows.sort((a, b) => b.points - a.points);
  const ranked = rows.map((r, i) => ({ ...r, rank: i + 1, award: AWARD_FOR_RANK[i + 1] ?? null }));
  const mine = ranked.find((r) => r.is_me);

  return {
    period,
    since: period === "week" ? startOfWeek() : null,
    people: ranked.slice(0, 10),
    dorms: SAMPLE_DORMS.map((d, i) => ({
      rank: i + 1, community_id: d.id, dorm_name: d.name, emoji: d.emoji, points: period === "week" ? d.week : d.all, people: d.people,
    })),
    me: { opted_in: settings.opted_in, nickname: settings.nickname, rank: mine?.rank ?? null, points: myPoints, award: mine?.award ?? null },
    stand_in: true,
  };
}
