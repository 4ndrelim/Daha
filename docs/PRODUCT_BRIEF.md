# DAHA — product brief

This brief is refined from the original consolidated brief, which collected what undergrads want. It describes the **full vision**. What we build first is in `PLAN.md` §2, and §13 below maps each idea to MVP or later.

---

## 1. Vision
DAHA is a campus-wide, peer-to-peer network where students easily **lend, borrow, give away, swap, and request** everyday items and services. It starts at Stanford.

Three principles:
- **Contributing should be as easy as taking a picture.**
- **Finding something should be as easy as searching for it.**
- **Borrowing should be convenient enough to replace unnecessary purchases.**

## 2. Where we start from
Today students use dorm group chats:
- "Does anyone have a calculator?"
- "Anyone have a vacuum?"
- "Can I borrow a black binder next Wednesday?"
- "Does anyone want a leather jacket?"

Others reply, arrange a handoff, and the request gets resolved. That works, but only inside one dorm, nothing is searchable, and good items stay invisible.

DAHA keeps this **casual, conversational behavior** and makes everything **searchable, discoverable, and campus-wide**. The dorm-channel experience must keep working inside DAHA.

## 3. One campus network, three discovery layers
**Core architectural rule:** one unified inventory, user, and request system. Dorms and organizations are **visibility and community layers over shared data**. They are not separate marketplaces or duplicated databases.

| Layer | What it offers |
|---|---|
| **Campus-wide** | A global feed of available items, requests, offers, and exchanges. Searchable inventory across all communities. Campus-wide requests that notify relevant potential lenders. Filters for location, dorm, category, availability, and transaction type |
| **Dorm communities** | A feed and discovery page per dorm, with dorm-specific inventory and requests. Students see their own dorm first and can expand to the whole campus |
| **Groups & organizations** | Clubs, classes, research groups, project teams, and student organizations. Shared group inventories, group-level requests, and membership and visibility permissions |

## 4. Onboarding & AI inventory creation (highest priority, the main differentiator)
Onboarding is built around one action: **"Show us what you have."** A new user should join and share their first items in **under 60 seconds**.
- Multi-image upload and direct camera capture.
- Photos of desks, closets, drawers, kitchens, pantries, storage spaces, and common areas.
- AI recognition that finds **multiple individual objects per photo**.
- Item names, categories, descriptions, and estimated quantities are generated automatically.
- One review screen for all detected items. The user:
  - selects what they're comfortable sharing
  - edits, removes, or corrects detections
  - publishes many items with one confirmation
- Manual single listings remain an alternative. Onboarding can be skipped and items added later.
- **Hard rules:**
  - AI-detected items are never published without explicit confirmation.
  - A whole personal inventory is never made public automatically.

## 5. Listings
Each listing supports:
- images, name, description, category, quantity
- condition and availability
- pickup location
- transaction type: **lend, give away, or exchange**
- optional lending duration
- visibility: **campus-wide, dorm-only, or selected groups**
- status: **available, reserved, borrowed, or unavailable**

## 6. Requests, offers & transactions
Keep the simplicity of chat-style requests and add structure underneath. Users can:
- write casual text requests, or structured ones with item, quantity, date needed, duration, and pickup area
- choose dorm, group, or campus-wide visibility
- respond to requests with offers, or suggest alternative items
- message each other and coordinate handoffs
- mark requests fulfilled or cancelled

**AI categorizes requests and matches them against existing inventories.** For example, a student posts *"Does anyone have a black binder I can borrow next Wednesday?"* The system should:
1. Recognize the item and its attributes (black, binder, borrow, next Wednesday).
2. Search matching available inventory across the communities the student can access.
3. Prioritize same-dorm and nearby lenders.
4. Show matching items right next to the request.
5. Notify relevant potential lenders.
6. Let a lender respond with an offer, then support coordination and fulfillment.

**Requests for unlisted items must work.** A request is a chance for someone to contribute an item they haven't listed yet.

**Lifecycle:** requested → offered → accepted → handed off → completed, with cancellation and return handling where applicable.

## 7. Search & discovery
One universal search across items, requests, offers, services, and communities. It accepts natural language:
- "Graphing calculator near me."
- "Anyone have a vacuum in my dorm?"
- "Formal clothes for an interview."
- "Moving boxes available this weekend."
- "Someone who can help repair my bike."

