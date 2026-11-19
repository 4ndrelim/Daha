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
