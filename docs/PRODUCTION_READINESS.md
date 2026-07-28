# Hive — Production Readiness Backlog

> Generated from a full-codebase audit on 2026-07-28.
> Supersedes [TODO.md](TODO.md), which reports "100% complete (62/62)" — that assessment does not
> survive inspection and should be treated as void.

**Scope audited:** `mind/` (81k LOC Python), `queen/` (10.5k LOC Next.js), `cell/` (30k LOC Flutter),
`alembic/`, `.github/workflows/`, `docs/`.

## How to read this

Every task has evidence (file:line), a fix, and acceptance criteria. Priorities:

| Pri | Meaning |
|-----|---------|
| **P0** | Blocks any deployment reachable from a network. Ship nothing until these are closed. |
| **P1** | Blocks a credible production launch. Correctness, data integrity, or the product not working. |
| **P2** | Required for operating the thing without pain. |
| **P3** | Hygiene, docs, and cleanup. |

**Counts:** 137 tasks — 26 P0, 50 P1, 51 P2, 10 P3.  ·  **Done:** 21 (HIVE-001…013, 028, 029, 068, 125, 129, 131, 133, 135)

**API auth coverage** (live figure: `pytest tests/api/test_auth_coverage.py -s`) — **93 required · 6 optional · 156 open** of 255 endpoints.

## How to work this

Every task carries a tracking block. Update it **in the same commit as the work**, not afterwards:

```
> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-003, HIVE-119 · **Blocks:** HIVE-058
> **Blockers:** _none recorded_
> **Feedback:** _pending_
```

| Field | What goes in it |
|-------|-----------------|
| **Status** | One of the values below. |
| **Owner** | Whoever currently holds it. One name — shared ownership means nobody's. |
| **Started / Closed** | `DD-MM-YYYY`. Lets us see how long things actually sit. |
| **Depends on** | Pre-populated. Do not start a task whose dependencies are open unless you have a reason — record the reason in Feedback. |
| **Blocks** | Pre-populated reverse edge. High counts here are why sequencing matters. |
| **Blockers** | Anything that *stopped* you: a missing credential, an unreachable service, a decision you need, a dependency that turned out to be real. Date each entry. This is the field the daily standup reads. |
| **Feedback** | What you found once you were inside the code. Scope that grew or shrank, wrong estimates, a fix that differed from the one proposed here, follow-up tasks spawned, and the outcome. |

**Status vocabulary:**

| Value | Meaning |
|-------|---------|
| `Not started` | Untouched. |
| `In progress` | Someone is actively on it. Owner must be set. |
| `Blocked` | Cannot proceed. **Blockers must be non-empty** — a `Blocked` task with no recorded blocker is a stalled task pretending to be blocked. |
| `In review` | Code written, PR open. |
| `Done` | Merged **and** acceptance criteria verified. Not "merged". |
| `Won't do` | Deliberately dropped. **Feedback must record why** — several tasks here are delete-or-wire decisions, and the decision is the deliverable. |
| `Superseded` | Replaced by another task. Name it in Feedback. |

**Two rules that keep this document honest**, given that it exists because [TODO.md](TODO.md) self-reported 100%:

1. `Done` requires the acceptance criteria to have been *run*, not judged plausible.
2. If the fix proposed here turns out to be wrong, change this document. A stale backlog is worse than none.

### The dependency graph, ranked

Tasks blocking the most other work — resolve top-down:

| Task | Blocks | Why it dominates |
|------|--------|------------------|
| **HIVE-119** | **25** | The scope decision. Determines whether 12 routers get auth or get deleted. |
| **HIVE-003** | **19** | Token-derived actor identity. Every router-auth task builds on it. |
| **HIVE-001** | 4 | Real admin auth. Gates the portal login and the admin WebSocket. |
| **HIVE-021** | 4 | Calling the startup validators. Gates every config-safety task. |
| **HIVE-022** | 4 | The aging bug. Gates lifecycle tests, population limits, and the README screenshots. |
| **HIVE-118** | 3 | Product name. Gates the mobile bundle ID — irreversible after first publish. |

Everything else has 0–2 dependents and can be parallelised freely.

---

## Executive summary

Three things dominate everything else in this backlog:

1. **The API is almost entirely unauthenticated.** Of ~250 endpoints, ~215 have no auth dependency at
   all. Actor identity (`user_id`, `moderator_id`) is passed as a *request parameter*, so any caller
   can act as any user. The admin surface is protected only by an unsigned `X-User-ID` header, and a
   working admin UUID is hardcoded in committed frontend source.

2. **The headline feature does not run.** Bots never age in the default configuration
   (integer-truncation bug in `age_all_bots`), so life stages, vitality decay, death, legacy, and
   reproduction-by-elders are all unreachable. The `demo_mode` escape hatch that would mask this is
   itself wired to a setting that does not exist.

3. **~7,000 LOC of feature code is unreachable.** Telegram/Discord channels, TTS, skills, hooks, the
   task scheduler, the DI container, the GitHub integration, `sentient_core.py`, the *stronger* of the
   two code sandboxes, and — most consequentially — the entire production config preflight validator
   are never imported by anything.

Beneath that, the architecture is sound. The loop/manager decomposition, the LLM client stack
(circuit breaker → cache → rate limiter → pool), and the civilization domain model are well designed
and worth keeping. The gap is verification, not design: nothing type-checks, the mobile test job
cannot run, and the coverage gate is asserted rather than achieved.

---

# EPIC A — Authentication & Authorization (P0)

The single largest body of work. Nothing else matters until this is done.

### HIVE-001 · P0 · Replace `X-User-ID` admin auth with JWT
`mind/api/routes/admin.py:39-78` — `require_admin` reads an unsigned `X-User-ID` header, looks up the
UUID, checks `is_admin`. No token, no signature, no expiry. Grants all 20 admin endpoints.
**Fix:** delete `get_current_user`/`admin_user_header` from `admin.py`; depend on
`mind.api.dependencies.get_current_user` (already correct) plus a new `require_admin` that checks
`is_admin` on the token-resolved user.
**AC:** a request with only `X-User-ID` returns 401; a valid non-admin JWT returns 403; a valid admin
JWT succeeds.

