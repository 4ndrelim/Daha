import { addDays, format, nextDay, type Day } from "date-fns";
import type { ParsedRequest, ParseRequestBody, TransactionType } from "../types";
import { guessCategory } from "./pool";

const DAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];
const COLORS = ["black", "white", "blue", "red", "green", "navy", "grey", "gray", "pink", "brown", "yellow"];
const iso = (d: Date) => format(d, "yyyy-MM-dd");

/** Stand-in for C's rule-based parser (POST /ai/parse-request). */
export function parseRequestLocally(text: string): ParsedRequest {
  const t = text.toLowerCase().trim();
  const offer = /\b(giving away|anyone want|free to (a )?good home|i have (a|an|some) .* (to give|to lend|if anyone)|selling|up for grabs)\b/.test(t);
  let item = t
    .replace(/[?!.]+$/g, "")
    .replace(/^(hi|hey|hello)[,!\s]+/, "")
    .replace(/^(does |do )?(anyone|anybody|someone|somebody)( here)? (have|got|has)( an?| some)?\s*/, "")
    .replace(/^(can|could|may) i (borrow|get|use)( an?| some| your)?\s*/, "")
    .replace(/^(i )?(need|looking for|want)( to borrow)?( an?| some)?\s*/, "")
    .replace(/^(giving away|anyone want)( an?| my| some)?\s*/, "")
    .replace(/\b(i|that i) (can|could) (borrow|use)\b.*$/, "")
    .replace(/\b(for|by|until|on|next|this|tonight|tomorrow|today)\b.*$/, "")
    .replace(/\b(in my dorm|near me|nearby)\b/, "")
    .trim();
  item = item.replace(/\(.*?\)/g, "").replace(/\s+/g, " ").trim();

  const today = new Date();
  let from: Date | null = null;
  const dayMatch = t.match(/\b(next |this |on )?(sunday|monday|tuesday|wednesday|thursday|friday|saturday)\b/);
  if (dayMatch) from = nextDay(today, DAYS.indexOf(dayMatch[2]) as Day);
  else if (/\btomorrow\b/.test(t)) from = addDays(today, 1);
  else if (/\b(tonight|today|asap|now)\b/.test(t)) from = today;
  else if (/\bthis weekend\b/.test(t)) from = nextDay(today, 6);

  const durMatch = t.match(/\bfor (a|one|two|three|\d+) (day|week)s?\b/);
  const n = durMatch ? ({ a: 1, one: 1, two: 2, three: 3 } as Record<string, number>)[durMatch[1]] ?? Number(durMatch[1]) : null;
  const duration = durMatch && n ? n * (durMatch[2] === "week" ? 7 : 1) : null;

  const category = guessCategory(t);
  let type: TransactionType | null = null;
  if (/\b(borrow|lend|use)\b/.test(t)) type = "lend";
  else if (/\b(keep|have one|giving away|free)\b/.test(t) || category === "consumables") type = "give";
  else if (/\b(swap|trade|exchange)\b/.test(t)) type = "exchange";

  const attributes: Record<string, string> = {};
  const color = COLORS.find((c) => new RegExp(`\\b${c}\\b`).test(t));
  if (color) attributes.color = color;

  const itemName = item || null;
  const title = itemName ? itemName.charAt(0).toUpperCase() + itemName.slice(1) : text.slice(0, 60);
  return {
    kind: offer ? "offer" : itemName ? "request" : "other",
    title, item_name: itemName, category, attributes, quantity: 1,
    needed_from: from ? iso(from) : null,
    needed_until: from && duration ? iso(addDays(from, duration)) : null,
    duration_days: duration, transaction_type: type,
    confidence: itemName && category ? 0.7 : 0.4,
  };
}

export const mockAi = {
  async parseRequest(body: ParseRequestBody): Promise<ParsedRequest> {
    await new Promise((r) => setTimeout(r, 60));
    return parseRequestLocally(body.text);
  },
};
