# Value exchange: what could come next (not built)
- Status: new
- Author: Person B · Date: 2026-11-19
- Problem it solves: the first version of value exchange (`VALUE_EXCHANGE_ENABLED`) shows estimated values and gives a small karma bonus, but karma can't be spent, pricey items get no extra protection, and the bonus is easy to farm.
- Proposal: the three ideas below, each behind its own flag and built only after the team agrees. No money ever moves in DAHA: every value stays an estimate.
- Cost: free (no new services)
- Effort: about 1–2 days in total. Touches A's points and transactions, B's screens, and the seed.
- Keys / accounts needed: none
- Risks / privacy: spending karma can turn a gift culture into a market and makes points worth gaming. Photo rules add friction to handoffs.
- Recommendation: after the hackathon. First, watch how people use the bonus.

## 1. Spending karma (a "karma price")
- **A separate karma ledger**, so spending never lowers a level: `karma_ledger` (`user_id`, `delta`, `kind`: earn | hold | release | spend | receive | refund | expire | admin, `transaction_id`, `counterparty_id`, `balance_after`), unique per (transaction, kind, user).
- **Balances:** `karma_balances` (`available`, `held`), rebuilt from the ledger. Writes lock the row so two requests can't overspend. New accounts get a small starting grant.
- **Rules:**
  - An owner may set an optional karma price, from 0 to 50; free always stays possible.
  - The price is held when the owner accepts, paid when the exchange completes, and released on cancel.
  - At most 100 karma spent per person per week.
  - Karma can never be bought, sold or turned into money, and it expires after 12 months.

## 2. Photo check for items worth $100+
- Mark items with an estimated value of $100 or more as "High value".
- Before hand-off, require the existing 3-photo condition check (front, back, marks), confirmed by the borrower. Only for lends, since that's where the condition check exists today.
- Maybe a bigger bonus for these items, for example 1 point per $10, with the same caps.

## 3. More anti-gaming
- **Weekly cap:** at most 100 value-bonus points per person per 7 days.
- **Repeat pairs:** no bonus when the same two people completed an exchange in the last 7 days.
- **Value lock:** no value edits while someone has asked for the item. Store the value when the request is made as well as at completion.
- **Price check:** flag values far above the typical price (for example, over 3× a cached store price and at least $50 more, or above a per-category ceiling). Flagged items earn no bonus, are logged for review, and the owner sees a short note.
- **Swaps:** record an estimate for both sides and show the difference.
- **Profile:** a "Value received" total next to "Value shared".

A full version of 2 and 3 was built in PR #48, which can be reused if the team wants it later.
