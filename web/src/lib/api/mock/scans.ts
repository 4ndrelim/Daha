/**
 * In-browser stand-in for C's scan API (POST /scans, GET /scans/{id}, POST /scans/{id}/publish).
 * Progressive like the real pipeline: photo i finishes about 1.5 s after photo i-1, with 3–7 detections,
 * and ~30% of photos include one sensitive thing that must never be pre-ticked.
 * Publishing creates real items through `items.batch` when A's items API is live, so the rest of the app sees them.
 */
import { ApiError } from "../client";
import { items as itemsApi } from "../endpoints/items";
import { me as meApi } from "../endpoints/users";
import type {
  Category, Condition, Detection, ID, ItemDetail, ItemsBatchResponse, Scan, ScanCreate, ScanImage, ScanPublishBody,
  ScanPublishResponse, TransactionType, Upload, UserRef,
} from "../types";

type Guess = Pick<Detection, "name" | "category" | "description" | "quantity" | "condition_guess" | "suggested_transaction_type">;

const g = (name: string, category: Category, description: string, condition: Condition | null = "good",
  type: TransactionType = category === "consumables" ? "give" : "lend", quantity = 1): Guess =>
  ({ name, category, description, quantity, condition_guess: condition, suggested_transaction_type: type });

/** Things you'd plausibly see in one photo of a dorm area. */
const AREAS: Guess[][] = [
  [ // desk
    g("Desk lamp", "dorm", "White LED desk lamp with adjustable arm"),
    g("TI-84 Plus calculator", "academic", "Graphing calculator, works fine", "good"),
    g("USB-C charger", "tech", "65W laptop charger with cable", "like_new"),
    g("HDMI cable", "tech", "About 2 m long", "good"),
    g("Stapler", "academic", "Standard desk stapler"),
    g("Noise-cancelling headphones", "tech", "Over-ear, black", "like_new"),
    g("Highlighters", "academic", "Pack of 5 colors", "new", "give", 5),
    g("Computer monitor", "tech", "24-inch monitor with stand", "good"),
    g("Mechanical keyboard", "tech", "Wired, full size", "good"),
  ],
  [ // closet
    g("Rain jacket", "clothing", "Navy, size M", "good"),
    g("Navy suit jacket", "clothing", "Slim fit blazer, size 40R", "like_new"),
    g("Clothes steamer", "dorm", "Handheld garment steamer", "good"),
    g("Umbrella", "other", "Compact black umbrella", "good"),
    g("Hiking backpack", "sports", "40 L daypack", "good"),
    g("Halloween costume", "events", "Pirate costume with hat", "fair"),
    g("Winter coat", "clothing", "Puffer coat, size L", "good"),
    g("Iron", "dorm", "Steam iron", "good"),
  ],
  [ // kitchen shelf
    g("Electric kettle", "dorm", "1.7 L, stainless", "good"),
    g("Rice cooker", "dorm", "3-cup rice cooker", "good"),
    g("Frying pan", "dorm", "Non-stick, 28 cm", "fair"),
    g("Instant noodles", "consumables", "Unopened packs", "new", "give", 4),
    g("Olive oil", "consumables", "Half-full bottle", null, "give"),
    g("Mixing bowls", "dorm", "Set of 3", "good", "lend", 3),
    g("Blender", "dorm", "Personal smoothie blender", "like_new"),
    g("Spice jars", "consumables", "Cumin, paprika, chili", null, "give", 3),
  ],
  [ // drawer / common room
    g("Extension cord", "tech", "6-outlet power strip", "good"),
    g("Screwdriver set", "moving", "Small precision set", "good"),
    g("Duct tape", "moving", "Mostly full roll", null, "give"),
    g("Bike pump", "sports", "Floor pump with gauge", "good"),
    g("Bluetooth speaker", "events", "Portable, about 10 h battery", "good"),
    g("Board game", "events", "Settlers of Catan", "good"),
    g("Yoga mat", "sports", "Purple, 6 mm", "fair"),
    g("Storage bins", "moving", "Clear plastic, with lids", "good", "lend", 2),
    g("Tennis racket", "sports", "With cover", "good"),
  ],
];

