// Copied verbatim from PLAN.md §7.2 — the contract. Do not edit by hand; update PLAN.md first.
// ---------- primitives ----------
export type ID = number;
export type ISODateTime = string;  // UTC, e.g. "2026-11-16T21:58:00Z"
export type ISODate = string;      // "2026-11-25" (campus local date)
export interface Page<T> { items: T[]; next_offset: number | null }

// ---------- enums ----------
export type Category = "academic" | "tech" | "clothing" | "dorm" | "consumables" | "sports" | "moving" | "events" | "services" | "other";
export type Condition = "new" | "like_new" | "good" | "fair" | "worn";
export type TransactionType = "lend" | "give" | "exchange";   // UI labels: Lend · Free · Swap
export type Visibility = "campus" | "dorm" | "groups" | "private";   // private = only me; used only for anonymous pings
export type ItemStatus = "available" | "reserved" | "borrowed" | "unavailable";
export type RequestStatus = "open" | "in_progress" | "fulfilled" | "cancelled" | "expired";
export type TxStatus = "requested" | "offered" | "accepted" | "handed_off" | "completed" | "declined" | "cancelled";
export type TxAction = "accept" | "decline" | "cancel" | "hand_off" | "mark_returned";
export type CommunityKind = "campus" | "dorm" | "group";
export type GroupType = "club" | "class" | "research" | "team" | "org" | "other";
export type NotificationType = "match" | "offer" | "borrow_request" | "tx_update" | "review" | "badge" | "system" | "private_match";
export type ItemSource = "manual" | "scan" | "offer";
export type Domain = "auth" | "users" | "communities" | "places" | "uploads" | "items" | "requests" | "transactions"
  | "conversations" | "notifications" | "events" | "search" | "feed" | "matches" | "ai" | "scans";

// ---------- users & auth ----------
export interface UserRef { id: ID; name: string; avatar_url: string | null; dorm_name: string | null; level_name: string; rating_avg: number | null }
export interface Badge { code: string; name: string; emoji: string; description: string; earned_at: ISODateTime }
export interface Level { name: string; min_points: number; next_level_name: string | null; next_level_points: number | null }
export interface UserPublic extends UserRef {
  bio: string | null; points: number; level: Level; badges: Badge[];
  rating_count: number; completed_count: number; items_shared_count: number; joined_at: ISODateTime;
}
export interface Me extends UserPublic {
  email: string; dorm: CommunityRef | null; groups: CommunityRef[]; walking_radius_min: number;
  onboarded: boolean; unread_notifications: number; unread_messages: number;
}
export interface AuthResponse { token: string; user: Me }
export interface SignupBody { email: string; password: string; name: string; dorm_id?: ID | null; ref_user_id?: ID | null }
export interface LoginBody { email: string; password: string }
export interface DemoLoginBody { user_id: ID }
export interface MeUpdate { name?: string; bio?: string | null; avatar_upload_id?: ID | null; dorm_id?: ID; walking_radius_min?: number; onboarded?: boolean }

// ---------- communities & places ----------
export interface CommunityRef { id: ID; slug: string; name: string; kind: CommunityKind; emoji: string | null }
export interface Community extends CommunityRef {
  description: string | null; group_type: GroupType | null; is_private: boolean;
  member_count: number; item_count: number; open_request_count: number;
  is_member: boolean; my_role: "member" | "admin" | null;
  join_code: string | null;             // only shown to admins, else null
  lat: number | null; lng: number | null; distance_min: number | null;
}
export interface CommunityCreate { name: string; description?: string | null; group_type: GroupType; is_private: boolean; emoji?: string | null }
export interface JoinBody { join_code?: string | null }
export interface Place { id: ID; name: string; lat: number; lng: number; description: string | null; distance_min: number | null }

// ---------- uploads ----------
export interface Upload { id: ID; url: string; width: number; height: number }

