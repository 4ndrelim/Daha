// Availability dates on items (docs/plans/availability-dates.md). The dates are campus calendar
// days (America/Los_Angeles), both optional and both inclusive. The server decides what is
// available today (`available_now`); this file only words it and sets date-picker limits.

import { format, parseISO } from "date-fns";
import type { ISODate } from "@/lib/api/types";

const CAMPUS_TZ = "America/Los_Angeles";

/** Today's date on campus as "2026-11-19", whatever time zone the phone is in. */
export function campusToday(): ISODate {
  try {
    return new Intl.DateTimeFormat("en-CA", { timeZone: CAMPUS_TZ, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
  } catch {
    return format(new Date(), "yyyy-MM-dd");
  }
}

/** "2026-11-21" → "Sat 21 Nov". A plain calendar day: no time zone shifts it. */
export function dayLabel(isoDate: ISODate): string {
  return format(parseISO(isoDate), "EEE d MMM");
}

export type AvailabilityKind = "upcoming" | "until" | "ended";
export interface AvailabilityNote { kind: AvailabilityKind; text: string }

interface Dated { available_from?: ISODate | null; available_until?: ISODate | null; available_now?: boolean }

/** The one line to show about an item's dates, or null when it is simply available. */
export function availabilityNote(item: Dated, today: ISODate = campusToday()): AvailabilityNote | null {
  const from = item.available_from ?? null;
  const until = item.available_until ?? null;
  if (until && until < today) return { kind: "ended", text: `Ended ${dayLabel(until)}` };
  if (from && from > today) return { kind: "upcoming", text: `Available from ${dayLabel(from)}` };
  if (until) return { kind: "until", text: `Available until ${dayLabel(until)}` };
  return null;
}

/** For the detail row: "Anytime", "From Sat 21 Nov", "Until Mon 23 Nov", "Sat 21 Nov – Mon 23 Nov". */
export function availabilityRange(item: Dated): string {
  const from = item.available_from ?? null;
  const until = item.available_until ?? null;
  if (from && until) return from === until ? dayLabel(from) : `${dayLabel(from)} – ${dayLabel(until)}`;
  if (from) return `From ${dayLabel(from)}`;
  if (until) return `Until ${dayLabel(until)}`;
  return "Anytime";
}

/** What is wrong with two typed dates, or null. Mirrors the server's checks. */
export function datesProblem(from: string, until: string, today: ISODate = campusToday()): string | null {
  if (from && until && until < from) return "“Until” is before “Available from”.";
  if (until && until < today) return "“Until” has already passed.";
  return null;
}
