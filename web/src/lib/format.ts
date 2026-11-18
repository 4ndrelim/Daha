import { differenceInMinutes, format, parseISO } from "date-fns";

/** "now", "5m", "3h", "2d", then "Nov 4". */
export function timeAgo(iso: string): string {
  const date = parseISO(iso);
  const mins = differenceInMinutes(new Date(), date);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m`;
  if (mins < 60 * 24) return `${Math.floor(mins / 60)}h`;
  if (mins < 60 * 24 * 7) return `${Math.floor(mins / (60 * 24))}d`;
  return format(date, "MMM d");
}

export function walkLabel(min: number | null | undefined): string | null {
  if (min === null || min === undefined) return null;
  return `${min} min`;
}

/** ISODate "2026-11-25" → "Wed Nov 25". */
export function shortDate(isoDate: string): string {
  return format(parseISO(isoDate), "EEE MMM d");
}

export function firstName(name: string): string {
  return name.split(" ")[0] ?? name;
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?";
}

/** plural(1, "ask") → "1 ask"; plural(3, "ask") → "3 asks"; plural(2, "thing", "things"). */
export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** "Florence Moore Hall (FloMo)" → "FloMo"; names without a nickname stay as they are. */
export function shortCommunityName(name: string): string {
  return name.match(/\(([^)]+)\)\s*$/)?.[1] ?? name;
}
