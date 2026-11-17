# Roadmap: what comes after the MVP (ML, RL, agents)

The MVP already **logs the data these need**:
- scan detections with user edits
- search logs
- events
- request matches and notifications
- the full transaction history with timestamps and reviews

Rough order, from quickest win to biggest project:

| # | Idea | Uses | Approach | Success metric |
|---|---|---|---|---|
| 1 | **Learn from corrections** | `scan_detections.edits` | Turn frequent fixes into few-shot examples and prompt rules (prompt v2, v3, …). Later, fine-tune a small open vision model (e.g. Florence-2 or YOLO-World) on corrected detections so scans are near-free and fast | edit rate ↓, scan recall ↑, $ per scan ↓ |
| 2 | **Learning-to-rank** for search and matching | `search_logs`, clicks, offers, accepted transactions | Features: similarity, keyword, distance, same dorm, owner reputation, freshness, response history. Train LightGBM LambdaMART; check offline nDCG, then A/B test with interleaving | CTR@5 ↑, request → offer time ↓ |
| 3 | **Smart notifications (contextual bandits, the "RL" starter)** | notifications sent/opened, offers that followed | Decide whom to ping about a request with a contextual bandit (Thompson sampling or LinUCB). Reward = a useful offer within 24 h; per-user daily caps | fulfillment rate ↑, notifications per fulfillment ↓ |
| 4 | **"You probably have this"** | inventories plus unmet requests | Collaborative filtering on who owns what, plus open demand → "3 people in Wilbur need a vacuum. Do you have one? Snap it." | new listings from prompts, unmet requests ↓ |
| 5 | **Demand forecasting & seasonal nudges** | requests by category, dorm, and week | Simple time-series per category and dorm (move-in: boxes and fans; finals: calculators; Halloween: costumes) → proactive "gap" alerts for dorm staff and students | fulfillment during peaks ↑ |
| 6 | **Trust & reliability** | transactions, reviews, return timing | Bayesian rating smoothing, on-time-return prediction, no-show anomaly detection → better badges and safer matching | late returns ↓, ratings ↑ |
| 7 | **Campus assistant agent** (via HarnessRouter) | the DAHA API as tools | An agent in dorm channels that answers "anyone have X?" with matches, suggests an exchange spot and time, and sends return reminders. Built as a HarnessRouter harness that calls our API | time-to-match ↓, messages per handoff ↓ |
| 8 | **Image search & dedupe** | item photos | Multimodal embeddings (CLIP or SigLIP): "find something like this photo", merging duplicate listings | search success on vague queries ↑ |
| 9 | **Impact analytics** | completed transactions | $ saved and CO₂ avoided per borrow (category estimates) → dorm leaderboards and a partnership pitch to campus sustainability groups | adoption by dorms and clubs |
| 10 | **Personal inventory & declutter** (`plans/C-ai-discovery.md` F1–F3) | private items, scan photo areas | "You already have this" check, "My stuff" search, a Keep / Share / Give-away swipe flow, a move-out week campaign | fewer duplicate requests; items rehomed per user |

**Before any of this:** get at least 4 weeks of real usage from 2–3 dorms. Models are only as good as the data.