const SENSITIVE: { guess: Guess; reason: string }[] = [
  { guess: g("Passport", "other", "Travel document", null), reason: "Looks like an ID document" },
  { guess: g("Prescription bottle", "other", "Medication bottle", null, "give"), reason: "Medication stays private" },
  { guess: g("House keys", "other", "Keyring with keys", null), reason: "Keys stay private" },
  { guess: g("Credit card", "other", "Payment card", null), reason: "Looks like a payment card" },
  { guess: g("Laptop", "tech", "Personal laptop", "good"), reason: "Personal device with your data" },
];

interface Plan { finishAt: number; fail: boolean; detections: Detection[] }
interface MockScan { id: ID; startedAt: number; createdAt: string; images: { upload_id: ID; url: string }[]; plans: Plan[]; published: boolean }

const store = new Map<ID, MockScan>();
const uploadsSeen = new Map<ID, Upload>();
let nextScanId = 9000 + Math.floor(Math.random() * 900);
let nextDetectionId = 90_000;
let nextMockUploadId = -1;
let scansThisSession = 0;
const SESSION_LIMIT = 20; // lets the 429 state be exercised; the real server has a daily limit

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const pick = <T,>(list: T[]) => list[Math.floor(Math.random() * list.length)]!;
const round = (n: number) => Math.round(n * 100) / 100;

function shuffle<T>(list: T[]): T[] {
  const out = [...list];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j]!, out[i]!];
  }
  return out;
}

function bbox(): [number, number, number, number] {
  const w = 0.15 + Math.random() * 0.3;
  const h = 0.15 + Math.random() * 0.3;
  return [round(Math.random() * (1 - w)), round(Math.random() * (1 - h)), round(w), round(h)];
}

function planImage(index: number): Plan {
  const count = 3 + Math.floor(Math.random() * 5);
  const guesses = shuffle(pick(AREAS)).slice(0, count);
  const detections: Detection[] = guesses.map((guess) => {
    const confidence = round(Math.random() < 0.15 ? 0.2 + Math.random() * 0.14 : 0.55 + Math.random() * 0.43);
    return {
      ...guess, id: nextDetectionId++, image_index: index, confidence, bbox: bbox(),
      suggested_share: confidence >= 0.35, sensitive_reason: null, status: "pending",
    };
  });
  if (Math.random() < 0.3) {
    const s = pick(SENSITIVE);
    detections.splice(Math.floor(Math.random() * (detections.length + 1)), 0, {
      ...s.guess, id: nextDetectionId++, image_index: index, confidence: 0.8, bbox: bbox(),
      suggested_share: false, sensitive_reason: s.reason, status: "pending",
    });
  }
  // The first photo always works so the demo never dead-ends; later ones fail now and then to show that state.
  return { finishAt: 1500 * (index + 1) + Math.random() * 400, fail: index > 0 && Math.random() < 0.1, detections };
}

function snapshot(s: MockScan): Scan {
  const elapsed = Date.now() - s.startedAt;
  const images: ScanImage[] = s.images.map((img, i) => {
    const p = s.plans[i]!;
    const finished = elapsed >= p.finishAt;
    return {
      upload_id: img.upload_id, url: img.url,
      status: !finished ? (elapsed < 300 ? "pending" : "processing") : p.fail ? "failed" : "done",
      error: finished && p.fail ? "We couldn't read this photo. Try a brighter, closer shot." : null,
    };
  });
  const detections = s.plans.flatMap((p, i) => (images[i]!.status === "done" ? p.detections : []));
  const allFinished = images.every((img) => img.status === "done" || img.status === "failed");
  const status = !allFinished ? "processing" : images.some((img) => img.status === "done") ? "done" : "failed";
  return { id: s.id, status, images, detections, provider: "mock", created_at: s.createdAt };
}

async function imageSize(blob: Blob): Promise<{ width: number; height: number }> {
  try {
    const bmp = await createImageBitmap(blob);
    const size = { width: bmp.width, height: bmp.height };
    bmp.close();
    return size;
  } catch {
    return { width: 1200, height: 1600 };
  }
}