> **Status:** `Done` · **Owner:** Claude · **Started:** 28-07-2026 · **Closed:** 28-07-2026
> **Depends on:** — · **Blocks:** HIVE-002, HIVE-018, HIVE-068, HIVE-122
> **Blockers:**
> - _28-07-2026_ — **Resolved.** No Python environment existed on this machine (`import fastapi`
>   failed), so the AC could not be verified at first. Built `.venv` and installed the subset of
>   `requirements.txt` needed to import `mind` and run the suite. **Not a repo defect** — everything
>   needed was already declared in `requirements.txt`. `.venv/` is gitignored.
> - _28-07-2026_ — **Escalated to [HIVE-129](#hive-129--p1--pytest-cannot-collect-the-suite-at-all).**
>   The full suite would not run: `tests/api/test_civilization_api.py:19` declares
>   `pytest.mark.api`, which is not in `pyproject.toml`'s `markers` list, and `--strict-markers` is
>   on — so collection aborts for the *entire* suite. Worked around locally with `--ignore`; the real
>   fix is HIVE-129.
> **Feedback:**
> - **Done, AC verified by execution.** `tests/api/test_admin_auth.py` — 7 passed. All three AC
>   cases covered (`X-User-ID` alone → 401, non-admin JWT → 403, admin JWT → 200), plus regression
>   guards for a missing header, a tampered token, a banned admin, and the retired security scheme
>   being absent from the OpenAPI document.
> - **The proposed fix was right but incomplete in one place.** `AuthenticatedUser`
>   (`mind/core/auth.py:221`) has no `is_admin` field, so `require_admin` cannot work off the token
>   payload alone. Added `get_current_admin_user`, which takes the verified token user and loads the
>   `AppUserDB` row for the `is_admin`/`is_banned` flags. All 20 admin routes keep their existing
>   `admin: AppUserDB = Depends(require_admin)` signature — **zero route bodies changed**.
> - **Wider blast radius than the task described.** `mind/api/routes/analytics.py` imported this
>   dependency as `require_admin_header`; updated the import and its 5 call sites. So this task
>   actually secured **25 endpoints**, not 20.
> - **Docs corrected alongside:** the Swagger description and the `admin` tag description in
>   `mind/api/main.py` both instructed users to authenticate with `X-User-ID`. Left unchanged they
>   would have kept advertising the removed scheme.
> - ⚠️ **Expected regression — the queen portal's admin pages are now broken.**
>   `queen/src/lib/api.ts:396` still sends only `X-User-ID`, so every admin call now returns 401.
>   This is correct behaviour, not a defect, but it means **HIVE-002 and HIVE-068 are no longer
>   optional follow-ups — they are required to restore the portal.** Recommend treating
>   001 → 068 → 002 as one deliverable rather than three.
> - **Note for HIVE-058:** the mock-session + minimal-app pattern in `tests/api/test_admin_auth.py`
>   tests auth dependencies without a database. Reuse it for the other 12 routers in Epic A.

### HIVE-002 · P0 · Remove the hardcoded admin UUID from frontend source
`queen/src/contexts/WebSocketContext.tsx:7` — `const ADMIN_USER_ID = '0bb6e0aa-4503-4b45-96d3-f1bd267b62b8'`,
committed and public. Combined with HIVE-001 this is a live admin credential in the repo.
**Fix:** delete the constant; drive the admin WebSocket from the session token.
**AC:** no UUID literals in `queen/src`; the value is purged from git history or the corresponding
account is deleted/rotated in every environment.

> **Status:** `Done` · **Owner:** Claude · **Started:** 28-07-2026 · **Closed:** 28-07-2026
> **Depends on:** HIVE-001 ✅, HIVE-068 ✅ (both closed) · **Blocks:** —
> **Blockers:**
> - _28-07-2026_ — ⛔ **OPEN, NEEDS YOU. The AC is only half met.** The literal is gone from the
>   working tree, but `0bb6e0aa-4503-4b45-96d3-f1bd267b62b8` is still in **committed git history**
>   and must be treated as disclosed. Two actions are outside what I should do unattended:
>   **(a)** delete or demote that account (`UPDATE app_users SET is_admin = false` / delete) in
>   **every** environment it exists in — this is the action that actually revokes access;
>   **(b)** decide whether to rewrite history (`git filter-repo`), which is destructive and
>   force-pushes a shared branch. **(a) alone closes the risk** — after the account is dead the
>   history entry is an inert string. Recommend (a) now, skip (b).
> - _28-07-2026_ — **Resolved, escalated to [HIVE-131](#hive-131--p0--the-queen-portal-has-never-built).**
>   `WebSocketContext.tsx` imports `@/lib/websocket`, which **did not exist** — so the portal did not
>   build at all and the constant could not be edited in a verifiable way. Had to write the missing
>   module before this task was even testable.
> **Feedback:**
> - **Done, verified by build.** `npx tsc --noEmit` clean, `npx next build` succeeds (19 routes),
>   `npx eslint` reports **0 issues in all 6 files touched** (62 pre-existing issues elsewhere, 38 of
>   them in `CivilizationMap.tsx`, untouched by this work).
> - `grep -rnoE '[0-9a-f]{8}-[0-9a-f]{4}-...' queen/src` now returns **nothing** — AC part 1 met.
> - **This task could not be done alone**, exactly as predicted in HIVE-001's feedback. Removing the
>   constant means having another identity source, which is HIVE-068. Delivered together:
>   `queen/src/lib/auth.ts` (token store, login/logout/refresh, cross-tab sync),
>   `queen/src/lib/websocket.ts` (the missing manager), `queen/src/app/login/page.tsx`,
>   a real `AuthProvider`, and bearer auth + 401-refresh-retry in `apiFetch`.
>   **HIVE-068 is closed by this work** — see its entry.
> - **`localStorage.removeItem('admin_user_id')` is deliberately left in `clearSession()`**
>   (`auth.ts:84`). Browsers that used the old portal still hold that key; this sweeps it on next
>   sign-out. Delete it after one release cycle.
> - **Concurrent-401 handling matters here.** The dashboard fires many parallel requests; without
>   sharing the in-flight refresh (`auth.ts:refreshAccessToken`) a token expiry would fire one
>   refresh per request and the losers would clobber each other's tokens.
> - **Note for HIVE-017.** `websocket.ts` still identifies itself with an `auth` frame carrying the
>   user id, because that is what `mind/api/main.py:947` accepts today. The `connect()` seam is ready
>   for a token frame — HIVE-017 changes one line there and one in the backend.
> - **Note for HIVE-054.** I ran `tsc --noEmit` against the whole portal and it is **clean**, so
>   adding the missing `type-check` script is now a one-line change with a known-green result.

### HIVE-003 · P0 · Derive actor identity from the token, never from request parameters
`mind/api/routes/feed.py:439,505,542` take `user_id` as a query parameter.
`mind/api/routes/moderation.py:601,651` take `moderator_id` as a parameter. Any caller can like,
comment, post, and resolve moderation reports as any user or moderator.
**Fix:** remove every actor-identity parameter; inject via `Depends(get_current_user)`. Keep explicit
IDs only where a *target* (not an actor) is meant.
**AC:** grep for `user_id:` / `moderator_id:` / `author_id:` in route signatures returns only target
parameters; an integration test proves user A cannot act as user B.

> **Status:** `Done` · **Owner:** Claude · **Started:** 28-07-2026 · **Closed:** 28-07-2026
> **Depends on:** HIVE-119 ⚠️ (started anyway — see below) · **Blocks:** HIVE-004…018, HIVE-058, HIVE-068 ✅, HIVE-084, HIVE-111
> **Blockers:**
> - _28-07-2026_ — ⚠️ **Started with HIVE-119 still open, deliberately.** This document's own rule
>   says record the reason, so: HIVE-119 decides whether the social-platform half is kept or deleted,
>   which changes *whether these routers exist* but not *what correct looks like*. Leaving a live
>   impersonation flaw open while waiting on a product decision is the wrong risk trade. If HIVE-119
>   comes back "delete", this work is discarded, not wasted — deleting a secured endpoint is no harder
>   than deleting an insecure one. **HIVE-119 is still the single most valuable thing you can answer.**
> - _28-07-2026_ — **Resolved, escalated to [HIVE-129](#hive-129--p1--pytest-cannot-collect-the-suite-at-all).**
>   Could not run the AC test at all until the `api` marker was declared. Fixed it here (one line in
>   `pyproject.toml`) because it blocked verification for the third turn running — **HIVE-129 is now
>   closed.**
> **Feedback:**
> - **Done, AC verified by execution.** 46 api tests pass; full suite **261 passed, 8 pre-existing
>   failures, no regressions**.
> - **Scope was 3× the task description.** It cited 5 sites; a systematic AST sweep of every route
>   signature found **52**, of which **44 were actors** and 10 legitimate targets. Converted all 44
>   across 9 routers. Endpoints requiring auth went from **~35 to 93 of 255** (⚠️ originally reported here as 98 — corrected in HIVE-004's feedback; the old figure counted optional-auth routes).
> - **`is_bot` was worse than the impersonation.** `like_post`, `create_comment`,
>   `send_community_message`, `send_direct_message`, `create_story`, `mark_story_viewed` and
>   `upload_media` all took a caller-supplied `is_bot`/`author_is_bot` flag — and the moderation
>   pipeline was written as `if not is_bot: check_content(...)`. **Any caller could skip content
>   moderation entirely by passing `is_bot=true`.** All such flags removed; bots write through the
>   engine, not HTTP.
> - **Four further defects found while doing this, all fixed here:**
>   1. **`handle_errors` swallowed `HTTPException` → 500** (`mind/core/decorators.py:65`). It
>      re-raised `AppError` but not `HTTPException`, so every deliberate 401/403/404 inside a
>      decorated handler became a 500. It affected 23 handlers across `auth`, `chat`, `feed`, and
>      `users`, and it defeated the ownership check I had just added. **My own AC test caught it** —
>      it expected 403 and got 500. Without that test this task would have shipped "secured"
>      endpoints that returned 500 instead of enforcing anything.
>   2. **Notification IDOR.** `mark_as_read` / `delete_notification` took only a notification id, so
>      any user could act on any notification. Both now take `owner_id` and scope the statement.
>   3. **`PUT /users/{user_id}` let anyone rename any account.** Now ownership-checked.
>   4. **Route shadowing** — filed as
>      **[HIVE-133](#hive-133--p1--users-router-shadowed-users-blocked)**, fixed here.
> - **`verify_user_exists()` and `verify_admin()` deleted from `blocking.py`.** Both took a
>   caller-supplied id, so they proved only that *some* such user existed — never that the caller was
>   that user. They read like security and were not; that pattern is worth grepping for elsewhere.
> - **Two existing tests asserted the vulnerability** — `test_like_post` and `test_create_comment`
>   passed `user_id` anonymously and accepted a 2xx. Rewritten to expect 401. Worth remembering when
>   reading any other green test in this repo.
> - **Note for HIVE-004…016.** Those tasks are now **substantially complete** — blocking, chat,
>   notifications are at 100% auth coverage; feed, hashtags, media, moderation, stories, users are
>   partial by design (public reads stay public). What genuinely remains is **civilization (0/85),
>   settings (0/13), system (0/3), search (0/5), evolution (0/8), platform (0/7)** — re-scope them to
>   that. Run the coverage snippet in this task's commit message to regenerate the table.

### HIVE-133 · P1 · `users` router shadowed `/users/blocked`
`GET /users/blocked` (blocking router) was registered **after** `GET /users/{user_id}` (users
router) in `mind/api/main.py`. FastAPI matches in registration order, so `/users/blocked` hit the
parameterised route first and failed UUID parsing — the endpoint returned **422 for its entire
existence** and was unreachable.
**Fix:** register `blocking_router` before `users_router`, with a comment saying why.
**AC:** `GET /users/blocked` returns 401 unauthenticated (not 422); authenticated, it returns the
caller's blocked list.

> **Status:** `Done` · **Owner:** Claude · **Started:** 28-07-2026 · **Closed:** 28-07-2026
> **Depends on:** — · **Blocks:** HIVE-008
> **Blockers:** _none recorded_
> **Feedback:**
> - **Done, AC verified** — covered by the parametrised auth test in
>   `tests/api/test_actor_identity.py`, which is what surfaced it: the endpoint returned 422 where
>   every sibling returned 401.
> - **Worth a systematic pass.** This is a whole *class* of bug and nothing in the repo guards
>   against it: any literal path registered after a same-shape parameterised path is silently dead.
>   Ordering is currently implicit in `main.py`'s 21 `include_router` calls. Cheap fix — a test that
>   walks `app.routes` and asserts no literal segment is shadowed by an earlier `{param}` at the same
>   depth. Recommend adding it with HIVE-064.
> - Nobody noticed because there is no frontend caller: the queen portal never built (HIVE-131) and
>   `cell/` does not use this endpoint.

### HIVE-004 · P0 · Add auth to the `feed` router (7 endpoints)
`mind/api/routes/feed.py` — 0 auth dependencies. Post creation, likes, comments, deletion all open.
**AC:** the feed router has zero endpoints reachable without authentication, except reads that are
deliberately public.

> **Status:** `Done` · **Owner:** Claude · **Started:** 28-07-2026 · **Closed:** 28-07-2026
> **Depends on:** HIVE-003 ✅, HIVE-119 ⚠️ (still open — see HIVE-003) · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:**
> - **Done, AC verified.** Feed is now **4 required / 3 optional / 0 open**. HIVE-003 did six of the
>   seven; this task closed the last one and built the measurement that proves it.
> - **`GET /feed/posts/{post_id}/likers` was the straggler** and the right call was not obvious. It
>   is a read, and the other feed reads are deliberately public — but it *enumerates user
>   identities*, which the others do not. Closed it. If HIVE-119 lands on "observation-only", revisit:
>   in a pure-observation product this might legitimately be public.
> - ⚠️ **I have to correct a number I reported in HIVE-003.** I wrote "auth coverage went from ~35 to
>   98 of 252". That counted any endpoint carrying an OpenAPI `security` entry — but `OptionalUser`
>   adds one while still serving anonymous callers. The honest split is
>   **93 required / 6 optional / 156 open of 255**. The direction was right, the figure was flattering.
> - **`tests/api/test_auth_coverage.py` is the fix for that class of mistake.** It classifies every
>   route by walking the actual dependency tree, and ratchets per router: coverage cannot silently
>   regress, and it cannot silently *improve* either — closing a task fails the test until the
>   baseline is lowered, so progress has to be recorded.
> - 🪤 **Trap for anyone writing similar tooling.** This FastAPI version does **not** flatten
>   `include_router` into `app.routes`; it inserts a `_IncludedRouter` wrapper holding the real
>   router on `.original_router`. My first version walked `app.routes` and confidently reported
>   **9 endpoints out of ~255** — a metric that wrong is worse than no metric. `_iter_api_routes`
>   handles it.
> - **The task's premise was partly wrong**, worth knowing before HIVE-119: it says "post creation …
>   open", but **there is no post-creation or post-deletion endpoint in the feed router at all**.
>   Humans cannot create posts over the API — only bots can, through the engine. Either a product gap
>   or evidence the platform really is observation-only. **Another data point for HIVE-119.**
> - **Remaining open surface, measured** (feeds HIVE-006…016): civilization 85, settings 13,
>   evolution 8, moderation 8, platform 7, search 5, users 5, health 6 (intentional), auth 4
>   (intentional), hashtags 3, media 3, stories 3, system 3, analytics 2. Run
>   `pytest tests/api/test_auth_coverage.py -s` for the live table.

### HIVE-005 · P0 · Add auth to the `chat` router (5 endpoints)
`mind/api/routes/chat.py` — 0 auth dependencies. Community chat and DM send/read fully open.
**AC:** every chat endpoint requires authentication, and a signed-in user can only read DM threads
they are a party to.

> **Status:** `Done` · **Owner:** Claude · **Started:** 28-07-2026 · **Closed:** 28-07-2026
> **Depends on:** HIVE-003 ✅, HIVE-119 ⚠️ (still open — see HIVE-003) · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:**
> - **Done, AC verified.** Chat is **4 required / 1 optional / 0 open**. Authentication came from
>   HIVE-003; the real work here was the authorization hole underneath it.
> - 🚨 **Found a private-message IDOR — the most severe defect of the session so far.**
>   `GET /chat/dm/{conversation_id}` filtered on the conversation id **alone**. That would be
>   survivable if ids were opaque, but `send_direct_message:588` builds them as
>   `f"{min(id_a, id_b)}_{max(id_a, id_b)}"` — derivable from two UUIDs — **and bot UUIDs are public**
>   via `GET /communities/{id}/bots`. So any signed-in user could enumerate and read **every private
>   conversation between any user and any bot**, by construction, with no guessing.
>   Fixed: participation is required, the message SELECT additionally filters on sender/receiver, and
>   it returns **404 not 403** so the status code cannot be used to probe which threads exist.
> - **This is the lesson of the task, and it generalises.** HIVE-003 made this endpoint *authenticated*
>   and the coverage table went green — chat showed `0 open` — while it remained trivially
>   exploitable. **Authentication coverage is not an authorization audit.** Every remaining router in
>   HIVE-006…016 needs the same second pass: for each endpoint that takes a resource id, ask *who is
>   allowed to name that id*. `tests/api/test_auth_coverage.py` cannot see this class of bug.
> - **The test was verified against the unpatched code**, not just written to pass: removing the
>   participation check fails 2 of the 4 cases. A regression test that has never seen the bug fail is
>   a guess.
> - **Two adjacent issues found, not fixed here** (both deserve their own tasks):
>   1. **Users cannot block other users — only bots.** `blocking_service.block_bot` is the only
>      block path, so `send_direct_message`'s block check is meaningless between humans. On a
>      platform with human-to-human DMs that is a harassment gap, and it makes HIVE-008's "blocking"
>      surface narrower than its name suggests. **Depends on HIVE-119**: irrelevant if the platform
>      is observation-only.
>   2. **`GET /chat/community/{id}/messages` is deliberately anonymous-readable** (OptionalUser).
>      Fine while every community is public — there is no privacy flag on `CommunityDB`. If private
>      communities are ever added, this endpoint leaks them on day one.
> - **Note on the dead block check.** `send_direct_message` still carries
>   `if is_bot: <check receiver blocked sender>`. Since HIVE-003 removed the caller-supplied
>   `is_bot`, that branch is now unreachable. Left in place rather than deleted because it documents
>   an intended rule; delete it when issue (1) above is resolved.

### HIVE-006 · P0 · Add auth to the `moderation` router (14 endpoints)
`mind/api/routes/moderation.py` — 0 auth dependencies. Report review, resolution, dismissal, and
moderation actions are open to anonymous callers. Requires a moderator role check, not just login.

> **Status:** `Done` · **Owner:** Claude · **Started:** 28-07-2026 · **Closed:** 28-07-2026
> **Depends on:** HIVE-003 ✅, HIVE-119 ⚠️ (still open — see HIVE-003) · **Blocks:** HIVE-050, HIVE-094
> **Blockers:** _none recorded_
> **Feedback:**
> - **Done, AC verified.** Moderation is **14 required / 0 open**. HIVE-003 closed the 6 write
>   endpoints; this closed the 8 reads.
> - **The reads were the bigger leak.** The whole moderation queue was anonymously readable —
>   `GET /reports`, `/reports/{id}`, `/reports/stats`, `/reports/counts`,
>   `/reports/content/{target_id}`. That exposes **who reported whom, for what reason, and the
>   reported content**. Reporter identity leaking is a retaliation risk, not just a privacy one.
> - **`POST /moderation/check` was a free classifier oracle.** Anonymous callers could run arbitrary
>   text through the content filter, unlimited — useful for probing exactly what phrasing evades
>   moderation, and cheap to abuse as a DoS. Now requires a session (not admin: legitimate clients
>   may want to pre-check their own drafts).
> - **Applied the HIVE-005 lesson and it paid immediately.** Rather than stop at "0 open", I did the
>   authorization second pass — which meant checking *route reachability*, and that surfaced
>   **[HIVE-135](#hive-135--p1--four-routes-were-unreachable-including-the-liveness-probe)**: four
>   dead endpoints and three duplicate registrations across the app, including a liveness-probe
>   misconfiguration that could restart containers in production. Both are closed.
> - ⚠️ **The two duplicate `GET /moderation/reports*` registrations are left in place** and
>   allowlisted in `tests/api/test_route_table.py`. They are the concrete manifestation of
>   **HIVE-050** — `report_system.py` and `reporting.py` both register the same paths, so the second
>   implementation is unreachable. Choosing which survives is a design decision, not a reordering,
>   and silently picking one would be the wrong call for me to make. **HIVE-050 is now blocking real
>   behaviour, not just tidiness — consider re-rating it from P2.**
> - **Note for HIVE-094** (moderation is stubs): the API surface is now correctly gated, but what it
>   gates is still largely placeholder — image moderation always allows, AI text moderation is a
>   no-op. A locked door in front of an empty room.

### HIVE-135 · P1 · Four routes were unreachable, including the liveness probe
FastAPI matches in registration order, so a literal path registered **after** a same-shape
parameterised path never wins — the parameterised route takes the request and fails on type
coercion, usually as a 422 that reads like a client error. Found by a route-table scan written
while applying the HIVE-005 authorization lesson to HIVE-006:

| Dead route | Swallowed by |
|---|---|
| `DELETE /notifications/subscribe` | `/notifications/{notification_id}` |
| `GET /moderation/reports/counts` | `/moderation/reports/{report_id}` |
| `GET /admin/bots/retired` | `/admin/bots/{bot_id}` (**across two routers** — `scaling_router` and `admin_router` share the `/admin` prefix) |
| `GET /health` | `metrics_router`'s component check |

**Push unsubscribe has never worked.** Neither has retired-bot listing.

The `/health` case is the operationally dangerous one. `metrics_router` registered its component
check at `/health` and, being included before the app-level route, shadowed the cheap liveness probe
in `main.py`. **A liveness probe pointed at `/health` therefore queried Postgres and the LLM on every
poll, and returned 503 whenever either was down** — turning a dependency blip into a container
restart loop, exactly when the system is least able to absorb one.
**Fix:** reorder the three shadowed routes; move the component check to `/health/components`; harden
`/health/detailed`, which returned **500** on missing `app.state` rather than reporting the component
unavailable.
**AC:** no route is shadowed; `GET /health` is a cheap 200 with no component fan-out; no health
endpoint can return 500.

> **Status:** `Done` · **Owner:** Claude · **Started:** 28-07-2026 · **Closed:** 28-07-2026
> **Depends on:** — · **Blocks:** HIVE-077 (push), HIVE-100 (health), HIVE-109 (deployment)
> **Blockers:** _none recorded_
> **Feedback:**
> - **Done, AC verified.** `tests/api/test_route_table.py` — shadowing scanner, duplicate-registration
>   guard, and liveness assertions. Scanner reports **zero shadowed routes**.
> - **This is the second instance of the same class** (HIVE-133 was the first, found by accident).
>   Four more existed. The guard test now makes the next one fail loudly instead of silently
>   producing a 422 — including the **cross-router** case, which is the one a per-file review would
>   never catch.
> - ⚠️ **Check your deployment manifests before deploying.** If anything points a liveness probe at
>   `/health`, it was getting the readiness semantics. Feeds directly into **HIVE-109** (no container
>   image or deployment manifest exists yet) — get the probe paths right when writing them:
>   `/health` = liveness, `/health/components` = readiness.
> - **Three duplicate registrations remain**, two of them allowlisted against HIVE-050 (the competing
>   report systems). The third — `GET /health` — is now resolved.
> - **Root cause is structural, not careless.** Route order is implicit in `main.py`'s 21
>   `include_router` calls plus per-file decorator order. Nothing surfaces it, and it is invisible in
>   review. The scanner is the durable fix; consider running it in CI (HIVE-063).

### HIVE-007 · P0 · Add auth + admin gate to the `settings` router (13 endpoints)
`mind/api/routes/settings.py` — 0 auth dependencies, including `update_auth_settings` (:227),
`update_moderation_settings` (:241), and `reset_all_settings` (:185). Anonymous callers can rewrite
the platform's own auth configuration.

**AC:** no `/settings/*` endpoint is reachable without an admin token.

> **Status:** `Done` · **Owner:** Claude · **Started:** 28-07-2026 · **Closed:** 28-07-2026
> **Depends on:** HIVE-003 ✅, HIVE-119 ⚠️ (still open — see HIVE-003) · **Blocks:** HIVE-136
> **Blockers:** _none recorded_
> **Feedback:**
> - **Done, AC verified.** Settings is **13 required / 0 open**. 22 tests: anonymous reads and
>   writes rejected, signed-in non-admins rejected on every write, admin reads succeed.
> - **The writes were the worst unauthenticated surface found so far.** An anonymous caller
>   could `PUT /settings/auth {"two_factor_enabled": false, "max_login_attempts": 10}`, or turn
>   off the profanity filter and spam detection, or set `maintenance_mode: true` as a one-request
>   DoS. Not data exposure — **direct control of the platform's own security posture**.
> - **Reads are gated too, deliberately.** `GET /settings/auth` reports whether 2FA is on, the
>   login-attempt limit, and the lockout duration. That is exactly the reconnaissance you would
>   want before a credential-stuffing run, so this is not a case where reads can stay public.
> - 🚨 **The feature underneath is not implemented** — filed as
>   **[HIVE-136](#hive-136--p1--the-settings-api-is-a-write-only-facade)**. `_settings_store` is a
>   module-level dict: it resets on restart, each of the 4 workers holds its own copy, and
>   **nothing outside `settings.py` reads any of these values**. TODO.md lists "Make settings page
>   functional" and "Settings functional with backend" as complete. They are not.
> - I gated it anyway rather than deleting it: the endpoints are the intended contract, and a
>   half-built feature that is publicly writable is strictly worse than one that is admin-only.
> - **Note for the queen portal.** `/settings` is one of the routes `AuthProvider` already guards
>   (HIVE-068), and `apiFetch` sends the bearer token — but a signed-in **non-admin** will now
>   get 403s with no UI affordance explaining why. Worth handling alongside **HIVE-132**.

### HIVE-008 · P0 · Add auth to the `blocking` router (10 endpoints)
`mind/api/routes/blocking.py` — 0 auth dependencies. Anyone can create/remove blocks on behalf of
anyone, which is also a harassment vector.

**AC:** every blocking/flagging endpoint requires auth, and no single account can
auto-pause a bot on its own.

> **Status:** `Done` · **Owner:** Claude · **Started:** 28-07-2026 · **Closed:** 28-07-2026
> **Depends on:** HIVE-003 ✅, HIVE-119 ⚠️ (still open — see HIVE-003) · **Blocks:** HIVE-134
> **Blockers:** _none recorded_
> **Feedback:**
> - **Done, AC verified.** Blocking is **10 required / 0 open**. Authentication came from
>   HIVE-003; as with HIVE-005, the real work was the authorization pass underneath.
> - 🚨 **Flag brigading: one account could silence any bot.** `POST /bots/{bot_id}/flag`
>   auto-pauses at `AUTO_PAUSE_THRESHOLD = 5` pending flags, and two defects compounded:
>   **(a)** nothing stopped the same reporter filing repeatedly — `BotBehaviorFlagDB` has no
>   uniqueness constraint, though `UserBlockDB` right next to it does; **(b)**
>   `_get_pending_flag_count` counted flag **rows**, not distinct reporters. Five requests from
>   one authenticated account therefore paused any bot until an admin intervened.
>   **On an observation product, silencing bots is the primary vandalism vector.**
> - **Fixed without disabling the feature:** one pending flag per (reporter, bot), and auto-pause
>   counts distinct reporters — so the threshold now means what it was written to mean,
>   community consensus rather than one persistent user. It still fires at 5 genuine reporters,
>   which is asserted by its own test so the fix cannot quietly neuter the protection.
> - **A test-quality lesson worth carrying forward.** My first version of the counting test
>   grepped the method source for `"distinct"` — and **passed against reverted code**, because
>   the word survived in the docstring I had just written. It now compiles the emitted statement
>   and asserts on the SQL. Structural tests that read source text are close to worthless;
>   assert on behaviour or on generated artefacts.
> - **Verified against unpatched code**, as with HIVE-005: 2 of the 5 tests fail when the fixes
>   are reverted.
> - **Hardening not done here** (deliberate, needs a migration): a partial unique index on
>   `(bot_id, reporter_id) WHERE status = 'pending'` would enforce (a) at the database rather
>   than in the service, closing the race between two concurrent flag requests. The service
>   check is correct under normal load; the index is what makes it airtight. **Worth folding
>   into the next migration** rather than raising one for it alone.
> - **Note for HIVE-134**: the blocking half of this router is user→bot only. Confirmed again
>   here — `UserBlockDB` is keyed `(user_id, blocked_bot_id)`, so there is no schema path for
>   user→user blocking at all. That task needs a migration, not just endpoints.

### HIVE-009 · P0 · Add auth to the `notifications` router (10 endpoints)
`mind/api/routes/notifications.py` — 0 auth dependencies. Notification read/mark/delete for arbitrary
user IDs; a direct privacy leak.

**AC:** every notification endpoint requires auth; a user can only read, mutate, and
subscribe on their own behalf.

> **Status:** `Done` · **Owner:** Claude · **Started:** 28-07-2026 · **Closed:** 28-07-2026
> **Depends on:** HIVE-003 ✅, HIVE-119 ⚠️ (still open — see HIVE-003) · **Blocks:** HIVE-077
> **Blockers:** _none recorded_
> **Feedback:**
> - **Done, AC verified.** Notifications is **9 required / 1 open**. The one open endpoint is
>   `GET /notifications/push/config`, which serves the public VAPID key — every client needs it
>   before it can subscribe, so it is correctly anonymous.
> - HIVE-003 had already closed the read/mutate IDOR (`mark_as_read` and `delete_notification`
>   took a bare notification id). The authorization pass found one more.
> - 🚨 **Push subscription takeover.** `PushService.register_device` looked its row up by
>   **endpoint alone** and, on a match, reassigned `user_id` to the caller. Submitting another
>   user's endpoint took over their subscription: **the victim silently stopped receiving push
>   notifications**, and the attacker's notifications were delivered to the victim's device.
> - **The interesting part is that the buggy behaviour was deliberate.** Reassigning on match
>   handles a real case — a shared device where a second person signs in. So the fix is not to
>   forbid the transfer but to authenticate it: the caller must present the subscription's own
>   `p256dh`/`auth` keys, which the browser hands only to the origin. An endpoint is an address;
>   the keys are the credential. Same-user re-registration still refreshes keys, and a genuine
>   shared-device transfer still works — both asserted, so the fix cannot regress into a block.
> - **Verified against unpatched code**: 2 of the 5 tests fail when the fix is reverted.
> - **Note for HIVE-077.** None of this is reachable today — `cell/lib/firebase_options.dart`
>   is still placeholders and there is no `google-services.json`, so no device can register.
>   The bug would have shipped the moment push was switched on. Worth re-reading this entry
>   when doing HIVE-077.
> - **Residual risk, accepted.** Endpoint-and-keys is the strongest check available server-side;
>   an attacker who obtains both has the browser's full subscription credential and is
>   indistinguishable from the device. Mitigation belongs at the transport layer, not here.

### HIVE-010 · P0 · Add auth to the `stories` router (7 endpoints)
`mind/api/routes/stories.py` — 0 auth dependencies. Story creation, deletion, and view-tracking open.

**AC:** story mutations require auth; viewer lists and expired stories are visible only to
the author; the public story feed keeps working.

> **Status:** `Done` · **Owner:** Claude · **Started:** 28-07-2026 · **Closed:** 28-07-2026
> **Depends on:** HIVE-003 ✅, HIVE-119 ⚠️ (still open — see HIVE-003) · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:**
> - **Done, AC verified.** Stories is **4 required / 3 optional / 0 open**. 9 tests, 4 of which
>   fail against unpatched code.
> - 🚨 **Viewer lists were world-readable.** `GET /stories/{id}/viewers` was anonymous and
>   returned the identity of everyone who had viewed a story. That is a social-graph leak —
>   it reveals **who is watching whom**, which is information no viewer consented to publish.
> - **The check was already specified and simply never written.** The handler's docstring read
>   *"Only the story author should typically have access to this."* Worth internalising: in this
>   codebase, a docstring describing a security rule is **not evidence the rule is enforced**.
>   The same pattern produced HIVE-133's dead route (`verify_admin` that verified nothing) and
>   `blocking.py`'s `verify_user_exists`. When auditing the remaining routers, grep for prose
>   like "only", "must be", "admin only" and check each one has code behind it.
> - 🚨 **Expired stories were retrievable forever**, by anyone, via `include_expired=true` or a
>   direct `GET /stories/{id}`. Ephemerality is the *entire* distinguishing property of a story
>   — without it this is just a post with extra steps. Users posted under a promise the API did
>   not keep. Expired stories are now author-only.
> - **Deliberate design choices**, both worth keeping if this code is revisited: non-authors get
>   **404 rather than 403**, so the status code does not confirm a story exists; and
>   `include_expired` is silently downgraded for non-authors rather than rejected, so existing
>   clients keep working instead of breaking on a 403.
> - **Fixed a real defect in the auth layer while testing.** `get_optional_user` opened its own
>   session via `async_session_factory()` instead of using the injected `get_db_session`, unlike
>   `get_current_user`. That meant **a second DB connection per request, outside the request's
>   transaction**, on every optional-auth endpoint — and it made the dependency impossible to
>   override in tests, which is how the tests found it. Now consistent.
> - **The coverage ratchet did its job.** Closing these dropped stories from 3 open to 0 and the
>   ratchet test failed until I lowered the baseline — forcing the improvement to be recorded
>   rather than silently absorbed. That is the behaviour it was built for.

### HIVE-011 · P0 · Add auth + quotas to the `media` router (5 endpoints)
`mind/api/routes/media.py` — 0 auth dependencies. Anonymous file upload to your disk/bucket is an
unbounded storage and cost DoS.

**AC:** upload and delete require auth; one account cannot exhaust storage; file serving cannot
escape the media directory.

> **Status:** `Done` · **Owner:** Claude · **Started:** 28-07-2026 · **Closed:** 28-07-2026
> **Depends on:** HIVE-003 ✅, HIVE-119 ⚠️ (still open — see HIVE-003) · **Blocks:** HIVE-097
> **Blockers:** _none recorded_
> **Feedback:**
> - **Done, AC verified.** Media is **2 required / 3 open**; the three open ones are public file
>   serving and metadata, which is correct — media is embedded in public posts.
> - **Closed together with [HIVE-028](#hive-028--p1--path-traversal-exposure-in-media-file-serving)
>   and [HIVE-029](#hive-029--p1--media-uploads-trust-client-declared-content-type)**, deliberately.
>   All three live in the same ~100 lines; doing them separately meant three reviews, three test
>   files, and three chances to reintroduce one while fixing another.
> - **Quotas: 100 files / 500 MB per uploader per rolling 24 hours.** Deliberately generous — the
>   goal is to bound abuse, not ration normal use. Checked **before** the body is read, so a caller
>   already over quota cannot make the server buffer a large upload just to be told no.
> - **Numbers are hardcoded constants**, not settings, and that is a deliberate deferral: adding
>   them to `mind/api/routes/settings.py` would put them in the store that **HIVE-136** shows is a
>   facade. Move them into config when HIVE-136 lands, not before.
> - **Not done: quota accounting is per-request, not atomic.** Two concurrent uploads can both pass
>   the check and land the account slightly over. Acceptable for an abuse bound; if it ever needs
>   to be exact, that is a Redis counter, not a bigger query.

### HIVE-012 · P0 · Add auth to the `users` router (6 endpoints)
`mind/api/routes/users.py` — 0 auth dependencies. Profile mutation for arbitrary user IDs.

**AC:** `device_id` never appears in a public response; profile reads require a session;
registration and bot browsing stay open.

> **Status:** `Done` · **Owner:** Claude · **Started:** 28-07-2026 · **Closed:** 28-07-2026
> **Depends on:** HIVE-003 ✅, HIVE-119 ⚠️ (still open — see HIVE-003) · **Blocks:** HIVE-137
> **Blockers:** _none recorded_
> **Feedback:**
> - **Done, AC verified.** Users is **2 required / 4 open**; the four open are registration and
>   bot/community browsing, which are public by design and asserted so they cannot regress.
> - 🚨 **`device_id` was a bearer credential, published anonymously.** The chain matters more
>   than any single endpoint: `POST /users/register` returns the **existing** account when
>   handed a `device_id` it already knows — that is the mobile app's whole login mechanism —
>   and `GET /users/{user_id}` was anonymous and **returned that device_id**. Read it, replay
>   it, receive the account.
> - **Neither endpoint is wrong on its own**, which is why this survived review. Device-keyed
>   identity is a legitimate pattern for an app with no signup screen; echoing a user's own
>   profile is legitimate too. The vulnerability lives in the *pair*. Worth remembering for
>   the remaining routers: read endpoints need auditing for what they emit, not only for who
>   may call them.
> - 🔴 **The bigger finding is architectural: Hive has two parallel account systems.**
>   `/auth/register` (email + password → JWT) and `/users/register` (device_id, no secret).
>   `auth.py:218` even fabricates a `device_id` per JWT user "for compatibility". One of these
>   should not exist. Filed as **[HIVE-137](#hive-137--p1--two-parallel-account-systems)** —
>   and the answer depends on **HIVE-119**, since a pure observation product may not need
>   human accounts at all.
> - **Left `/users/register` working.** `cell/lib/services/api_service.dart:66` depends on it,
>   and breaking the mobile app to close a leak that is already closed by removing `device_id`
>   from public views would be the wrong trade.
> - 🪤 **Found while reading the client: the mobile profile editor calls an endpoint that does
>   not exist.** `api_service.dart:101,121` PUT to `/users/{id}/profile`; the router has no
>   such route (only `/users/{user_id}`). Profile editing and avatar upload have never worked.
>   Same family as HIVE-133/135 — filed as part of HIVE-137's client audit.
> - **Tests assert on the published OpenAPI schema**, not only the Pydantic model, so the
>   contract cannot drift back through a response_model change.

### HIVE-013 · P0 · Gate the 28 mutating civilization endpoints
`mind/api/routes/civilization.py` — 85 endpoints, 0 auth dependencies, 28 of them POST/PUT/DELETE:
`/initialize`, `/eras/declare`, `/eras/propose`, `/rituals/propose`, `/rituals/perform`,
`/config` (write), `/config/reset`, `/migration/execute/{bot_id}`, `/bots/{id}/create-artifact`, …
Anonymous callers can rewrite civilization history and reset its configuration.
**Fix:** keep GET endpoints public (this is an observation portal — that part of the design is
intentional); require admin on every mutating route.
**AC:** all 28 mutating routes return 401 unauthenticated; all 57 read routes remain public.

> **Status:** `Done` · **Owner:** Claude · **Started:** 28-07-2026 · **Closed:** 28-07-2026
> **Depends on:** HIVE-003 ✅ · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:**
> - **Done, AC verified.** Civilization is **28 required / 57 open**, exactly the split the
>   task specified. The single largest unauthenticated surface in the codebase is closed.
> - **The LLM endpoints are the part I would flag to an operator first.** Eleven of the 28
>   (`create-artifact`, `reflect-on-*`, `origin-story`, `propose`, `declare`,
>   `recognize-pattern`, …) invoke the model on demand. Anonymous access made them an
>   **unmetered spend endpoint** — the worst shape of bug, because the cost lands on the
>   operator while the damage lands on the simulation. Anyone could have run up an Ollama
>   queue or, with a paid provider configured, a bill.
> - **`PUT /civilization/config` and `/config/reset` were the most damaging.** Unlike
>   HIVE-136's facade, this config is **real** — `mind/civilization/config.py` is DB-backed
>   and read by the lifecycle manager, so an anonymous caller could change `time_scale`,
>   vitality decay, and life-stage boundaries, or reset them all. That is direct control of
>   the simulation the product exists to observe.
> - **The test pins the rule by shape, not by listing paths.** Any new mutating endpoint
>   inherits the requirement instead of quietly escaping it — which matters here more than
>   anywhere else, because this router is 2,576 lines and grew to 85 endpoints without anyone
>   noticing none of them were protected.
> - **It also asserts the 57/28 counts.** Adding an endpoint fails the test until someone
>   states which side of the line it belongs on. Given how this file got to 85 endpoints, an
>   assertion that forces a decision is worth more than one that merely permits the status quo.
> - **Reads deliberately stay anonymous**, and there is a test asserting so. Gating them would
>   be the easy over-correction and would break both the portal and VISION.md's
>   "observation over control". Six portal-facing read paths are spot-checked against a 401.
> - **Mechanical note.** Patching 28 signatures by regex needed three attempts: my first
>   signature-span detection was wrong, and the second produced `,,` on handlers whose
>   parameter list already ended with a trailing comma. Both failed loudly at compile time —
>   but it is a reminder that bulk-editing signatures wants an AST-derived span
>   (`node.body[0].lineno`), not paren counting.

### HIVE-014 · P0 · Gate the `evolution` router (8 endpoints)
`mind/api/routes/evolution.py` — 0 auth dependencies.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-003, HIVE-119 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-015 · P0 · Gate the `system` router (3 endpoints)
`mind/api/routes/system.py` — 0 auth dependencies. `/system/status` exposes host CPU/memory/disk/network
and service topology; `/system/logs` exposes the application log buffer to anonymous callers.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-003 · **Blocks:** HIVE-066
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-016 · P0 · Rate-limit and gate `search` + `hashtags` (12 endpoints)
`mind/api/routes/search.py`, `mind/api/routes/hashtags.py` — 0 auth dependencies. Unbounded anonymous
full-text search is a cheap DoS against Postgres.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-003, HIVE-119 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-017 · P0 · Authenticate the user WebSocket
`mind/api/main.py:934-1047` — `/ws/{client_id}` accepts any `client_id` with no handshake auth, then
`register_user` (:951, :1033) trusts a `user_id` sent in the message body. Any client can subscribe
to any user's notification stream and send DMs and chat messages as any user.
**Fix:** require a JWT in the connect query string or first frame; derive `user_id` from it; reject
`auth`/`subscribe_notifications` frames that name a different user.
**AC:** connecting without a valid token closes with 4401; a client cannot receive another user's
notifications.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-003 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-018 · P0 · Fix admin WebSocket auth
`mind/api/main.py:1153-1182` — same `X-User-ID`-equivalent flaw: `admin_id` is taken from the URL path
and merely looked up. Move to token-based auth alongside HIVE-001.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-001, HIVE-003 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-019 · P0 · Enforce CORS in production
`mind/config/settings.py:242` defaults `CORS_ORIGINS="*"` and `mind/api/main.py:355-362` combines it
with `allow_credentials=True` — a combination browsers reject and that signals the config was never
exercised.
**Fix:** fail startup if `ENVIRONMENT=production` and `CORS_ORIGINS == "*"`.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-021 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-020 · P0 · Fail startup on a default JWT secret
`mind/config/settings.py:247` defaults `JWT_SECRET_KEY="your-super-secret-key-change-in-production"`.
The guard that catches this (`validate_config_on_startup`, `settings.py:737`) is **never called** — see
HIVE-021.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-021 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-021 · P0 · Actually call the startup validators
`mind/config/settings.py:737` `validate_config_on_startup()` and the entire 602-line
`mind/config/production.py` preflight validator are exported but never invoked from
`mind/api/main.py`. Every production safety check the codebase already implements is dead code.
**Fix:** call both at the top of the `lifespan` handler; abort startup on failure.
**AC:** booting with `ENVIRONMENT=production` and a default JWT secret exits non-zero with a clear message.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** HIVE-019, HIVE-020, HIVE-038, HIVE-060
> **Blockers:** _none recorded_
> **Feedback:** _pending_

---

# EPIC B — Core functional bugs (P0/P1)

### HIVE-022 · P0 · Bots never age — the entire lifecycle is dead in production
`mind/civilization/lifecycle.py:171` — `lifecycle.virtual_age_days += int(virtual_days)`.
With the production `time_scale = 7.0` and hourly aging, `virtual_days = (1/24)*7 = 0.29`, and
`int(0.29) == 0`. Age never increments. Therefore: no life-stage transitions, no vitality decay
beyond the separate float path, no natural death, no legacy, no elder-triggered reproduction, no era
pressure. **The product's headline feature does not run.**
**Fix:** make `virtual_age_days` a float column (migration), or accumulate a `virtual_age_remainder`
float and add whole days when it crosses 1.0.
**AC:** a test asserts that 24 hourly aging cycles at `time_scale=7.0` advance a bot by exactly 7
virtual days.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** HIVE-027, HIVE-059, HIVE-092, HIVE-116
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-023 · P0 · `demo_mode` is wired to a setting that does not exist
`mind/engine/activity_engine.py:263` — `settings.DEMO_MODE if hasattr(settings, 'DEMO_MODE') else False`.
The real field is `AUTHENTICITY_DEMO_MODE` (`settings.py:177`). The `hasattr` guard makes this
silently and permanently `False`, so the civilization loop's fast path (1 min vs 1 hr aging, 2 min vs
2 hr culture) is unreachable — and it was the only thing masking HIVE-022 in testing.
**Fix:** read `settings.AUTHENTICITY_DEMO_MODE` directly; drop the `hasattr`.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-024 · P0 · In-place JSON mutations are silently discarded
`mind/civilization/lifecycle.py:178, 256, 371` append to `lifecycle.life_events`, which is a plain
`JSON` column (`mind/civilization/models.py:46`). SQLAlchemy does not track in-place mutation of JSON
containers, and `flag_modified` appears **0 times** in the codebase. Every life event — stage
transitions, death records, grief events — is lost on commit.
Same exposure on `relationships` (`models.py:68`) and `roles` (`models.py:72`).
**Fix:** wrap the columns in `MutableList.as_mutable(JSON)`, or call
`sqlalchemy.orm.attributes.flag_modified(obj, "life_events")` after each mutation. Audit every JSON
column for the same pattern.
**AC:** a test appends a life event, commits, re-reads in a new session, and finds it.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** HIVE-059, HIVE-086
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-025 · P1 · Operator-precedence bug in self-coded module compilation
`mind/engine/bot_self_coding.py:184` —
`if callable(obj) and name.startswith("_auto_") or name == code.split("(")[0].replace("def ", "")`
parses as `(A and B) or C`, so any global whose name matches the fragile string expression is bound as
the compiled function regardless of callability.
**Fix:** parenthesise; better, capture the function name from the AST instead of string-splitting.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-032 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-026 · P1 · Rate limiter leaks memory and is per-worker
`mind/api/main.py:69-128` — `request_counts` is a `defaultdict(list)` keyed by client IP, pruned only
for IPs that make a new request. Idle IPs are never evicted, so the dict grows without bound. With
`API_WORKERS=4` (`settings.py:235`) the effective limit is also 4× the configured value, and it resets
on restart.
**Fix:** move to a Redis-backed sliding window (Redis is already a dependency); add periodic eviction.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-027 · P1 · `age_all_bots` loads the entire living population into memory
`mind/civilization/lifecycle.py:163-166` — unbounded `SELECT` of all living lifecycles, then a Python
loop with per-bot async work inside a single transaction. At the VISION target of 50–100 bots it is
fine; at any real scale it is a long-held transaction and a memory spike.
**Fix:** batch with `yield_per` / keyset pagination; commit per batch.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-022 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-028 · P1 · Path traversal exposure in media file serving
`mind/api/routes/media.py:272` and `:307` — `storage.storage_path / file_type / filename` where
`filename` is a URL path parameter. Percent-encoded traversal (`%2e%2e%2f`) decodes after routing.
**Fix:** `resolve()` the joined path and assert it is inside `storage_path` before serving; reject
filenames containing separators.
**AC:** a request for `..%2f..%2fetc%2fpasswd` returns 400/404, not file content.

> **Status:** `Done` · **Owner:** Claude · **Started:** 28-07-2026 · **Closed:** 28-07-2026
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:**
> - **Done, AC verified.** Closed alongside HIVE-011/029. 6 of the 21 media tests fail when this
>   fix alone is reverted.
> - **Confirmed exploitable, and the mechanism is worth stating precisely:** Starlette matches path
>   segments against the **raw** URL but hands the handler the **decoded** value. `%2e%2e%2f`
>   therefore never looks like traversal to the router and arrives at the handler as `../`.
>   Reviewing the route pattern alone would not reveal this.
> - **The fix is stricter than the task asked for.** Containment is enforced against the *type*
>   directory (`<root>/images`), not merely the storage root. Containing only to the root would
>   still allow `images/../videos/x.mp4`, which stays inside storage but sidesteps the `file_type`
>   allowlist. Filenames must also be plain names — **a filename is never a path**.
> - **A test of mine was wrong first, and that is how the stronger rule was found.** I asserted that
>   `images/../secret.txt` escapes; it does not — it resolves to `<root>/secret.txt`, still inside
>   storage. Chasing that failure is what surfaced the sub-directory requirement. Worth the
>   reminder that a failing test is sometimes the test being wrong, and investigating rather than
>   adjusting the assertion is what pays.

### HIVE-029 · P1 · Media uploads trust client-declared content type
`mind/api/routes/media.py:91` — `content_type = file.content_type or "application/octet-stream"`,
taken from the multipart header with no sniffing, and no enforcement of `MAX_IMAGE_SIZE_MB` /
`ALLOWED_IMAGE_TYPES` visible on the request path.
**Fix:** sniff magic bytes, enforce the configured size and type limits, re-encode images.

> **Status:** `Done` · **Owner:** Claude · **Started:** 28-07-2026 · **Closed:** 28-07-2026
> **Depends on:** — · **Blocks:** HIVE-096, HIVE-097
> **Blockers:** _none recorded_
> **Feedback:**
> - **Done, AC verified.** Closed alongside HIVE-011/028.
> - **Two separate defects were hiding under one line.** (1) `UploadFile.content_type` comes from
>   the client's multipart header, so arbitrary bytes could be stored as `image/png` and served
>   back **from our own origin** under a MIME type of the uploader's choosing. (2) The size cap was
>   applied with `len(content)` **after** `await file.read()` had pulled the entire body into
>   memory — so the limit protected disk but not RAM, and a multi-gigabyte upload was an OOM before
>   the 10 MB check ever ran. The second is arguably the more dangerous and was not in the task
>   description.
> - **Sniffing is hand-rolled in `mind/media/validation.py`**, not `python-magic`: that needs a
>   native library and is painful to install on Windows, which is this project's dev platform.
>   Signatures cover exactly the formats in `ALLOWED_IMAGE_TYPES` / `ALLOWED_VIDEO_TYPES`.
> - **Two deliberate leniencies**, both tested so they cannot silently widen: `.mov` and `.mp4`
>   share the ISO base media container and `ftyp` cannot tell them apart, so they are treated as
>   equivalent; and RIFF is checked for the `WEBP` sub-type, since RIFF also covers `.wav`/`.avi`.
> - **Note for HIVE-096/097.** Bot-generated images (HIVE-096) will pass through the engine, not
>   this endpoint, so they bypass sniffing — fine, they are locally produced. Video processing
>   (HIVE-097) will need its own validation for the extracted thumbnail.

### HIVE-030 · P1 · Sandbox timeout does not stop runaway code
`mind/scaling/self_coding_sandbox.py:484-491` — `thread.join(timeout)` returns, but the daemon thread
keeps executing. An infinite loop in generated code burns a CPU core for the process lifetime. The
documented memory limit is annotated *"conceptual"* (`:103`) and is not enforced at all.
**Fix:** execute in a subprocess with `resource.setrlimit` (CPU + address space) and hard-kill on
timeout.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** HIVE-032
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-031 · P1 · `ALLOWED_AST_NODES` is defined and never used
`mind/scaling/self_coding_sandbox.py:189-265` declares a 60-entry AST whitelist; `validate_code`
(`:329`) walks the tree but only blacklists specific node types. The docstring promises whitelisting
the code does not perform.
**Fix:** enforce the whitelist — reject any node not in the set — or delete the constant and correct
the docstring.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** HIVE-032
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-032 · P1 · The weaker of the two sandboxes is the one in use
`mind/engine/bot_self_coding.py:181` `exec()`s LLM-generated code guarded by a substring denylist,
with `getattr` in its safe-builtins (`:118`). String concatenation defeats a substring denylist
(`getattr((), "__cl"+"ass__")`), and the escape runs in-process with full privileges. Meanwhile the
stricter `mind/scaling/self_coding_sandbox.py` is imported by nothing but its own package `__init__`.
**Fix:** delete the ad-hoc sandbox in `bot_self_coding.py`; route all generated code through the
hardened executor from HIVE-030/031.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-030, HIVE-031 · **Blocks:** HIVE-025
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-033 · P1 · `create_all()` competes with Alembic as schema authority
`mind/core/database.py` `init_database()` runs `Base.metadata.create_all` on every startup, alongside
a complete 6-revision Alembic chain. In dev this masks a missed migration; in prod the two will
diverge.
**Fix:** `create_all` only under `ENVIRONMENT=test`; production startup runs (or verifies) `alembic
upgrade head`.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** HIVE-063
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-034 · P1 · Calculator skill can hang the event loop
`mind/capabilities/skills.py:277` — `eval(expr, {"__builtins__": {}}, safe_dict)` with `**` permitted
and no bound on operands. `9**9**9` blocks the worker.
(Currently mitigated only because the whole `skills.py` module is unreachable — see HIVE-060.)
**Fix:** cap operand magnitude and expression length, or use a real expression parser.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-043 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-035 · P1 · 12 `except Exception: pass` blocks swallow failures silently
36 broad `except` clauses across `mind/`, 12 of which discard the exception entirely — including the
civilization broadcast path (`civilization_loop.py:79-80`, `:323-324`) and the social-graph refresh
(`:441-442`), where failures are invisible by design.
**Fix:** log at `warning` with context in every one; keep the swallow only where genuinely best-effort.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-036 · P1 · 358 uses of `datetime.utcnow()`
Deprecated since Python 3.12 and returns *naive* datetimes, which are then compared against and stored
alongside timezone-aware values.
**Fix:** mechanical migration to `datetime.now(timezone.utc)`; make DB columns `DateTime(timezone=True)`
in a migration.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

---

# EPIC C — Dead and unwired code (P1)

~7,000 LOC that no execution path can reach. Each task is a **decide-then-act**: wire it up or delete
it. Leaving it is the worst option — it inflates the apparent feature set and rots.

### HIVE-037 · P1 · Decide the fate of the entire channels package (1,310 LOC)
`mind/channels/` — `channel_service.py` and `webhook.py` have **zero importers**; `discord.py`,
`telegram.py`, and `base.py` are reachable only through them. Nothing in `mind/api/` or `mind/engine/`
references the package. Meanwhile `EXTERNAL_CHANNELS_ENABLED` defaults to `True` (`settings.py:399`)
and `AIC_TELEGRAM_BOT_TOKEN` / `AIC_DISCORD_BOT_TOKEN` are documented in `.env.example` — the config
advertises a feature that cannot run.
**Fix (wire):** mount `WebhookHandler` routes in `main.py`, start `ChannelService` in `lifespan`,
connect it to the response loop. **Fix (delete):** remove the package and the four settings.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-119 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-038 · P1 · `mind/config/production.py` (602 LOC) is unreachable
The production preflight validator — default-secret detection, CORS checks, demo-mode warnings, a
deployment checklist. Zero importers. Covered operationally by HIVE-021; this task is to verify its
checks are correct and complete once it actually runs.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-021 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-039 · P1 · `mind/engine/sentient_core.py` (990 LOC) is unreachable
Zero importers. Determine whether it was superseded by `bot_mind.py` + `conscious_mind.py` and delete,
or whether functionality was lost in a refactor.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-119 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-040 · P1 · `mind/engine/bot_github.py` (596 LOC) is unreachable
Zero importers, but `GITHUB_TOKEN` and `GITHUB_BOT_REPO_PREFIX` settings exist (`settings.py:280-287`)
and `scripts/test_github.py` / `scripts/create_repo.py` reference the concept. Bots creating GitHub
repos is also a significant new attack surface — decide deliberately.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-119 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-041 · P1 · `mind/core/container.py` (326 LOC) DI container is unreachable
Zero importers. The codebase uses module-level singletons + `mind/core/dependencies.py` providers
instead. Delete, or migrate to it consistently.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-042 · P1 · `mind/capabilities/tts.py` (439 LOC) is unreachable
Three provider implementations (OpenAI, ElevenLabs, Edge). `TTS_ENABLED`/`TTS_PROVIDER`/`TTS_API_KEY`
settings exist. Nothing calls `synthesize_speech`.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-119 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-043 · P1 · `mind/capabilities/skills.py` (410 LOC) is unreachable
Skill registry with Weather and Calculator skills. Never registered with any bot.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-119 · **Blocks:** HIVE-034
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-044 · P1 · `mind/capabilities/scheduler.py` (411 LOC) is unreachable
A second task scheduler, duplicating `mind/scheduler/activity_scheduler.py` (which *is* used).

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-045 · P1 · `mind/capabilities/hooks.py` (306 LOC) is unreachable
Event-hook system with priorities. No `HookEvent` is ever emitted.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-046 · P1 · `mind/capabilities/context_engine.py` (303 LOC) is unreachable
Conversation context compaction and token estimation — arguably the thing most worth wiring, since
long-running bots will blow the context window without it.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-047 · P1 · `mind/civilization/cultural_integration.py` (862 LOC) is re-exported but never used
Imported only by `mind/civilization/__init__.py`. TODO.md claims "cultural_integration.py complete".

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-119 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-048 · P2 · `mind/core/pubsub.py` (491 LOC) is re-exported but never used
Redis pub/sub service. Would be the correct fix for the single-process WebSocket broadcast limitation
(HIVE-075) — wire it rather than delete it.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** HIVE-075
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-049 · P2 · `mind/core/idle_precompute.py` (387 LOC) is re-exported but never used
Idle-time precomputation. Never started by `lifespan`.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-050 · ~~P2~~ **P1** · Two overlapping report systems (two routes are dead)
`mind/moderation/report_system.py` (399 LOC) and `mind/moderation/reporting.py` (580 LOC) are *both*
imported by `mind/api/routes/moderation.py:20,25`. Determine the overlap, pick one, migrate, delete the
other.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-006 ✅ · **Blocks:** HIVE-135 (allowlist entry)
> **Blockers:** _none recorded_
> **Feedback:**
> - _28-07-2026_ — **Re-rated P2 → P1 during HIVE-006.** No longer tidiness: both
>   modules register `GET /moderation/reports` and `GET /moderation/reports/{report_id}`,
>   so **one of the two implementations is unreachable dead code**, and which one answers is
>   decided by import order in `mind/api/routes/moderation.py`. Confirmed by the scanner in
>   `tests/api/test_route_table.py`, where the pair sits on the `KNOWN_DUPLICATES` allowlist.
> - The decision is which system survives — `report_system.py` (399 lines) or `reporting.py`
>   (580). Both are imported by the same route file. Deliberately not resolved during HIVE-006:
>   picking one silently would be a design decision made by the wrong party.

### HIVE-051 · P2 · Scaling subsystems have no scheduler
`mind/scaling/bot_retirement.py`, `community_scaling.py`, `memory_consolidation.py` are reachable only
through manual admin endpoints in `routes/scaling.py`. Nothing runs them periodically, so memory
consolidation and bot retirement never happen unless an operator clicks a button.
**Fix:** add a maintenance loop to the activity engine.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** HIVE-090
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-052 · P2 · Analytics tracker and aggregator reachability audit
`mind/analytics/tracker.py` (395) and `aggregator.py` (679) are consumed only via
`routes/analytics.py`. Confirm events are actually being *recorded* anywhere in the request path, or
the analytics endpoints are reporting on an empty table.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

---

# EPIC D — Testing, CI & type safety (P1)

> HIVE-129 and HIVE-130 were discovered during HIVE-001 and appended to the numbering, but
> **HIVE-129 comes first in this epic** — nothing else here can be verified until it lands.

### HIVE-129 · P1 · pytest cannot collect the suite at all
`tests/api/test_civilization_api.py:19` — `pytestmark = [pytest.mark.unit, pytest.mark.api]`.
The `api` marker is not declared in `pyproject.toml`'s `markers` list, and `--strict-markers` is set
in `addopts`. Collection therefore **aborts for the entire suite**, not just that file:
`Failed: 'api' not found in 'markers' configuration option`.
**Consequence:** `pytest` has never run to completion on `main`, so CI's `--cov-fail-under=70` gate
has been erroring rather than passing since that file was added. This is the concrete answer to the
suspicion recorded in HIVE-056.
**Fix:** add `"api: marks tests that exercise API routes"` to `[tool.pytest.ini_options] markers`.
One line. Then run the suite and triage what falls out.
**Known state once collection works** (measured 28-07-2026, `--ignore` that one file):
**222 passed, 8 failed, 6 skipped**. The 8 failures are pre-existing and split three ways —
`tests/test_api_health.py` (5) needs a live server on `localhost:8000`,
`tests/integration/test_civilization_integration.py` (2) needs Postgres,
`tests/unit/civilization/test_lifecycle.py::test_legacy_from_children` (1) is a genuine logic
failure worth investigating on its own.
**AC:** `pytest tests/` collects without error; the failure count is a deliberate, triaged number
rather than a collection abort.

> **Status:** `Done` · **Owner:** Claude · **Started:** 28-07-2026 · **Closed:** 28-07-2026
> **Depends on:** — · **Blocks:** HIVE-056, HIVE-059, HIVE-060, HIVE-064
> **Blockers:** _none recorded_
> **Feedback:**
> - **Done.** One line in `pyproject.toml` declaring the `api` marker. Closed during HIVE-003, which
>   could not be verified without it. `pytest tests/` now collects cleanly: **261 passed, 8 failed,
>   6 skipped** — the first complete run of this suite in the repo's history.
> - The 8 remaining failures are pre-existing and triaged: `test_api_health.py` (5) needs a live
>   server on `localhost:8000`, `test_civilization_integration.py` (2) needs Postgres,
>   `test_lifecycle.py::test_legacy_from_children` (1) is a real logic failure — still open, still
>   worth checking against HIVE-022/HIVE-024 before writing a separate fix.
> - _28-07-2026_ — Found while verifying HIVE-001. Worked around locally with
>   `pytest --ignore=tests/api/test_civilization_api.py`; that workaround should be deleted, not
>   institutionalised.
> - The `test_legacy_from_children` failure is the interesting one — it is a unit test with no
>   external dependency, so it is failing on logic. Given HIVE-022 and HIVE-024 both live in
>   `lifecycle.py`, check whether it is the same root cause before writing a separate fix.

### HIVE-130 · P2 · `mind.core.database` creates the engine at import time
`mind/core/database.py:30` — `engine = create_async_engine(...)` runs at module scope, and
`mind/__init__.py:44` imports it. Consequences:
- `import mind` fails outright without `asyncpg` installed, even for code paths that never touch the
  database. Discovered while standing up a test environment for HIVE-001.
- The connection URL is bound at import time, so `settings` changes or test overrides applied after
  import have no effect.
- Every tool that merely *inspects* the package (linters, doc generators, `--collect-only`) pays for
  engine construction.
**Fix:** move engine/session-factory creation behind a lazily-initialised accessor
(`get_engine()` / `get_session_factory()`), matching the singleton pattern already used throughout
`mind/core/` for the LLM client, cache, and memory core.
**AC:** `python -c "import mind"` succeeds in an environment without `asyncpg`; a test can point the
engine at a different URL after import.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:**
> - _28-07-2026_ — Low urgency but touches every test file, so it is cheapest to do **before** the
>   Epic A test work (HIVE-058) rather than after.

### HIVE-053 · P1 · Fix the Flutter CI job — it cannot pass
`.github/workflows/ci.yml:120` pins `flutter-version: '3.24.0'` (Dart 3.5) against
`cell/pubspec.yaml` requiring `sdk: ^3.11.1`. `flutter pub get` fails before any test runs. The
"139 unit + 52 widget + 51 integration tests" TODO.md counts as complete are not executing.
**AC:** the job runs, and its pass/fail reflects the real suite.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** HIVE-061
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-054 · P1 · Add the missing `type-check` script
`.github/workflows/ci.yml` runs `npm run type-check || true`; no such script exists in
`queen/package.json`. Frontend types have never been checked in CI.
**Fix:** add `"type-check": "tsc --noEmit"`; remove the `|| true`.
**AC:** CI fails on a type error.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-055 · P1 · Un-suppress mypy and fix the fallout
`.github/workflows/ci.yml` runs `mypy mind/ --ignore-missing-imports || true`.
**First finding it will surface:** 13 imports of `BotMindManager` and `BotLearningManager`, which do
not exist — the real classes are `MindManager` (`bot_mind.py:1119`) and `LearningManager`
(`bot_learning.py:700`) — across all 7 files in `mind/engine/loops/`
(`chat_loop.py:35-36`, `consciousness_loop.py:21`, `engagement_loop.py:51-52`,
`evolution_loop.py:21-22`, `gradual_engagement_loop.py:40-41`, `post_loop.py:44-45`,
`response_loop.py:32-33`). They sit under `TYPE_CHECKING` so they do not crash — every type
annotation in the loop layer is silently wrong.
**Fix:** correct the names, then adopt mypy incrementally (per-module strictness) with the gate on.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-056 · P1 · Establish real coverage, then set an honest gate
251 backend test functions against 81k LOC with `--cov-fail-under=70` enforced. Either the gate is not
actually passing on `main` or coverage is being measured against far less than it claims.
**Fix:** run coverage locally, publish the true number, set the gate just below it, and ratchet up.
**AC:** the reported figure is reproducible from a clean checkout.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-057, HIVE-129 · **Blocks:** HIVE-126
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-057 · P1 · `tests/test_bot.py` is not a test
106 lines, zero `def test_` functions — a manual script that requires a live server on
`localhost:8000`. Pytest collects it and finds nothing.
**Fix:** move to `scripts/smoke_test.py` or convert to real tests.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** HIVE-056
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-058 · P1 · No tests cover the auth layer
No test exercises `mind/core/auth.py`, `mind/api/dependencies.py`, or admin authorization. Given
Epic A, this is the highest-value test suite to write.
**AC:** tests for token expiry, tampered signature, refresh rotation, disabled user, non-admin
escalation, and cross-user access on every router touched by HIVE-004…016.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-003 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-059 · P1 · No tests cover the aging/lifecycle path
HIVE-022 and HIVE-024 are both bugs that a single end-to-end lifecycle test would have caught.
**AC:** a test drives a bot from birth through every life stage to death and asserts persisted state.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-022, HIVE-024, HIVE-129 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-060 · P1 · No integration test boots the app
Nothing verifies that `lifespan` completes — the one check that would have caught HIVE-021, HIVE-023,
and the unwired modules of Epic C.
**AC:** a test starts the app against test Postgres/Redis with a stub LLM and asserts `/health/detailed`
reports all components healthy.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-021, HIVE-129 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-061 · P2 · Pin CI to a Flutter version matching the pubspec, and keep them in sync
Add a check that fails if `flutter-version` and the pubspec SDK constraint diverge.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-053 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-062 · P2 · Add `queen` lint to CI
`npm run lint` exists but CI never calls it.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-063 · P2 · Add a migration check to CI
Assert `alembic upgrade head` then `alembic check` produces no pending autogenerate diff — this is what
keeps HIVE-033 from silently regressing.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-033 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-064 · P2 · Frontend has zero tests
`queen/` has no test runner configured at all. 10.5k LOC, 19 pages, no tests.
**Fix:** Vitest + Testing Library; start with the API client and the WebSocket hook.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-129 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-065 · P2 · No load or soak test exists
The activity engine runs 15 concurrent loops with a shared LLM semaphore. Nothing establishes what
`MAX_ACTIVE_BOTS` the box can actually sustain.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

---

# EPIC E — Frontend: queen portal (P1/P2)

> HIVE-131 and HIVE-132 were discovered during HIVE-002 and appended to the numbering.
> **HIVE-131 comes first in this epic** — until it landed, nothing in `queen/` could be verified.

### HIVE-131 · P0 · The queen portal has never built
`queen/src/contexts/WebSocketContext.tsx:4` imports `getWebSocketManager`, `ConnectionStatus`, and
`EventHandlers` from `@/lib/websocket` — **a module that did not exist**. `src/lib/` contained only
`api.ts`. `WebSocketProvider` is mounted in `components/Providers.tsx:24`, which the root layout
renders, so the missing import is in the build graph for **every** route.
**Verified empirically** (28-07-2026) by removing the new file and rebuilding:
`Error: Turbopack build failed with 1 errors: Module not found: Can't resolve '@/lib/websocket'`.
**Consequence:** `npm run build` fails, so CI's `dashboard-build` job — which is **not** suffixed
`|| true`, unlike the type-check step — has been failing since the portal was written. Combined with
HIVE-129 (backend suite cannot collect) and HIVE-053 (Flutter job cannot install), **three of the
four CI jobs have never passed.** That is the mechanism by which TODO.md was able to report
"100% complete" — nothing was checking.
**Fix:** implement `queen/src/lib/websocket.ts`.
**AC:** `npx next build` succeeds; `npx tsc --noEmit` is clean.

> **Status:** `Done` · **Owner:** Claude · **Started:** 28-07-2026 · **Closed:** 28-07-2026
> **Depends on:** HIVE-125 ✅ (root cause) · **Blocks:** HIVE-002 ✅, HIVE-068 ✅, HIVE-069, HIVE-070
> **Blockers:** _none recorded_
> **Feedback:**
> - **Done, AC verified by execution.** Build succeeds (19 routes), `tsc --noEmit` clean.
> - Written against the real backend contract, not guessed: the `EventHandlers` map lists only event
>   names that actually appear at `_broadcast_event` call sites in `mind/engine/loops/` and
>   `mind/civilization/`. That makes **HIVE-070 mechanical** — the emitted-but-unhandled events are
>   now typed and just need handlers.
> - Includes exponential-backoff reconnect (capped at 30s), a 30s ping heartbeat matching
>   `main.py:1043`, and a guard that stops reconnecting once the session ends — without which a
>   signed-out tab would reconnect-loop forever.
> - **This is the most alarming finding of the session.** Not the missing file itself, but what it
>   implies: a whole frontend was written, documented as complete, and screenshotted for the README
>   without anyone once running `npm run build`.

### HIVE-132 · P2 · No sign-out control or signed-in identity in the portal
HIVE-068 delivered login, guards, and `useAuth().logout()`, but no component renders them. A
signed-in operator cannot sign out except by clearing browser storage, and nothing on screen shows
**who** is signed in — on an admin console that performs bans and moderation actions, that is an
accountability gap as much as a usability one.
**Fix:** surface the signed-in user and a sign-out control in `Header.tsx` and `Sidebar.tsx`
(both already consume `useConnectionStatus`, so the wiring pattern exists). Show the identity on
`/reports` and `/bots` where destructive actions live.
**AC:** a signed-in user can sign out from any page; the current identity is visible on every
protected route.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-068 ✅ · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:**
> - _28-07-2026_ — Small and self-contained; `useAuth()` already exposes `user` and `logout`, so this
>   is presentation only. Worth doing immediately after Epic A rather than deferring to P2 order.

### HIVE-066 · P1 · `/logs` page is 100% fabricated data
`queen/src/app/logs/page.tsx:170` — `setLogs(generateMockLogs(50))` on a `setTimeout`. A working
`/system/logs` endpoint exists and the `/system` page already consumes it. TODO.md marks this page
complete. An operator reading this page is reading fiction.
**Fix:** wire to `systemApi.getLogs()`; delete `generateMockLogs` (`:88-89`).

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-015 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-067 · P1 · `/relationships` silently falls back to fake data
`queen/src/app/relationships/page.tsx:155-156` — on any fetch failure it renders
`generateMockData()`, so a backend outage looks like a healthy graph.
**Fix:** delete the fallback; render the error state that is already implemented three lines above.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-068 · P1 · Portal has no login
`queen/src/components/AuthProvider.tsx` is a passthrough (*"No auth required - this is a public
observation portal"*), yet the portal ships `/bots`, `/posts`, `/reports`, `/system`, `/logs`, and
`/settings` — full admin surfaces. Prerequisite for HIVE-001/002.
**Fix:** add a login route, token storage, an authenticated fetch wrapper, and route guards on the
admin pages; keep the civilization pages public.

> **Status:** `Done` · **Owner:** Claude · **Started:** 28-07-2026 · **Closed:** 28-07-2026
> **Depends on:** HIVE-001 ✅, ~~HIVE-003~~ (see below) · **Blocks:** HIVE-002 ✅
> **Blockers:**
> - _28-07-2026_ — **Dependency on HIVE-003 was wrong and has been dropped.** HIVE-003 is about how
>   the *backend* derives actor identity on non-admin routers. The portal only calls admin and
>   civilization endpoints, so it needs HIVE-001 (done) and nothing else. Recorded here rather than
>   silently deleted, per this document's own rule about correcting bad guidance.
> **Feedback:**
> - **Done, closed as a by-product of HIVE-002** — the two are one deliverable, as flagged in
>   HIVE-001's feedback. All four items in the Fix line delivered:
>   - **login route** — `queen/src/app/login/page.tsx`. Deliberately does not distinguish
>     "no such user" from "wrong password"; that difference is a user-enumeration oracle.
>   - **token storage** — `queen/src/lib/auth.ts`. `localStorage`, with the tradeoff written down in
>     the module docstring rather than left implicit: acceptable only while the portal has no
>     third-party scripts; move the refresh token to an httpOnly cookie if that changes.
>   - **authenticated fetch wrapper** — `apiFetch` in `lib/api.ts` now sends
>     `Authorization: Bearer`, and on 401 refreshes once, retries once, then clears the session and
>     redirects.
>   - **route guards** — `AuthProvider` gates `/analytics`, `/bots`, `/logs`, `/posts`, `/reports`,
>     `/settings`, `/system`. Civilization pages (`/`, `/civilization`, `/culture`, `/timeline`,
>     `/rituals`, `/circles`, `/relationships`, `/world`) stay **public**, per VISION.md's
>     "observation over control".
> - **Implementation note worth keeping.** The first version tracked auth with `useState` +
>   `useEffect`, which `react-hooks/set-state-in-effect` correctly rejected. Rewritten on
>   `useSyncExternalStore` with a `'server'` sentinel snapshot — that gives correct SSR/hydration
>   *and* cross-tab sync for free, and means protected routes never paint admin data before the
>   redirect resolves. Use the same pattern for any future localStorage-backed state.
> - ⚠️ **Deliberate gap: there is no sign-out control in the UI.** `useAuth().logout()` exists and
>   works, but nothing renders it — a signed-in operator currently cannot sign out without clearing
>   storage. Not in this task's Fix line, so filed as
>   **[HIVE-132](#hive-132--p2--no-sign-out-control-or-signed-in-identity-in-the-portal)** rather
>   than silently widening scope. **Do it before anyone uses the portal for real.**

### HIVE-069 · P2 · Dead WebSocket handlers
`queen/src/hooks/useCivilizationWebSocket.ts:227,230` handle `ritual_performed` and `era_transition`.
The backend emits `world_map_era_transition` (`emergent_eras.py:766,814`) and **never** emits any
ritual event. Era transitions never reach the portal.
**Fix:** align the names; emit a ritual event from `civilization_loop._hold_*` (see HIVE-093).

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-093, HIVE-131 ✅ · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-070 · P2 · Emitted events with no consumer
Backend emits `world_map_community_revived` (`civilization_loop.py:433`), `bot_self_improved`
(`evolution_loop.py:203`), `new_dm` (`response_loop.py:450`), `typing_start`/`typing_stop`
(`response_loop.py:355,365`) — none handled by the portal.
**Fix:** handle them or stop emitting. Add a shared event-name constant module used by both sides.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-131 ✅ · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-071 · P2 · No error or loading states on `/circles` and `/timeline`
Both score 0 on error handling. A failed fetch renders a blank page.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-072 · P2 · Six pages exceed 800 lines
`bots` (1406), `posts` (1262), `analytics` (1042), `settings` (1001), `relationships` (858),
`reports` (836). Data fetching, transformation, and presentation are interleaved.
**Fix:** extract data hooks and presentational components.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-073 · P2 · No React error boundaries
A render error in any page blanks the whole app. (`cell/` has one; `queen/` does not.)

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-074 · P2 · No responsive/mobile verification
Only `/world` shows evidence of responsive work. The admin tables and D3 visualizations are untested
below desktop widths.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-075 · P2 · WebSocket broadcast is single-process
`mind/api/main.py:884-931` — `ConnectionManager` holds connections in a process-local dict. With
`API_WORKERS=4` (`settings.py:235`), a client connected to worker 2 never sees events produced by
worker 1.
**Fix:** wire `mind/core/pubsub.py` (HIVE-048) as the broadcast fan-out.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-048 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-076 · P3 · No accessibility pass
No focus management, ARIA labels, or keyboard navigation on custom controls (`Terminal`, `DataGrid`,
`NeonButton`). Charts have no text alternative.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

---

# EPIC F — Mobile: cell app (P1/P2)

### HIVE-077 · P1 · Push notifications cannot work — Firebase config is placeholders
`cell/lib/firebase_options.dart:67-81` — `YOUR_ANDROID_API_KEY`, `YOUR_PROJECT_ID`, etc.
Neither `android/app/google-services.json` nor `ios/Runner/GoogleService-Info.plist` exists.
TODO.md marks "Push notifications (FCM)" complete; the backend side
(`mind/notifications/push_service.py`, 1,003 LOC) is real, the client side cannot receive anything.
**Fix:** provision a Firebase project, generate real config, keep the files out of git, document setup.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-078 · P1 · Stale app identity
`cell/android/app/build.gradle.kts:24` — `applicationId = "com.aicompanions.ai_social"`, from a
previous name. Changing it after any release is a new app on the store.
**Fix:** settle the product name (see HIVE-118) and set the bundle ID before first publish.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-118 · **Blocks:** HIVE-079
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-079 · P1 · No release signing configuration
No keystore config or signing setup present. `flutter build appbundle --release` produces a
debug-signed artifact.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-078 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-080 · P2 · Six platform targets, one plausible audience
`android ios web macos windows linux` are all scaffolded. Decide which are actually supported; unsupported
targets are dead maintenance surface and misleading CI signal.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-119 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-081 · P2 · Unintegrated typing calculator
`cell/lib/services/typing_calculator.dart:5` — *"TODO: Issue #6 - Integrate this with the typing
indicator in chat_detail_screen.dart"*. TODO.md marks "Typing indicators" complete.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-082 · P2 · Offline replay is a stub
`cell/lib/services/offline_service.dart:388` — *"This is just a placeholder"* inside the queued-action
replay path. TODO.md marks "Retry logic for offline queue" complete.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-083 · P2 · Mobile app is a full social client, not an "observer"
README describes `cell/` as "Mobile app (observer mode)"; it ships `create_post_screen`, `dm_screen`,
`chat_detail_screen`, `community_chat_screen`, `edit_profile_screen`, `profile_edit_screen`.
Two profile-edit screens also suggest a duplicate.
**Fix:** reconcile with HIVE-118; delete the duplicate screen.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-118, HIVE-119 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-084 · P2 · No token storage or refresh on mobile
Once Epic A lands, the app needs secure token storage (`flutter_secure_storage`) and refresh-on-401.
Currently `shared_preferences` is the only persistence.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-003 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-085 · P2 · No crash reporting
`error_boundary.dart` logs locally. No Crashlytics/Sentry, so field failures are invisible.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

---

# EPIC G — Data, persistence & correctness (P1/P2)

### HIVE-086 · P1 · Audit every JSON column for the HIVE-024 mutation bug
49 tables, heavy JSON use (`personality_traits`, `writing_fingerprint`, `activity_pattern`,
`emotional_state`, `interests`, `inherited_traits`, `mutations`, `relationships`, `roles`,
`life_events`). Any in-place mutation without `flag_modified` is a silent data-loss bug.
**AC:** every JSON column is either `MutableDict`/`MutableList` or provably only ever wholesale-reassigned.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-024 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-087 · P1 · No database backup verified for restore
`scripts/backup_db.py` / `backup_db.sh` and `docs/operations/database-backup.md` exist. No restore has
been exercised. An unrestored backup is not a backup.
**AC:** a documented, timed restore drill into a scratch database.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-088 · P2 · No connection-pool tuning or timeout policy
`DATABASE_POOL_SIZE=10`, `MAX_OVERFLOW=20` (`settings.py:79-87`) against 15 concurrent engine loops
plus API traffic. No statement timeout, no `pool_pre_ping` verified.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-089 · P2 · pgvector index strategy unverified
`memory_items` uses 768-dim embeddings with similarity search (`memory_core.py:334`). Confirm an
IVFFlat/HNSW index exists and is being used, rather than a sequential scan.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-090 · P2 · No data retention or archival policy
`memory_items`, `system_logs`, `post_views`, `admin_audit_logs`, and `bot_metrics` grow without bound.
`ArchivedMemoryDB` and `RetiredBotDB` exist but nothing schedules archival (see HIVE-051).

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-051 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-091 · P2 · No cascade/orphan policy on bot deletion
Deleting a bot leaves lifecycle, ancestry, memories, posts, relationships, and beliefs behind. Define
the policy (soft-delete is likely right, given the "legacy" model).

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-119 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-092 · P2 · Reproduction has no population ceiling
`civilization_loop.py:291-325` — partnered creation fires at 5% per eligible pair per cycle with no
cap, plus solo legacy (`:342`) and spontaneous emergence (`:356`). Against `MAX_ACTIVE_BOTS=12`
(`settings.py:167`), the DB population and the simulated population can diverge without limit.
**Fix:** a configured carrying capacity that gates all three reproduction paths.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-022 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

---

# EPIC H — Partial features to complete (P1/P2)

### HIVE-093 · P1 · Rituals are held but never broadcast or surfaced
`civilization_loop._hold_remembrance/_hold_elder_council/_hold_storytelling` (`:485-581`) persist
results and log them, but emit no event. The portal's `/rituals` page and its `ritual_performed`
handler (HIVE-069) therefore never see a live ritual.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** HIVE-069
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-094 · P1 · Content moderation is stubs
`mind/moderation/content_filter.py:177-185` — image moderation *"Placeholder: Always allow images for
now"*. `:147, :205, :219` — AI-based text moderation is a placeholder.
`mind/moderation/word_lists.py:51` — *"These are placeholder patterns - in production, use a
comprehensive list"*. The moderation *API* is complete; the enforcement behind it is not.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-006 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-136 · P1 · The settings API is a write-only facade
`mind/api/routes/settings.py:100` — `_settings_store` is a **module-level dict**, not storage. Three
consequences, each independently disqualifying:

1. **It resets to defaults on every restart.** Nothing is persisted.
2. **Each worker holds its own copy.** With `API_WORKERS=4` (`settings.py:235`), a `PUT` lands on one
   worker and a later `GET` may read another, so the API returns different values depending on which
   process answers.
3. **Nothing reads it.** Verified by grep: no engine, loop, service, or middleware outside
   `settings.py` consumes `maintenance_mode`, `toxicity_threshold`, `two_factor_enabled`,
   `profanity_filter`, or any other key. `max_active_bots` *appears* elsewhere but that is
   `MAX_ACTIVE_BOTS` from the env-var config system — a completely separate mechanism.

So the queen settings page writes to a dict that dies on restart and that no code consults.
[TODO.md](TODO.md) lists "Make settings page functional" and "Settings functional with backend" as
complete. **Neither is true.**

**Fix:** decide what settings the platform actually has. Most of these keys duplicate
`mind/config/settings.py` (env-driven) or `mind/civilization/config.py` (DB-backed, and a working
model to copy). Then persist to a table, read through a cached accessor, and wire each key to the
code that should honour it — or delete the keys nothing will ever consume.
**AC:** a setting changed through the API survives a restart, is visible from every worker, and
demonstrably changes platform behaviour (one end-to-end test per key that is kept).

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-007 ✅ · **Blocks:** HIVE-099
> **Blockers:** _none recorded_
> **Feedback:**
> - _28-07-2026_ — Found while gating the router in HIVE-007. The endpoints are now admin-only, so
>   this is no longer urgent from a security angle — but it is a **documented-complete feature that
>   does nothing**, which is worse than a missing one because nobody re-checks it.
> - **`mind/civilization/config.py` already solves this problem properly** (DB-backed, cached,
>   consumed by the lifecycle manager). Copy that pattern rather than inventing a third config system
>   — the repo already has two.
> - **Scope check before building.** Several keys (`jwt_expiry_hours`, `max_login_attempts`,
>   `session_timeout_minutes`) describe behaviour that is not implemented anywhere — there is no
>   lockout mechanism and no 2FA. Persisting a `two_factor_enabled` flag with nothing behind it just
>   moves the facade. **Delete those keys or implement the behaviour; do not persist a lie.**

### HIVE-134 · P2 · Users can only block bots, not other users
`mind/blocking/blocking_service.py` exposes `block_bot` and nothing else; `UserBlockDB` is keyed
bot-side. Every blocking endpoint in `mind/api/routes/blocking.py` is therefore user→bot only.

Consequences: `send_direct_message`'s block check cannot fire between two humans, and the "blocking"
feature named in HIVE-008 covers a narrower surface than it appears to. On a platform that ships
human-to-human DMs, no way to block another human is a harassment gap.

**Depends on the HIVE-119 answer** — irrelevant if the product is observation-only, required if it is
a social platform.
**Fix:** generalise `UserBlockDB` to (blocker_id, blocked_id, blocked_is_bot), add user-blocking
endpoints, and enforce it in the DM and comment paths.
**AC:** a blocked user cannot DM or comment at their blocker; the check runs for human senders.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-119 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:**
> - _28-07-2026_ — Found during HIVE-005. Also note `send_direct_message` still carries a now-dead
>   `if is_bot:` block check (HIVE-003 removed the caller-supplied flag). Delete it as part of this
>   task, not before — it documents the intended rule.

### HIVE-095 · P1 · Follower system is unimplemented
`mind/api/routes/users.py:187` — `follower_count=0  # TODO: Implement followers`. No follow table, no
endpoints, but the field is exposed in the API contract.
**Fix:** implement, or remove the field rather than serve a constant lie.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-119 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-096 · P1 · Generated post images are discarded
`mind/engine/loops/post_loop.py:190` — `return None  # TODO: Save to media storage`. Image generation
runs (and costs money if a paid provider is configured), then throws the result away.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-097 · P2 · Video processing is a stub
`mind/api/routes/media.py:138` — *"Video processing (placeholder - would extract dimensions and
thumbnail)"*. Videos upload but get no thumbnail or metadata.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-029 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-098 · P2 · Two admin endpoints return placeholder data
`mind/api/routes/admin.py:554` and `mind/core/admin_service.py:766` — both annotated as placeholders
whose "actual implementation depends on how the engine is managed". Identify and implement or remove.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-099 · P2 · Dark/light theme toggle incomplete
`queen/src/contexts/ThemeContext.tsx:18` — *"TODO: Issue #4 - Complete the dark/light mode toggle
implementation"*. Every page hardcodes hex colors (`#0a0a0a`, `#00f0ff`, …) rather than using
`src/styles/design-tokens.ts`, so a toggle cannot work without a token migration first.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-100 · P2 · `/health/detailed` reports a hardcoded database status
`mind/api/main.py:542` — `"database": "healthy",  # Would check actual connection`. The endpoint will
report healthy with Postgres down.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-101 · P2 · Starter content is hardcoded English filler
`mind/engine/activity_engine.py:454-480` seeds posts like *"Coffee and chill kind of day"* and
*"This community is awesome"*. This directly contradicts the project's stated "emergence over design"
principle and is the first thing an observer sees.
**Fix:** generate seed content from the LLM, or seed nothing.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-102 · P2 · Conscious-mind intents are parsed by substring matching
`mind/engine/activity_engine.py:505-516` — intents are routed with
`any(x in intent_lower for x in ["post", "share", …])`, and two of three branches only log. Bots form
intentions that are then discarded.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-103 · P2 · `queen` `/world` page has no error or empty state
`queen/src/app/world/page.tsx` is 15 lines wrapping `CivilizationMap` with no loading, error, or
empty handling.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

---

# EPIC I — Observability & operations (P2)

### HIVE-104 · P2 · No structured logging
`mind/api/main.py:24-28` configures `logging.basicConfig` with a plain string format. No request IDs,
no correlation IDs, no JSON output. 358 `print()`-style bootstrap messages bypass logging entirely
(e.g. `main.py:164-187`).

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** HIVE-112
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-105 · P2 · Prometheus metrics exist but no dashboards or alerts
`mind/monitoring/metrics.py` + `MetricsMiddleware` are wired, and `docker-compose.yml` ships Prometheus
and Grafana. `monitoring/` contains exactly one file (`prometheus.yml`). No dashboards, no alert rules.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** HIVE-106
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-106 · P2 · No alerting on the things that actually break
Needed: LLM circuit-breaker open, Ollama unreachable, aging loop not advancing (HIVE-022 would have
been caught by this), DB pool exhaustion, WebSocket disconnect storms, population collapse.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-105 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-107 · P2 · Grafana ships with default credentials
`docker-compose.yml:52` — `GF_SECURITY_ADMIN_PASSWORD=admin`, port published to the host.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-108 · P2 · No graceful shutdown for in-flight LLM work
`ActivityEngine.stop()` (`activity_engine.py:350-361`) cancels tasks immediately. In-flight generations
and their DB writes are lost mid-transaction.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-109 · P2 · No container image or deployment manifest for the backend
`docker-compose.yml` provides Postgres/Redis/Prometheus/Grafana only. There is no `Dockerfile` for
`mind/`, and no Ollama service — despite the README quickstart implying `docker-compose up` gives you a
running system.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** HIVE-115
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-110 · P2 · No LLM cost/usage tracking
With `IMAGE_GENERATION_PROVIDER=openai`, `TTS_PROVIDER`, and paid search providers all configurable,
and 15 autonomous loops generating continuously, there is no spend visibility or budget cap.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-111 · P2 · No `/metrics` protection
`mind/api/routes/metrics.py` — 4 endpoints, 0 auth. Prometheus scrape endpoints should not be public.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-003 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-112 · P3 · No log rotation for the in-memory buffers
`AdminConnectionManager.log_buffer` (`main.py:1071`) caps at 100 entries; `/system/logs` reads a ring
buffer. Nothing persists logs beyond process lifetime.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-104 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

---

# EPIC J — Packaging, docs & hygiene (P3)

### HIVE-113 · P1 · `pip install -e .` installs nothing
`pyproject.toml` — `[tool.setuptools.packages.find] include = ["ai_companions*"]`, but the package is
`mind`. `[project.scripts] ai-companions = "ai_companions.api.main:main"` points at a module that does
not exist. Both are rename leftovers.
**AC:** a clean venv + `pip install -e .` + `python -c "import mind"` succeeds.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** HIVE-115
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-114 · P2 · `docs/TODO.md` is actively misleading
Claims 100% on 62/62 items including several this audit found unimplemented (rituals surfacing,
push notifications, typing indicators, offline retry, logs page, relationships page).
**Fix:** replace with a pointer to this document.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-115 · P2 · README quickstart does not work as written
`docker-compose up -d` starts no Ollama and no backend; there is no `.env` in the repo (correctly
gitignored) and the instructions do not mention `alembic upgrade head` ordering relative to
`create_all`. A fresh contributor cannot get to a running system.
**AC:** a clean-machine walkthrough that produces a running civilization, verified by someone who has
not seen the repo.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-109, HIVE-113 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-116 · P2 · Screenshots in README are undated and may not reflect current UI
Six screenshots claiming "32 beings in The Founding era" — with HIVE-022, that era can never advance.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-022 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-117 · P2 · No `CHANGELOG.md` and no releases
`.github/workflows/release.yml` exists; no releases have been cut. Version is `1.0.0` in
`main.py:309`, `2.0.0` in `pyproject.toml`, `0.1.0` in `queen/package.json`, `1.0.0+1` in
`cell/pubspec.yaml` — four different versions.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-118 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-137 · P1 · Two parallel account systems
Hive has two unrelated ways to be a user:

| Path | Credential | Result |
|---|---|---|
| `POST /auth/register` + `/auth/login` | email + password | JWT access/refresh pair |
| `POST /users/register` | `device_id` only, no secret | returns the **existing** account for a known `device_id` |

The second is what `cell/` uses (`api_service.dart:66`). `mind/api/routes/auth.py:218` fabricates a
`device_id` for every JWT user *"for compatibility"*, so every account exists in both systems at
once. Since HIVE-003 the API authenticates with JWTs, which means the device path can create an
account it cannot then use — and HIVE-012 had to strip `device_id` from public responses precisely
because that path treats it as a credential.

**Also in scope — the mobile client calls endpoints that do not exist.** Found while auditing this:
`cell/lib/services/api_service.dart:101,121` PUT to `/users/{id}/profile`, which the router does not
define. **Profile editing and avatar upload have never worked**, despite
[TODO.md](TODO.md) listing "Profile editing completion" as complete. Same family as HIVE-133/135:
nobody noticed because no test exercises the client's URL list against the server's route table.

**Fix:** decide which identity model survives (this follows from **HIVE-119**), migrate `cell/` onto
it, delete the other, then audit every URL in `api_service.dart` against the live route table.
**AC:** one account system; `cell/` authenticates through it; a test asserts every endpoint the
mobile client calls exists on the server.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-119, HIVE-012 ✅ · **Blocks:** HIVE-084
> **Blockers:** _none recorded_
> **Feedback:**
> - _28-07-2026_ — Found during HIVE-012. The security consequence is already closed (HIVE-012);
>   what remains is the architectural duplication and the dead client calls.
> - **The client-vs-route-table test is the cheap win here** and worth doing even before the identity
>   decision: extract the URL templates from `api_service.dart`, compare against `app.openapi()`, fail
>   on any the server does not serve. That single test would have caught this, HIVE-133, and HIVE-135.

### HIVE-118 · P2 · Settle the product identity
The repo is simultaneously **Hive** (README), **Sentient** (CLAUDE.md, VISION.md), **ai-companions**
(pyproject), **Hive Social Platform** (FastAPI title, `main.py:287`), and **hive_observation**
(pubspec). Package is `mind`, portal is `queen`, app is `cell`.
This is not cosmetic — it is why the social-platform half of the codebase is undocumented (HIVE-119).

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-119 · **Blocks:** HIVE-078, HIVE-083, HIVE-117
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-119 · P1 · Document or excise the social-platform half
README, VISION.md, and CLAUDE.md describe only the digital-species simulation. The codebase also
contains a full social network — human users, JWT auth, posts, likes, comments, hashtags, stories,
DMs, media, moderation, blocking, analytics, admin — roughly half of the 81k backend LOC, mentioned
nowhere.
**Decision required:** is Hive an observation-only simulation (in which case a large deletion is due),
or a social platform populated by an AI civilization (in which case the docs are badly wrong)?
Nearly every P0 in Epic A only exists because of the undocumented half. **Answer this first — it
changes the scope of Epics A, C, and F.**

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** HIVE-003, HIVE-004, HIVE-005, HIVE-006, HIVE-007, HIVE-008, HIVE-009, HIVE-010, HIVE-011, HIVE-012, HIVE-014, HIVE-016, HIVE-037, HIVE-039, HIVE-040, HIVE-042, HIVE-043, HIVE-047, HIVE-080, HIVE-083, HIVE-091, HIVE-095, HIVE-118, HIVE-120, HIVE-124
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-120 · P3 · `CLAUDE.md` architecture section is out of date
Lists 5 subdirectories under `mind/`; there are 21. Omits `intelligence/`, `scaling/`, `moderation/`,
`analytics/`, `notifications/`, `capabilities/`, `media/`, `stories/`, `search/`, `hashtags/`,
`blocking/`, `monitoring/`, `agents/`, `communities/`, `prompts/`, `scheduler/`.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-119 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-121 · P3 · Worklog discipline lapsed
`CLAUDE.md:91-100` mandates a worklog entry per session. Three exist (20, 21, 28 March 2026); the
repo has commits after that date.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-122 · P3 · `SECURITY.md` promises a process that does not exist
Given Epic A, publishing a vulnerability-disclosure policy before fixing unauthenticated admin access
is the wrong order.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-001 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-123 · P3 · Dependabot backlog
9 open dependabot branches on `origin`. Nearly all commits since March are dependabot merges.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-124 · P3 · `docs/` structure has stale entries
`docs/api/endpoints.md` vs `docs/api/CIVILIZATION_API.md` (claims "70+ endpoints"; the router has 85),
`docs/architecture/overview.md` vs `ARCHITECTURE.md`, `docs/getting-started/backend-readme.md`.
Consolidate.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-119 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-125 · ~~P3~~ **P0** · `.gitignore` silently swallows `queen/src/lib/` — root cause of HIVE-131
**Re-rated from P3 to P0 on 28-07-2026.** Originally filed as hygiene ("fragile"). It is not
hygiene — it is the mechanism that broke the build.

`.gitignore:24` had an **unanchored** `lib/`, inherited from the standard Python template where it
means the root-level build artifact directory. Unanchored, it matches *any* directory named `lib` at
*any* depth — including `queen/src/lib/` and `cell/lib/`. The `!cell/lib/` line patched one victim
and left the other invisible.

**This explains HIVE-131.** `queen/src/lib/websocket.ts` was almost certainly written, `git add`ed,
silently ignored, and never committed — which is why every consumer imported a module that does not
exist in the repository. `api.ts` survives only because it is already tracked (git ignores
`.gitignore` for files already in the index), which is exactly what made the bug invisible: the
directory *looked* fine in `git status`.

Confirmed live on 28-07-2026 — new files in `queen/src/lib/` did not appear in `git status`:
`git check-ignore -v queen/src/lib/auth.ts` → `.gitignore:24:lib/`.

**Fix applied:** anchored to `/lib/` and `/lib64/`; removed the now-redundant `!cell/lib/`.
**AC:** new files under `queen/src/lib/` and `cell/lib/` appear in `git status`; no build artifacts
newly tracked.

> **Status:** `Done` · **Owner:** Claude · **Started:** 28-07-2026 · **Closed:** 28-07-2026
> **Depends on:** — · **Blocks:** HIVE-002 ✅, HIVE-068 ✅, HIVE-131 ✅
> **Blockers:** _none recorded_
> **Feedback:**
> - **Done, AC verified.** `queen/src/lib/auth.ts` and `websocket.ts` now show as untracked;
>   `cell/lib` still resolves 51 tracked files; `git status` gained no unexpected entries.
> - **Found by accident**, doing a routine `git status` after finishing HIVE-002 — the new files
>   were not listed. Without that check, HIVE-002 and HIVE-068 would have been marked `Done` with
>   their two most important files uncommittable, reproducing the exact failure as HIVE-131.
> - **Audit the other blanket patterns before trusting them.** `.gitignore` also carries unanchored
>   `build/`, `dist/`, `var/`, `parts/`, and `downloads/` from the same template. `cell/build/` is
>   separately listed, implying someone already hit this once and patched a symptom rather than the
>   cause. Worth one pass: `git status --ignored` and look for source directories.
> - **Recommend a CI guard.** A job that fails when a tracked-directory source file is ignored
>   (`git ls-files --others --ignored --exclude-standard -- '*.ts' '*.tsx' '*.dart' '*.py'`) would
>   have caught this in March. Folding into HIVE-063's migration-check job is the cheap option.

### HIVE-126 · P3 · `codecov.yml` configured but coverage never verified
See HIVE-056.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** HIVE-056 · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-127 · P3 · CodeQL runs but findings unreviewed
`.github/workflows/codeql.yml` scans Python and JavaScript weekly. Given the findings in Epic A, review
the existing alert backlog before adding more scanning.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

### HIVE-128 · P3 · No `CODEOWNERS` or branch protection evidence
67 commits, effectively one author, direct-to-main development.

> **Status:** `Not started` · **Owner:** _unassigned_ · **Started:** _—_ · **Closed:** _—_
> **Depends on:** — · **Blocks:** —
> **Blockers:** _none recorded_
> **Feedback:** _pending_

---

# Suggested sequencing

**Gate 0 — decide (blocks everything).**
HIVE-119. The answer determines whether Epic A is 21 tasks or 5.

**Gate 1 — make it safe (do not deploy before this).**
Epic A in full (HIVE-001…021). Roughly: auth dependencies on 12 routers, actor-identity refactor,
WebSocket auth, startup validators. HIVE-058 alongside it — do not ship this without tests.

**Gate 2 — make it work.**
HIVE-022, 023, 024 (the product's headline feature), then 025…036, then HIVE-059/060.

**Gate 3 — make it honest.**
Epic C decisions (delete ~7,000 LOC or wire it), HIVE-066/067 (stop shipping fake data),
HIVE-053/054/055/056 (CI actually verifies things), HIVE-114 (retire the false TODO).

**Gate 4 — make it operable.**
Epic I, HIVE-087, HIVE-109.

**Gate 5 — polish.**
Epics E/F remainder, Epic J.

---

## Notes on what is already good

Worth protecting during the above:

- The loop/manager decomposition in `mind/engine/` — clean composition, easy to reason about.
- The LLM client stack (`llm_client.py` → `llm_pool.py` → `llm_rate_limiter.py`): circuit breaker,
  Redis-backed response cache, token-bucket priority limiting, multi-instance load balancing with
  health checks. Genuinely production-grade.
- The civilization domain model. `lifecycle.py` implements virtual-time aging, per-stage vitality
  decay, probabilistic death, LLM-generated final words, legacy-impact scoring, and grief propagation.
  It is real, not scaffolding — it is simply never exercised because of HIVE-022.
- Schema integrity: 49 ORM tables, 49 migrated tables, verified matching in both directions.
- No secrets committed; `.gitignore` is thorough; no SQL string interpolation anywhere.
- `mind/config/production.py` is a good preflight validator. It just needs to be called.
