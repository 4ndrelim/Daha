import type { Category, TransactionType } from "@/lib/api/types";

/**
 * C5 "Tick what you have": common lendables people are happy to share when asked.
 * Ticked ones become private items (visibility "private", pings_enabled) via POST /items/batch,
 * so nobody sees the list and DAHA quietly pings the owner when someone nearby needs one.
 */
export interface CommonHave { key: string; name: string; emoji: string; category: Category; type: TransactionType }

export const COMMON_HAVES: CommonHave[] = [
  { key: "bike-pump", name: "Bike pump", emoji: "🚲", category: "sports", type: "lend" },
  { key: "tool-kit", name: "Tool kit", emoji: "🧰", category: "moving", type: "lend" },
  { key: "hdmi-cable", name: "HDMI cable", emoji: "🔌", category: "tech", type: "lend" },
  { key: "extension-cord", name: "Extension cord", emoji: "🔋", category: "tech", type: "lend" },
  { key: "phone-charger", name: "Phone charger", emoji: "📱", category: "tech", type: "lend" },
  { key: "laptop-charger", name: "USB-C laptop charger", emoji: "💻", category: "tech", type: "lend" },
  { key: "calculator", name: "Graphing calculator", emoji: "🧮", category: "academic", type: "lend" },
  { key: "iron", name: "Iron", emoji: "👔", category: "dorm", type: "lend" },
  { key: "umbrella", name: "Umbrella", emoji: "☂️", category: "other", type: "lend" },
  { key: "speaker", name: "Bluetooth speaker", emoji: "🔊", category: "events", type: "lend" },
  { key: "kettle", name: "Electric kettle", emoji: "🫖", category: "dorm", type: "lend" },
  { key: "vacuum", name: "Vacuum", emoji: "🧹", category: "dorm", type: "lend" },
  { key: "fan", name: "Fan", emoji: "🌀", category: "dorm", type: "lend" },
  { key: "frying-pan", name: "Frying pan", emoji: "🍳", category: "dorm", type: "lend" },
  { key: "scissors", name: "Scissors", emoji: "✂️", category: "academic", type: "lend" },
  { key: "stapler", name: "Stapler", emoji: "📎", category: "academic", type: "lend" },
  { key: "suit", name: "Suit or blazer", emoji: "🕴️", category: "clothing", type: "lend" },
  { key: "rain-jacket", name: "Rain jacket", emoji: "🧥", category: "clothing", type: "lend" },
  { key: "tent", name: "Tent", emoji: "⛺", category: "sports", type: "lend" },
  { key: "sleeping-bag", name: "Sleeping bag", emoji: "🛌", category: "sports", type: "lend" },
  { key: "bike-lock", name: "Bike lock", emoji: "🔒", category: "sports", type: "lend" },
  { key: "helmet", name: "Bike helmet", emoji: "⛑️", category: "sports", type: "lend" },
  { key: "yoga-mat", name: "Yoga mat", emoji: "🧘", category: "sports", type: "lend" },
  { key: "board-game", name: "Board games", emoji: "🎲", category: "events", type: "lend" },
  { key: "projector", name: "Projector", emoji: "📽️", category: "events", type: "lend" },
  { key: "moving-boxes", name: "Moving boxes", emoji: "📦", category: "moving", type: "give" },
  { key: "dolly", name: "Hand truck / dolly", emoji: "🛒", category: "moving", type: "lend" },
  { key: "first-aid", name: "First aid kit", emoji: "🩹", category: "other", type: "give" },
  { key: "sewing-kit", name: "Sewing kit", emoji: "🧵", category: "other", type: "lend" },
  { key: "lab-goggles", name: "Lab goggles", emoji: "🥽", category: "academic", type: "lend" },
  { key: "camera", name: "Camera", emoji: "📷", category: "tech", type: "lend" },
  { key: "spices", name: "Spices", emoji: "🧂", category: "consumables", type: "give" },
];
