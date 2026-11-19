import type { Category, Condition, Detection, ID, Me, ScanPublishItem, TransactionType, Visibility } from "@/lib/api/types";

export type DefaultType = "auto" | TransactionType;

export interface Row {
  key: string;
  detectionId: ID | null;
  imageIndex: number | null;
  checked: boolean;
  name: string;
  category: Category;
  quantity: number;
  /** null = follow the defaults bar. */
  type: TransactionType | null;
  description: string;
  condition: Condition | null;
  /** null = follow the defaults bar. */
  visibility: Exclude<Visibility, "groups"> | null;
  open: boolean;
  sensitive: string | null;
  suggestedType: TransactionType;
  /** Whole US dollars, or null. Only sent when item value is on. */
  value: number | null;
  /** The AI suggested `value` and nobody changed it: shown as "estimate". */
  valueIsEstimate: boolean;
  /** Value exchange: "store" when a cached store price filled it in. */
  valueFromStore?: boolean;
}

export interface Defaults {
  visibility: Visibility;
  groupIds: ID[];
  type: DefaultType;
  pickupPlaceId: ID | null;
}

export const NAME_MAX = 120;

export const fallbackType = (c: Category): TransactionType => (c === "consumables" || c === "services" ? "give" : "lend");

export function rowFromDetection(d: Detection): Row {
  return {
    key: `d${d.id}`, detectionId: d.id, imageIndex: d.image_index,
    // Sensitive things are never pre-ticked, whatever the model said.
    checked: d.suggested_share && !d.sensitive_reason,
    name: d.name, category: d.category, quantity: Math.max(1, d.quantity || 1), type: null,
    description: d.description ?? "", condition: d.condition_guess, visibility: null, open: false,
    sensitive: d.sensitive_reason, suggestedType: d.suggested_transaction_type,
    value: d.value_estimate_usd ?? null, valueIsEstimate: d.value_estimate_usd != null, valueFromStore: d.value_source === "store",
  };
}

let manualSeq = 0;
export function manualRow(): Row {
  return {
    key: `m${Date.now().toString(36)}${manualSeq++}`, detectionId: null, imageIndex: null, checked: true,
    name: "", category: "other", quantity: 1, type: null, description: "", condition: null, visibility: null,
    open: false, sensitive: null, suggestedType: "lend", value: null, valueIsEstimate: false,
  };
}

/** Services can never be lent (the server 400s), so Lend falls back to Free. */
export function effectiveType(row: Row, defaults: Defaults): TransactionType {
  const t = row.type ?? (defaults.type === "auto" ? row.suggestedType : defaults.type);
  return row.category === "services" && t === "lend" ? "give" : t;
}

export function effectiveVisibility(row: Row, defaults: Defaults): Visibility {
  return row.visibility ?? defaults.visibility;
}

export function defaultVisibility(me: Me | undefined): Visibility {
  return me?.dorm ? "dorm" : "campus";
}

export function rowProblem(row: Row, defaults: Defaults, me: Me | undefined): string | null {
  if (!row.name.trim()) return "Give it a name";
  const v = effectiveVisibility(row, defaults);
  if (v === "dorm" && !me?.dorm) return "Pick a dorm in your profile first, or share with Campus";
  if (v === "groups" && defaults.groupIds.length === 0) return "Pick at least one group";
  return null;
}

export function toPublishItem(row: Row, defaults: Defaults, withValue = false): ScanPublishItem {
  const visibility = effectiveVisibility(row, defaults);
  return {
    ...(withValue ? { value_usd: row.value } : {}),
    detection_id: row.detectionId,
    name: row.name.trim().slice(0, NAME_MAX),
    description: row.description.trim() || null,
    category: row.category,
    quantity: row.quantity,
    condition: row.condition,
    transaction_type: effectiveType(row, defaults),
    visibility,
    group_ids: visibility === "groups" ? defaults.groupIds : [],
    pickup_place_id: defaults.pickupPlaceId,
    image_upload_ids: [], // empty → the server crops the scan photo to the detection's bbox
    pings_enabled: true,
  };
}

/** Did the user change anything the model suggested? (Counted for the scan_published event and evals.) */
export function wasEdited(row: Row, d: Detection, defaults: Defaults): boolean {
  return row.name.trim() !== d.name || row.category !== d.category || row.quantity !== Math.max(1, d.quantity || 1)
    || effectiveType(row, defaults) !== d.suggested_transaction_type || row.description.trim() !== (d.description ?? "").trim()
    || row.condition !== d.condition_guess || row.value !== (d.value_estimate_usd ?? null);
}
