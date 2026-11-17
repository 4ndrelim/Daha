import type { Category, Condition, ItemStatus, TransactionType } from "@/lib/api/types";

export interface CategoryInfo { value: Category; label: string; emoji: string; tint: string }

/** PLAN.md §9. `tint` is the soft background of the emoji tile shown when an item has no photo. */
export const CATEGORIES: CategoryInfo[] = [
  { value: "academic", label: "Academic", emoji: "📚", tint: "bg-sky-50" },
  { value: "tech", label: "Tech", emoji: "💻", tint: "bg-indigo-50" },
  { value: "clothing", label: "Clothing", emoji: "👔", tint: "bg-rose-50" },
  { value: "dorm", label: "Dorm essentials", emoji: "🏠", tint: "bg-amber-50" },
  { value: "consumables", label: "Consumables", emoji: "🧂", tint: "bg-orange-50" },
  { value: "sports", label: "Sports & outdoors", emoji: "🚲", tint: "bg-lime-50" },
  { value: "moving", label: "Moving", emoji: "📦", tint: "bg-yellow-50" },
  { value: "events", label: "Events", emoji: "🎉", tint: "bg-fuchsia-50" },
  { value: "services", label: "Services", emoji: "🛠️", tint: "bg-teal-50" },
  { value: "other", label: "Other", emoji: "✨", tint: "bg-stone-100" },
];

const byValue = new Map(CATEGORIES.map((c) => [c.value, c]));
export function categoryInfo(c: Category | null | undefined): CategoryInfo {
  return (c && byValue.get(c)) || byValue.get("other")!;
}

export const TX_TYPE_LABEL: Record<TransactionType, string> = { lend: "Lend", give: "Free", exchange: "Swap" };

export const STATUS_LABEL: Record<ItemStatus, string> = {
  available: "Available", reserved: "Reserved", borrowed: "Lent out", unavailable: "Unavailable",
};

export const CONDITION_LABEL: Record<Condition, string> = {
  new: "New", like_new: "Like new", good: "Good", fair: "Fair", worn: "Worn",
};
