# Plan: all Stanford graduate residences as dorm communities

- Status: **built 2026-11-19** by A · Owner: **A** (seed data, tests, docs) · No contract change · No web change
- Builds on: #36 (EVGR A–D and the safe sync, `seed --sync-base`)

## 1. Goal
Graduate students can pick the residence they actually live in at signup and on their profile, and get
a community page and walking minutes for it. Databases already in use (laptop, Azure) get the new rows without losing anything.

## 2. Where we are today
- `backend/app/seed/data/dorms.json`: 19 rows. Graduate housing is only "Escondido Village" (`ev`) and EVGR A–D.
- `backend/app/seed/seed.py` → `seed_communities()` upserts each row by `seed_key` (`community:<slug>`); `sync_base()` / `--sync-base` / `make dorms` runs only that plus places. It never deletes, and skips a slug a user's own group already uses.
- `backend/docker-entrypoint.sh` runs `--sync-base` on every container start, so a deploy is all Azure needs.
- Web: the signup picker (`web/src/app/signup/signup-screen.tsx`, searchable list), the profile switcher (`web/src/app/(app)/profile/page.tsx`, a `<select>`) and community pages all read `GET /communities`. Nothing is hard-coded, so no web change is needed.
- Walking minutes: `app/core/geo.py` `distance_min()` from the two dorms' coordinates.

## 3. The official list
Source: R&DE Student Housing, **Graduate Housing Options** — https://rde.stanford.edu/studenthousing/graduate-housing-options
(building names and addresses from its sub-pages: `/escondido-village-highrise-apartments`, `/escondido-village-midrise-apartments`, `/escondido-village-studios`, `/escondido-village-lowrise-apartments`, `/munger-graduate-residence`). Read 2026-11-19.

| R&DE entry | Buildings | In DAHA |
|---|---|---|
| Escondido Village Graduate Residences (EVGR) | A, B, C, D | already there (#36) |
| Escondido Village High-Rises | Blackwelder, Quillen | **new:** `ev-blackwelder`, `ev-quillen` |
| Escondido Village Mid-Rises | Abrams, Barnes, Hoskins, Hulme, McFarland | **new:** `ev-abrams`, `ev-barnes`, `ev-hoskins`, `ev-hulme`, `ev-mcfarland` |
| Escondido Village Studios | Studios 1–6 | **new:** `ev-studio-1` … `ev-studio-6` |
| Escondido Village Low-Rises | ~90 numbered buildings | existing "Escondido Village" (`ev`) |
| Escondido Village South Low-Rises | numbered buildings | existing "Escondido Village" (`ev`) |
| Escondido Village Kennedy Graduate Residences | Hastorf, Lieberman, Miller, Rosse | **new:** `kennedy` |
| Liliore Green Rains Houses | many small houses | **new:** `rains` |
| Lyman Graduate Residences | 3 buildings | **new:** `lyman` |
| Munger Graduate Residence | Buildings 1–4, Jacobson-Sorensen Hall | **new:** `munger` |
| GSB Residences | Schwab Residential Center, Jack McDonald Hall, Highland Hall | **new:** `schwab`, `jack-mcdonald`, `highland` |
| Off Campus Subsidized Housing | apartment complexes around Palo Alto | existing "Off-campus" |

20 new rows; 39 dorms in total. The three GSB building names are not on the R&DE page (it only links to GSB's site); Schwab and Jack McDonald Hall are confirmed in OpenStreetMap, Highland Hall is from general knowledge.

## 4. Data
Same row format as today: `{"slug", "name", "emoji", "lat", "lng"}`. Coordinates are OpenStreetMap building centres (Overpass, one query, generic User-Agent), rounded to 5 decimals.
- Approximate (logged in `docs/decisions.md`): **Highland Hall** (`"approx": true`).
- Complex centres rather than one building: Kennedy (average of its 4 buildings), Munger, Rains, Lyman.
- Names carry the group in brackets where the bare name would be unclear in a search box: "Hulme (EV Mid-Rise)", "Schwab Residential Center (GSB)".

No schema, API or type change.

## 5. Files
| File | Owner | Change |
|---|---|---|
| `backend/app/seed/data/dorms.json` | A | +20 rows |
| `backend/tests/core/test_sync_base.py`, `test_seed.py`, `test_communities.py` | A | counts 19 → 39; new test for the graduate residences |
| `PLAN.md` §8, `docs/decisions.md`, this file | A | list, approximations |

## 6. Steps
1. Add the rows. 2. Update counts, add the test. 3. `make dorms` on the laptop database; check counts before and after. 4. Check the signup picker, profile switcher and a community page in a real browser at 360 px. 5. ruff, pytest, web checks, `make smoke`. 6. PR, merge when green.

## 7. How it reaches each database
- **Fresh install:** `make seed`.
- **Laptop, already in use:** `make dorms`.
- **Azure:** `./infra/deploy/deploy.sh` from an up-to-date `main`. The API container runs `seed --sync-base` on every start, so the rows appear with the deploy; nothing else to run. To run it by hand on the VM without deploying: `docker compose exec api python -m app.seed.seed --sync-base` (it prints "Synced: 20 communities added, 39 dorms now").

## 8. Tests
- Automated: an older database (the 20 rows deleted) → sync adds exactly 20, a second run adds 0, users/items/memberships unchanged; every new dorm has coordinates and an emoji; names are unique; signup into Munger, walking minutes Munger→Rains < Munger→Lyman, switch to Lyman, community page shows 1 member.
- Manual: the three screens above.

## 9. Risks
- **A long picker (39 rows).** Signup has a search box; the profile switcher is a native select, which phones show as a scrolling wheel. Acceptable.
- **A user's group already uses a slug** (say `munger`): the sync skips that row and prints a warning, as in #36.
- **Renaming later:** names and coordinates can be corrected in the JSON; the sync updates rows in place. Slugs must not change.

## 10. Out of scope
Undergraduate houses beyond today's list, per-building rows for the low-rises and Rains, grouping dorms into neighbourhoods in the picker.

## 11. Self-review against the code (what changed in this plan)
- `seed_communities()` ignores unknown keys, so `"approx": true` is safe (already used by 3 rows).
- `test_a_group_that_already_uses_the_slug_is_left_alone` hard-codes the count (18 → 38); found by reading the test, added to §5.
- First draft had one "EV Studios" row; Studios 1–2 and 5–6 are about 600 m apart, which is a 7-minute error in walking minutes, so each studio gets its own row.
- First draft added "Escondido South"; I could not confirm a location, and it is the same kind of housing as the low-rises, so it stays under `ev` rather than guessing a point.
- Community slugs are globally unique (`communities.slug`), so the EV buildings get an `ev-` prefix to stay clear of likely club names ("barnes", "abrams").

## 12. Done when
- [x] 39 dorms on a fresh seed; 20 added by the sync on an existing database, nothing else changed.
- [x] Signup picker, profile switcher and community pages show them; walking minutes are sensible.
- [x] ruff, pytest, web lint/typecheck/build, `make smoke` pass.