Results are ranked by **relevance, availability, proximity, and user preferences**. Filters: category, dorm/community, walking distance, availability, transaction type, condition. The system also **recommends requests a user could fulfill** based on their inventory.

## 8. Student use cases & categories
| Category | Examples |
|---|---|
| Academic | textbooks, calculators, notebooks, stationery, lab supplies |
| Technology | chargers, adapters, monitors, keyboards, cameras |
| Clothing | suits, dresses, jackets, costumes, formalwear |
| Dorm essentials | vacuums, fans, kettles, cookware, appliances |
| Consumables | spices, oil, packaged food, detergent, toiletries |
| Sports | bikes, helmets, rackets, camping equipment |
| Moving | boxes, carts, tools, furniture, storage supplies |
| Events | speakers, projectors, decorations, costumes |
| Services | tutoring, photography, bike repair, moving help |

DAHA supports lending, gifting, exchanges, and free giveaways. It is **not limited to physical item borrowing**.

## 9. Location, safety & coordination
- Users and items are tied to dorms or approximate campus locations.
- Users set a preferred walking radius.
- Priority order: same dorm, then nearby dorms, then the wider campus.
- Approximate walking distances are shown when location data allows.
- Pickup instructions and direct messaging are supported, as are optional campus exchange locations.
- **Private residential addresses are never exposed.**

## 10. Engagement & trust
- A lightweight reputation and contribution system: points for lending, gifting, fulfilling requests, and contributing inventory.
- Contribution levels and badges, transaction history, and reviews after completed transactions.
- Invitations and shareable request links. Encourage adoption by dorms, clubs, and organizations.
- **Trust and genuine community participation come before gamification.**

## 11. UI/UX
- Polished, mobile-first, and responsive. It should feel like a campus community app combined with a conversational messaging platform and a lightweight marketplace.
- Clean typography, strong visual hierarchy, consistent components, modern rounded interfaces, fast navigation, minimal onboarding steps, and a **prominent camera/upload action**.
- Primary navigation:
  - **Home:** personalized campus activity, nearby items, relevant requests
  - **Explore:** search and browse everything
  - **Add:** upload photos, list an item, or create a request
  - **Communities:** dorms, clubs, classes, organizations
  - **Profile:** inventory, requests, transactions, reputation
- Home must make it instantly obvious **what's available nearby and what you can contribute**.
- It must **not** feel like a static e-commerce catalog. Keep the immediacy of student messaging.

## 12. Non-goals for now
Payments or selling, native mobile apps, push or email notifications, and multi-campus support. See `PLAN.md` §2 for the full list.

## 13. Brief → build plan (traceability)
| Brief section | MVP (v0.1) | Later |
|---|---|---|
| Unified inventory + 3 layers | ✅ campus, dorms, groups as communities with audience-based visibility | group-owned inventory (P1) |
| "Show us what you have" AI onboarding | ✅ multi-photo scan → review → batch publish; skippable | learn from user corrections; cheaper on-device model (`plans/ROADMAP.md`) |
| Listings (all fields) | ✅ | |
| Casual + structured requests, AI parse | ✅ rule-based instant parse | LLM enrichment (P1) |
| Matching, nearby priority, lender notifications | ✅ embeddings + proximity; top owners notified | learned ranking; bandit-based notification targeting |
| Unlisted-item requests | ✅ offer an unlisted item → it becomes a listing | "you probably have this" prompts |
| Full transaction lifecycle | ✅ requested/offered → accepted → handed off → returned/completed | overdue reminders (P1) |
| Universal natural-language search + filters | ✅ items, requests, communities | image search |
| Requests you could fulfill | ✅ "You could help" | |
| Location & safety | ✅ dorm-level only, walking minutes, exchange spots, private pickup notes | |
| Reputation, badges, reviews, invites, share links | ✅ | dorm leaderboard (P1) |
| Mobile-first UI with 5-tab navigation | ✅ responsive web app | PWA (P1), native apps |

## Resources
- HarnessRouter (our AI credit for photo detection): https://harnessrouter.ai/docs · community: https://community.harnessrouter.ai/roadmap