function fabricate(body: ScanPublishBody, owner: UserRef): ItemsBatchResponse {
  const now = new Date().toISOString();
  return {
    items: body.items.map((it, i): ItemDetail => ({
      id: 800_000 + Math.floor(Math.random() * 100_000) + i, name: it.name, category: it.category,
      transaction_type: it.transaction_type, status: "available", condition: it.condition ?? null,
      quantity: it.quantity ?? 1, thumbnail_url: null, owner, visibility: it.visibility,
      community_label: it.visibility === "private" ? "Only you" : it.visibility === "campus" ? "Campus" : owner.dorm_name ?? "Campus",
      distance_min: 0, same_dorm: true, created_at: now, match_score: null, match_reason: null,
      description: it.description ?? null, images: [], max_lend_days: it.max_lend_days ?? null,
      available_from: null, available_until: null, pickup_place: null, pickup_note: null,
      group_ids: it.group_ids ?? [], pings_enabled: it.pings_enabled ?? true, is_mine: true, can_borrow: false,
      active_transaction_id: null, source: "scan", updated_at: now,
    })),
  };
}

export function rememberUpload(upload: Upload): void {
  uploadsSeen.set(upload.id, upload);
}

export const mockScans = {
  /** Used only when the uploads domain itself is mocked: keeps the photo in the browser. */
  async upload(file: Blob): Promise<Upload> {
    const [size] = await Promise.all([imageSize(file), sleep(150 + Math.random() * 250)]);
    const upload: Upload = { id: nextMockUploadId--, url: URL.createObjectURL(file), ...size };
    rememberUpload(upload);
    return upload;
  },

  async create(body: ScanCreate): Promise<Scan> {
    await sleep(250);
    if (body.upload_ids.length < 1 || body.upload_ids.length > 6) throw new ApiError(400, "Add 1 to 6 photos");
    if (++scansThisSession > SESSION_LIMIT) throw new ApiError(429, "You've scanned a lot today — list items manually for now");
    const id = nextScanId++;
    const s: MockScan = {
      id, startedAt: Date.now(), createdAt: new Date().toISOString(), published: false,
      images: body.upload_ids.map((uid) => ({ upload_id: uid, url: uploadsSeen.get(uid)?.url ?? "" })),
      plans: body.upload_ids.map((_, i) => planImage(i)),
    };
    store.set(id, s);
    return snapshot(s);
  },

  async get(id: ID): Promise<Scan> {
    await sleep(120 + Math.random() * 150);
    const s = store.get(id);
    if (!s) throw new ApiError(404, "Scan not found");
    return snapshot(s);
  },

  async publish(id: ID, body: ScanPublishBody): Promise<ScanPublishResponse> {
    await sleep(400);
    const s = store.get(id);
    if (!s) throw new ApiError(404, "Scan not found");
    const scan = snapshot(s);
    if (scan.status !== "done") throw new ApiError(409, "This scan is still processing");
    if (s.published) throw new ApiError(409, "Already shared");
    if (body.items.some((it) => it.category === "services" && it.transaction_type === "lend")) {
      throw new ApiError(400, "Services can't be lent — pick Free or Swap");
    }
    const byDetection = new Map(scan.detections.map((d) => [d.id, d]));
    const items = body.items.map(({ detection_id, ...item }) => {
      const d = detection_id === null ? undefined : byDetection.get(detection_id);
      const uploadId = d ? s.images[d.image_index]?.upload_id : undefined;
      // The real server crops the source photo; here we attach the whole photo when it's a real upload.
      const imageIds = item.image_upload_ids?.length ? item.image_upload_ids : uploadId && uploadId > 0 ? [uploadId] : [];
      return { ...item, image_upload_ids: imageIds };
    });

    let res: ItemsBatchResponse;
    try {
      res = await itemsApi.batch({ items });
    } catch (e) {
      if (e instanceof ApiError) throw e;
      const owner = await meApi.get().catch(() => null);
      res = fabricate({ items: body.items }, owner ?? {
        id: 0, name: "You", avatar_url: null, dorm_name: null, level_name: "New Neighbor", rating_avg: null,
      });
    }
    s.published = true;
    await meApi.update({ onboarded: true }).catch(() => undefined);
    const shared = body.items.filter((it) => it.visibility !== "private").length;
    return { items: res.items, points_awarded: 2 * Math.min(shared, 10) };
  },
};
