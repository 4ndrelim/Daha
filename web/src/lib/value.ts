/** Item value (ITEM_VALUE_ENABLED on the server, read from `me.item_value_enabled`).
 *  An optional estimated new price in whole US dollars. Display only: never points or payments. */
export const VALUE_MAX = 10000;

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export function formatUsd(n: number): string {
  return usd.format(n);
}

/** Text the person typed → whole dollars (0..10000), or null when empty. Non-digits are dropped. */
export function parseValue(text: string): number | null {
  const digits = text.replace(/[^\d]/g, "").slice(0, 5);
  if (!digits) return null;
  return Math.min(VALUE_MAX, Number(digits));
}

export function worthLabel(n: number): string {
  return `Worth about ${formatUsd(n)} (estimate)`;
}

/** Value exchange: the web switch (the server also needs VALUE_EXCHANGE_ENABLED and ITEM_VALUE_ENABLED).
 *  No money moves in DAHA: every number is an estimate, and the wording always says "about". */
export const VALUE_EXCHANGE = process.env.NEXT_PUBLIC_VALUE_EXCHANGE?.trim().toLowerCase() === "true";

/** Both switches on: the web one and the server's (from /api/me). */
export function valueExchangeOn(me: { value_exchange_enabled?: boolean } | null | undefined): boolean {
  return VALUE_EXCHANGE && !!me?.value_exchange_enabled;
}

/** "Worth about $45": the chip shown first on item cards. */
export function worthChip(n: number): string {
  return `Worth about ${formatUsd(n)}`;
}

export const NO_BONUS_TEXT: Record<string, string> = {
  self: "No karma bonus for exchanging with yourself.",
  no_value: "No karma bonus: this item had no estimated value.",
};