// ---------- items ----------
export interface ItemImage { id: ID; url: string; width: number; height: number }
export interface ItemCard {
  id: ID; name: string; category: Category; transaction_type: TransactionType; status: ItemStatus;
  condition: Condition | null; quantity: number; thumbnail_url: string | null; owner: UserRef;
  visibility: Visibility; community_label: string;      // "Campus" | dorm name | first group name (+N) | "Only you" (private)
  distance_min: number | null; same_dorm: boolean; created_at: ISODateTime;
  match_score: number | null;    // only in search/match/fulfillable responses, else null
  match_reason: string | null;   // e.g. "Same dorm · 2 min walk"
}
export interface ItemDetail extends ItemCard {
  description: string | null; images: ItemImage[]; max_lend_days: number | null;
  available_from: ISODate | null; available_until: ISODate | null;
  pickup_place: Place | null;
  pickup_note: string | null;    // only for the owner, or the counterparty of an accepted/handed_off transaction
  group_ids: ID[];               // owner only, else []
  pings_enabled: boolean;        // owner can turn anonymous pings off for this item
  is_mine: boolean; can_borrow: boolean; active_transaction_id: ID | null;
  source: ItemSource; updated_at: ISODateTime;
}
export interface ItemCreate {
  name: string; description?: string | null; category: Category; quantity?: number; condition?: Condition | null;
  transaction_type: TransactionType; max_lend_days?: number | null;
  available_from?: ISODate | null; available_until?: ISODate | null;
  visibility: Visibility; group_ids?: ID[]; pickup_place_id?: ID | null; pickup_note?: string | null;
  image_upload_ids?: ID[];       // ≤ 6, first = thumbnail
  pings_enabled?: boolean;       // default true
}
export type ItemUpdate = Partial<ItemCreate> & { status?: "available" | "unavailable" };
export interface BorrowBody { message?: string | null; start_date?: ISODate | null; due_date?: ISODate | null; request_id?: ID | null }
export interface ItemsBatchBody { items: ItemCreate[] }   // ≤ 30, e.g. the "tick what you have" checklist
export interface ItemsBatchResponse { items: ItemDetail[] }

// ---------- requests ----------
export interface ParsedRequest {
  kind: "request" | "offer" | "other"; title: string; item_name: string | null; category: Category | null;
  attributes: Record<string, string>; quantity: number; needed_from: ISODate | null; needed_until: ISODate | null;
  duration_days: number | null; transaction_type: TransactionType | null; confidence: number;
}
export interface ParseRequestBody { text: string }
export interface RequestCard {
  id: ID; title: string; raw_text: string; category: Category | null; status: RequestStatus; requester: UserRef;
  needed_from: ISODate | null; needed_until: ISODate | null; visibility: Visibility; community_label: string;
  distance_min: number | null; same_dorm: boolean; offer_count: number; match_count: number; created_at: ISODateTime;
}
export interface RequestDetail extends RequestCard {
  item_name: string | null; attributes: Record<string, string>; quantity: number; duration_days: number | null;
  transaction_type: TransactionType | null; pickup_place: Place | null; group_ids: ID[]; is_mine: boolean;
  matching_status: "pending" | "done";
  offers: Transaction[];         // requester sees all; others see only their own
  share_url: string;             // `${PUBLIC_BASE_URL}/r/${id}`
}
export interface RequestCreate {
  raw_text: string; title: string; item_name?: string | null; category?: Category | null; attributes?: Record<string, string>;
  quantity?: number; needed_from?: ISODate | null; needed_until?: ISODate | null; duration_days?: number | null;
  transaction_type?: TransactionType | null; visibility: Visibility; group_ids?: ID[]; pickup_place_id?: ID | null;
}
export type RequestUpdate = Partial<RequestCreate> & { status?: "cancelled" | "fulfilled" };
export interface OfferCreate { item_id?: ID | null; new_item?: ItemCreate | null; message?: string | null }  // exactly one of item_id / new_item
export interface MatchesResponse { matching_status: "pending" | "done"; items: ItemCard[]; private_pinged_count: number }  // anonymous pings sent (a number only, never who)

