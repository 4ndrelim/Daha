# Karma price: spend points to borrow (not built)
- Status: new
- Author: Person B · Date: 2026-11-19
- Problem it solves: Value exchange shows what things are worth and rewards sharing with points, but points can't be *used* for anything. A karma price would let an owner ask for points instead of money, for example "borrow my camera for 20 karma", so heavy borrowers give back and points mean something.
- Proposal: an opt-in karma price on items, paid in points between two people. No money, no cash-out, no buying points. Behind its own flag (`KARMA_PRICE_ENABLED`, off), and only on top of value exchange.
- Cost: free (no new services)
- Effort: ~1–2 days. Touches A's `points_ledger` and transactions, B's item form and transaction screens, the seed, and the leaderboard.
- Keys / accounts needed: none
- Risks / privacy: it turns a gift culture into a market (people may stop lending for free), it creates inflation and hoarding, it could be seen as virtual currency, and points become worth gaming (fake accounts, collusion). Needs the anti-gaming rules below before launch.
- Recommendation: after the hackathon. First, watch how people use the value bonus.

## What it would need

### 1. A karma ledger (separate from "earned" points)
Today `points_ledger` only grows: earned points decide levels and badges. Spending must never lower a level, so spending needs its own ledger:
- `karma_ledger`: `id`, `user_id`, `delta` (+ earned, − spent, + received), `kind` (`earn` | `hold` | `release` | `spend` | `receive` | `refund` | `expire` | `admin`), `transaction_id` null, `counterparty_id` null, `balance_after`, `created_at`, plus a unique `(transaction_id, kind, user_id)` so a retry can't post twice.
- Writes go through one function, `post(db, user, delta, kind, tx)`, which locks the user's balance row (`SELECT … FOR UPDATE`) so two requests at once can't overspend.
- Earned points keep flowing into `points_ledger` as today. A share of them (for example, the value bonus) would also be credited to `karma_ledger` as spendable karma.

### 2. Balances
- `karma_balances`: `user_id` PK, `available`, `held`, `updated_at`. This is a cache of the ledger, rebuilt by summing it, and checked nightly.
- `/api/me` adds `karma: { available, held }`. The profile shows "Karma to spend" next to points, with the wording "not money".
- New accounts start with a small grant (for example, 10) so newcomers can borrow on day one.

### 3. Rules
- **Prices:** an owner may set `karma_price` (0–50) on an item. The default is 0 (free), and free always stays possible. A suggested price comes from the value: about 1 karma per $10, at most 50.
- **Hold, then pay:** when the owner accepts, the borrower's price is *held* (`hold`). It's paid to the owner (`spend` + `receive`) only when the exchange completes. Cancel or decline → `release`.
- **Disputes:** if the condition check says "possible changes", the payment waits up to 48 h. Either person can ask for a refund in chat, and an admin decides. No automatic penalties.
- **Limits:** at most 100 karma spent per person per week; at most 3 paid exchanges between the same two people per 30 days; no karma for self-exchanges or between accounts created on the same device the same day.
- **No cash, ever:** karma can't be bought, sold, transferred outside an exchange, or converted to money. It has no value outside DAHA. Say so in the UI and the terms.
- **Expiry:** unspent karma older than 12 months expires (`expire`), so balances don't pile up.
- **Moderation:** items with a karma price far above their value suggestion are flagged, like value flags today. Admins can post `admin` corrections, and every correction is logged with a reason.

### 4. API and screens (sketch)
- `PATCH /items/{id}` with `karma_price`, locked while a transaction is active (the same as the value lock).
- `Transaction.karma: { price, status: "none" | "held" | "paid" | "released" | "refunded" }`.
- The item card shows "Borrow for 20 karma" next to "Worth about $X". The accept sheet says "20 karma will be held until you return it".
- The receipt card adds "You paid 20 karma" or "You received 20 karma".

### 5. Before building
- Agree on the rules with all three people (this changes the contract: §6 tables and §7 types).
- Decide what earns spendable karma: everything, or only the value bonus.
- Write tests for double-spend, concurrent holds, refunds and the weekly limits first.