// ---------- transactions & reviews ----------
export interface TxTimelineEntry { status: TxStatus; at: ISODateTime; by: UserRef | null; note: string | null }
export interface Transaction {
  id: ID; kind: TransactionType; status: TxStatus; item: ItemCard; request_id: ID | null;
  owner: UserRef; borrower: UserRef; initiated_by: "owner" | "borrower"; my_role: "owner" | "borrower";
  message: string | null; start_date: ISODate | null; due_date: ISODate | null; is_overdue: boolean;
  pickup_place: Place | null; pickup_note: string | null; conversation_id: ID;
  allowed_actions: TxAction[]; can_review: boolean; timeline: TxTimelineEntry[];
  created_at: ISODateTime; updated_at: ISODateTime;
}
export interface TxActionBody { action: TxAction; note?: string | null; due_date?: ISODate | null; pickup_place_id?: ID | null }
export interface ReviewCreate { rating: 1 | 2 | 3 | 4 | 5; body?: string | null }
export interface Review { id: ID; transaction_id: ID; reviewer: UserRef; reviewee_id: ID; rating: number; body: string | null; created_at: ISODateTime }

// ---------- messaging, notifications, events ----------
export interface Message { id: ID; conversation_id: ID; sender: UserRef | null; kind: "text" | "system"; body: string; created_at: ISODateTime }
export interface ConversationSummary {
  id: ID; other_user: UserRef;
  transaction: { id: ID; status: TxStatus; kind: TransactionType; item_name: string } | null;
  last_message: Message | null; unread_count: number; updated_at: ISODateTime;
}
export interface DirectConversationBody { user_id: ID }
export interface SendMessageBody { body: string }
export interface Notification { id: ID; type: NotificationType; title: string; body: string; link: string; actor: UserRef | null; read: boolean; created_at: ISODateTime }
export interface UnreadCounts { notifications: number; messages: number }
export interface MarkReadBody { ids?: ID[]; all?: boolean }
export interface EventIn { type: string; payload?: Record<string, unknown>; ts?: ISODateTime }
export interface EventsBody { events: EventIn[] }

// ---------- discovery (C) ----------
export interface ParsedQuery {
  text: string; category: Category | null; scope: "campus" | "dorm" | null; near_me: boolean;
  available_from: ISODate | null; available_until: ISODate | null; transaction_type: TransactionType | null;
  chips: string[];               // human-readable, e.g. ["Tech", "Near you", "This weekend"]
}
export interface SearchResponse { parsed: ParsedQuery; items: ItemCard[]; requests: RequestCard[]; communities: Community[]; next_offset: number | null }
export interface FulfillableRequest { request: RequestCard; my_matching_items: ItemCard[] }
export interface HomeFeed {
  dorm: CommunityRef | null; my_item_count: number; show_scan_cta: boolean;   // show_scan_cta = my_item_count < 3
  you_can_help: FulfillableRequest[];  // ≤ 5
  requests_nearby: RequestCard[];      // ≤ 10
  new_nearby: ItemCard[];              // ≤ 12
  stats: { dorm_items: number; campus_items: number; open_requests: number };
}
export type FeedEntry =
  | { kind: "request"; created_at: ISODateTime; request: RequestCard }
  | { kind: "item"; created_at: ISODateTime; item: ItemCard };

// ---------- scans (C) ----------
export interface ScanImage { upload_id: ID; url: string; status: "pending" | "processing" | "done" | "failed"; error: string | null }
export interface Detection {
  id: ID; image_index: number; name: string; category: Category; description: string; quantity: number;
  condition_guess: Condition | null; confidence: number;
  bbox: [number, number, number, number] | null;   // normalized x, y, w, h (0..1), approximate
  suggested_share: boolean; sensitive_reason: string | null; suggested_transaction_type: TransactionType;
  status: "pending" | "published" | "discarded";
}
export interface Scan { id: ID; status: "processing" | "done" | "failed"; images: ScanImage[]; detections: Detection[]; provider: string; created_at: ISODateTime }
export interface ScanCreate { upload_ids: ID[] }
export interface ScanPublishItem extends ItemCreate { detection_id: ID | null }  // empty image_upload_ids → server uses the source photo (cropped to bbox if available)
export interface ScanPublishBody { items: ScanPublishItem[] }
export interface ScanPublishResponse { items: ItemDetail[]; points_awarded: number }
