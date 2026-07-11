# The agents, one by one

A per-agent architecture reference for the fleet — inputs, pipeline, where
Claude is (and isn't) used, state, output shape, and the design decisions
behind each one.

> This is the **agent-level** companion to **[ARCHITECTURE.md](ARCHITECTURE.md)**,
> which covers the shared system: the Cloudflare Worker clock, the GitHub
> Actions execution model, `agentlib`, the dedupe/backup/alert reliability
> layer, and the secrets model. Every agent below inherits that skeleton —
> this doc only describes what's *specific* to each one.

**Legend** — 🧠 calls Claude · ⚙️ deterministic (no model) · 🧠🧠 two-stage /
multi-call. Times are IST.

---

## 🌅 Morning cloud agents

### weather-report
- **Purpose:** Sends one deterministic morning Telegram forecast for 24 major cities across the US, Europe, India, Singapore and China, grouped by region.
- **Schedule (IST):** 06:00 sharp via fleet-scheduler; backup crons 06:00/07:00 (`30 0 * * *` / `30 1 * * *` UTC).
- **Inputs / data sources:** Open-Meteo forecast API (`api.open-meteo.com/v1/forecast`, no key) and Open-Meteo air-quality API (`air-quality-api.open-meteo.com/v1/air-quality`, US AQI). Cities are hardcoded coordinate tuples in the `REGIONS` dict.
- **Pipeline:**
  1. Flatten `REGIONS` into a 24-city list.
  2. `fetch_batch` — one batched GET with comma-separated lat/lon lists and `timezone=auto`, 2 forecast days; a location-count mismatch raises.
  3. On batch failure, fall back to isolated per-city GETs (`weather_line`); either path degrades a single bad city to one "unavailable" line.
  4. `format_line` renders each city: picks today vs. tomorrow by `EVENING_CUTOFF_HOUR` (15:00 local), maps WMO code to words, gates feels-like/rain%/wind by thresholds, flags severe codes.
  5. `fetch_aqi` — one batched air-quality call; appends AQI + band word to Indian city lines only (drops silently on any failure).
  6. Group lines under region headers, hoist severe cities into a top ⚠ Watch block, prepend date header, `send_telegram`.
- **LLM role:** ⚙️ deterministic — no model call; all formatting and severe-weather selection is rule-based.
- **State / memory:** none.
- **Output format:** Date header, then an optional ⚠ Watch block listing severe-weather cities, then per-region sections each with a header and one line per city. Always sends (never silent); broken cities show an inline "unavailable" line.
- **Notable design decisions:**
  - Single batched API call with per-city fallback so one bad response can't blank the whole report.
  - Notability gates keep calm days to one short line; extras appended only when they clear a threshold.
  - AQI is a best-effort enrichment for India only — any failure drops the enrichment, never the report.
  - Per-location timezone drives show-tomorrow logic past 3 PM local so lines never show a nearly-finished day.
- **Key dependencies:** `requests`, `python-dotenv`.

### mail-digest
- **Purpose:** The inbox guardian — a morning digest of the last 24h of Gmail (VIP block, numbered NEEDS ACTION deadline-first, CARRIED unanswered actions with ages, a 📅 deadline ledger, SECURITY alerts, FYI, still-unread pile, deterministic noise counts) plus a 19:00 evening sweep that is silent unless something genuinely can't wait until morning. Sundays add a 📊 week scorecard, VIP suggestions mined from sent mail, and unsubscribe candidates.
- **Schedule (IST):** 06:00 primary, 07:00 backup (`30 0 * * *` / `30 1 * * *` UTC) + the 19:00 sweep; 3-hour dedupe guard window pairs each backup with its edition.
- **Inputs / data sources:** Gmail API (read-only OAuth; SENT label checked to verify replies), the Anthropic API, the `VIP_SENDERS` secret, and four memories in `state/`: noise trends, weekly stats, the carried-action ledger, and the deadline ledger.
- **Pipeline:** anchored 6AM→6AM window → fetch + thread-group → **1 Claude call** classifies and extracts actions/deadlines into a `===STATE===` JSON tail → deterministic blocks assembled around it (VIP guaranteed by code, CARRIED verified via thread_replied(), Ahead ledger date-validated, hallucinated Gmail links stripped) → send → state saved after the send.
- **LLM role:** 🧠 1 call — classification and action extraction; VIP surfacing, carry-over verification, deadline validation and link validity are code-enforced.
- **State / memory:** `state/noise.json`, `stats.json`, `actions.json`, `deadlines.json` — committed back by the workflow.
- **Output format:** Header (window + counts), 📅 Ahead, 🔔 VIP, ⚡ NEEDS ACTION (numbered), 🔁 CARRIED (with ages), 🚨 SECURITY (omitted when none), 📥 FYI, ⏳ STILL UNREAD, 🗑 noise line; Sunday extras. Evening sweep: silent unless can't-wait.
- **Notable design decisions:** anchored windows (backup covers the identical day); the carry-over ledger checks the SENT label so "replied" is a fact, not a guess; deadlines must parse as real dates to enter the ledger.
- **Key dependencies:** `google-api-python-client`, `google-auth`, `google-auth-oauthlib`, `anthropic`, `requests`, `python-dotenv`.

### news-briefing
- **Purpose:** Two Telegram editions a day — a full morning briefing (seven sections: India, Indian politics, business, Hyderabad incl. Telugu media, US politics & immigration with visa/H-1B/corridor stories always kept, non-politics US, world) and a tight 21:00 evening wrap of only what broke after the morning, article-grounded and personalized by a watchlist.
- **Schedule (IST):** 06:00 sharp and 21:00 via fleet-scheduler; backup crons 06:00/07:00/21:00/22:00 UTC-shifted (`30 0` / `30 1` / `30 15` / `30 16 * * *`), deduped by a 3-hour guard window.
- **Inputs / data sources:** 41 verified RSS feeds via `feedparser` (each probed for reachability + freshness before inclusion; ~20 rejects documented in code), the selected stories' own article pages, the Anthropic API, `state/seen.json` + `state/briefed.json`, and the `NEWS_WATCH` secret (comma-separated personal topics).
- **Pipeline:**
  1. `edition` — morning (full caps, 24h lookback) or evening (tight caps, 16h) by IST hour; a quiet evening stays silent.
  2. `gather_headlines` — up to 6 fresh entries per feed; dead feeds skipped, stale and already-seen links dropped; watchlist matches 👁-flagged deterministically.
  3. `select_stories` — **Claude call 1** (haiku): picks story indices per section under editorial rules (one story one section, outlet variety, corroboration = importance, politics = governance substance, skip cinema filler); skipped 👁 stories are forced back in by code.
  4. `fetch_article` — full boilerplate-stripped text (3k chars) for just the selected stories.
  5. `write_briefing` — **Claude call 2** (sonnet): 2-3 substantive sentences per bullet from real article text, Telugu sources rendered in English, plus a state tail naming each bullet's story key and the Top story's link.
  6. `validate_links` — strip any URL (incl. the top link) not in the gathered set; `fetch_og_image` + `send_photo` then send the Top story as a captioned photo front page (best-effort).
  7. Sunday mornings: `week_in_review` — **Claude call 3** traces the week's story arcs from the 7-day briefed memory.
  8. `send_telegram`, then record seen links and briefed keys (after the send).
- **LLM role:** 🧠 2 Claude calls (3 on Sundays) — cheap model selects, strong model writes from fetched articles; freshness, seen-dedupe, watchlist enforcement and link validation are deterministic.
- **State / memory:** `state/seen.json` (3 days — briefed once, and the evening wrap is new-only by construction) and `state/briefed.json` (7 days of what the bullets said — developments framed as developments, Sunday arcs), both committed back by the workflow.
- **Output format:** Header (edition + candidate/feed counts), photo front page when the Top story carries an og:image, 🗞 Top line, then 📰 INDIA / 🏛 POLITICS / 💼 BUSINESS / 📍 HYDERABAD / 🗽 US POLITICS & IMMIGRATION / 🇺🇸 US / 🌍 WORLD bullets (👁-prefixed for watchlist hits), each with its validated source link; 🗓 THE WEEK on Sundays.
- **Notable design decisions:**
  - Two-stage select/fetch/write: bullets carry numbers, names and consequences because they're written from articles, not headlines.
  - The watchlist guarantee is code-enforced (same pattern as mail-digest's VIP block), not just prompted.
  - The evening wrap exists because India's news cycle happens 9:00–21:00; the seen-memory makes it non-overlapping by construction.
  - Hallucinated links replaced with `[link removed: not in source feeds]`; the photo and week blocks are enrichments that can never sink the briefing.
  - Tech and cricket deliberately excluded — handled by separate agents; politics is split by country (🏛 India, 🗽 US), with immigration guaranteed a slot in 🗽 by selector rule since no keyless immigration-only feed exists.
- **Key dependencies:** `feedparser`, `anthropic`, `requests`, `python-dotenv`.

### cricket-scores
- **Purpose:** Filters the Cricinfo live-scores board down to matches worth attention (India at any level, majors' internationals — men's and women's equally — IPL/WPL) across three editions: morning overnight matches, a lunch edition that exists only on India match days, and the day's results in the evening. Sunday evenings add 📊 SERIES STATS — leaderboards computed deterministically from Cricsheet's open ball-by-ball archives.
- **Schedule (IST):** 06:00 (backup 07:00), 13:37 lunch (deterministically silent unless an India side is on the board), 21:47 evening (backup 22:47); 3-hour dedupe guard window.
- **Inputs / data sources:** Cricinfo live-scores RSS (up to 25 score lines) and, Sunday evenings, Cricsheet's 30-day ball-by-ball JSON zip (keyless open data, ~300 matches).
- **Pipeline:** `gather_scores()` three-way contract (None = dead feed → raise; [] = quiet board → silent; lines) → lunch gate `india_on_board()` (deterministic substring check, no model call on ordinary lunchtimes) → **1 Claude call** sections the kept lines verbatim into 🔴 LIVE / ✅ RESULTS / 📅 UPCOMING with 🇮🇳/🚺 flags → Sundays `series_stats()` computes top run-getters/wicket-takers per tracked series in pure Python (run-outs not credited to bowlers) → send or stay silent.
- **LLM role:** 🧠 1 call as a filter/sectioner — score numbers are always copied verbatim; the stats block is entirely deterministic.
- **State / memory:** none.
- **Output format:** `🏏 Cricket — <date> (<edition>)`, sectioned lines, 🇮🇳 first, women's matches 🚺-tagged; Sunday evenings append the 📊 stats block. Silent when nothing notable.
- **Notable design decisions:** the lunch edition costs nothing on non-India days (deterministic gate before any model call); Cricsheet gives real leaderboards with no stats API and no hallucination surface; every keyless live-data API was probed and found bot-walled — the RSS stays the spine.
- **Key dependencies:** `feedparser`, `anthropic`, `requests`, `python-dotenv`.

### tech-news
- **Purpose:** The fleet's flagship — two Telegram editions a day covering the full tech landscape in nine sections (AI with primary sources, data engineering/science/analytics, cloud & infra, operating systems (Windows/Linux/macOS), software & dev, hardware, industry, India tech, security), every bullet carrying a '↳' background-context line plus deterministic blocks: HN TOP (the community's actual front page), PATCH NOW (CISA's actively-exploited CVE catalog) and a Saturday WEEK IN TECH; the five core topics run up to 10 stories deep.
- **Schedule (IST):** 06:00 full briefing and 19:15 evening wrap via fleet-scheduler; backup crons 07:00/20:15; 3-hour dedupe guard window pairs each backup with its own edition.
- **Inputs / data sources:** 45 verified RSS feeds (probed for reachability + freshness; rejects documented in code — data-vendor engineering blogs deliberately left to the eng-blogs agent), plus three structured APIs: HN Algolia (top stories + points/comments enrichment, one call for both), and the CISA Known Exploited Vulnerabilities JSON. The `TECH_WATCH` secret carries a personal watchlist. State: `seen.json`, `briefed.json`, `extras.json`.
- **Pipeline:**
  1. `edition()` — morning (full caps, 24h lookback) or evening (tight caps, 14h); a quiet evening is silent unless a new exploited CVE fires.
  2. `hn_window()` — one Algolia call: 🔥 HN TOP (top-5 by points, 100-point floor) + a title→(points, comments) map enriching HN entries in the dev section.
  3. `gather_stories()` — fresh, unseen, per-feed try/except; watchlist matches 👁-flagged.
  4. `kev_block()` — deterministic: KEV entries added in the last 7 days not yet surfaced, capped 5, with NVD links + patch-due dates; runs in BOTH editions.
  5. `select_stories()` — **Claude call 1** (haiku) picks per-category indices under editorial rules; skipped 👁 stories forced back in by code.
  6. `fetch_article()` + `write_briefing()` — **Claude call 2** (sonnet) writes bullets from real article text (version numbers, benchmarks, consequences) with a `===STATE===` tail (story keys + top link).
  7. `validate_links()`, then deterministic blocks appended (their URLs are code-fetched).
  8. Saturday: `week_in_review()` — **Claude call 3** traces the week's arcs from the briefed memory.
  9. Photo front page (Top story og:image via `sendPhoto`, best-effort), `send_telegram`, then state saves.
- **LLM role:** 🧠 2 Claude calls (3 on Saturdays) — select + write; HN TOP, PATCH NOW and the watchlist guarantee are fully deterministic.
- **State / memory:** `seen.json` (3d — briefed once, evening wrap new-only by construction), `briefed.json` (7d — developments framed as developments, Saturday arcs), `extras.json` (KEV CVEs 90d, so the tripwire never repeats).
- **Output format:** Header (edition + candidate/feed counts), photo front page, 🗞 Top line, nine emoji sections (each bullet: facts + ↳ context + link) (👁-prefixed watchlist bullets, validated links), then 🔥 HN TOP / 🚨 PATCH NOW / 🗓 WEEK IN TECH as they apply.
- **Notable design decisions:**
  - Security accuracy is non-negotiable: PATCH NOW is code-built from CISA's official catalog — no model touches it, and it alone can break evening silence.
  - Two-stage article-grounded writing (the news-briefing engine) with per-edition caps.
  - HN significance measured (Algolia points), and the HN TOP block is verbatim — the model neither picks nor rewrites it.
  - Watchlist inclusion is code-enforced (mail-digest VIP pattern).
- **Key dependencies:** `feedparser`, `requests`, `anthropic`, `python-dotenv`.

### finance-tracker
- **Purpose:** Reads bank/UPI/card transaction notification emails from Gmail and reports money movement (in/out/net, categories, alerts) to Telegram on daily/weekly/monthly cadences.
- **Status:** ⚠️ Deployed but **blocked on Telegram bot creation** — `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` for `@jayanth_finance_bot` still need to be set via @BotFather before it can go live.
- **Schedule (IST):** Daily 06:00 IST (`30 0 * * *` UTC); backup 07:00 with dedupe guard. Extra sections trigger on Mondays (weekly + projection + expected subscriptions), the 15th (budget pace + projection, if `BUDGETS` set), and the 1st (monthly rollup + savings rate + 3-month category averages + detected subscriptions).
- **State / memory:** `state/ledger.json` — a year of transactions keyed by calendar day, committed back by the workflow. Daily runs record; weekly/monthly reports compute FROM the ledger (Gmail backfill for gap days); it powers the 🆕 first-time-payee flags, ⚠ duplicate-charge notes and the deterministic subscription detector (cadence 24–38d, amounts ±15%).
- **Inputs / data sources:** Gmail API (read-only OAuth via `token.json`/`credentials.json`, shared with mail-digest). Query built from optional `TXN_SENDERS` secret (sender fragments) or a broad `TXN_KEYWORDS` fallback. Config from env/secrets: `TXN_SENDERS`, `BUDGETS`, `LARGE_TXN_THRESHOLD`. Deterministic `MERCHANT_MAP` and `CATEGORIES` in code.
- **Pipeline:**
  1. Authenticate Gmail; compute calendar-aligned IST windows (daily always; weekly on Mon; month-to-date on 15th; monthly + prior month on 1st).
  2. `fetch_emails()` — Gmail search per window, fetch each message full, build body from snippet-first + decoded text/plain (or HTML with style/script stripped), capped at 700 chars.
  3. `extract_transactions()` — chunk emails (40/call); **N Claude calls** (one per 40-email chunk, `max_tokens=4000`) each returning a JSON array of `{date, direction, amount, merchant, description, category}`, filtering out OTPs/failed/promo/balance-only and using UPI P2M/P2A to separate spending from transfers.
  4. `categorize()` pins known merchants to fixed categories; `dedupe_txns()` collapses dual-alert duplicates (same date/direction/amount + shared word).
  5. `aggregate()` and other deterministic-Python analytics (`top_merchants`, `sparkline`, `daily_totals`) do all the maths; `format_report()` builds the plain-text report per period.
  6. Send per applicable window (daily/weekly silent when empty; monthly always sends; 15th pace check when budgets set).
- **LLM role:** 🧠🧠 Multiple Claude calls (one per 40-email chunk) — the model **only extracts and classifies** each transaction (amount/direction/merchant/category); all arithmetic and totals are done in Python by design ("a model that miscounts a total is worse than useless").
- **State / memory:** none persisted — windows are recomputed each run from Gmail.
- **Output format:** Plain-text reports. Daily: `💰 Finance — <date>` with In/Out/Net, large-txn alerts (`⚠️ Large (₹2000+)`), spending by category, income, full transaction list. Weekly adds daily-spend sparkline + top merchants. Monthly adds month-over-month change, per-category budget adherence, averages, biggest expense. 15th sends a `⏱ Budget pace` over/under-pace check. Silent on empty daily/weekly; monthly always sends.
- **Notable design decisions:**
  - Model-classifies / Python-sums split so totals never drift.
  - Calendar-anchored (not rolling) windows so the backup cron reports the exact same day with no gaps/overlap.
  - Snippet-first body assembly rescues bank alerts (e.g. Axis) that ship a blank text/plain part; dedupe guards against dual bank+wallet alerts.
  - Chunked extraction (40/call) keeps each JSON reply small and parseable in busy months; CI fails loudly on a missing/unrefreshable token.
- **Key dependencies:** `google-api-python-client`, `google-auth`, `google-auth-oauthlib`, `requests`, `python-dotenv`, `anthropic`.

### papers-digest
- **Purpose:** Weekly Saturday digest of the most relevant arXiv papers for a data & AI engineer — 10-12 picks from ~2,500 weekly submissions across seven categories, grouped under 🤖 AI & LLM / 👁 VISION / 🗄 DATA & SYSTEMS / 🔧 HARDWARE, each with two sentences + link, plus a 📌 SPOTLIGHT deep-dive on the week's #1 read from arXiv's HTML full text.
- **Schedule (IST):** Saturday 06:00 — dispatched on the minute; guarded GitHub cron backup an hour later (`30 1 * * 6` UTC).
- **Inputs / data sources:** arXiv Atom API (cs.LG, cs.CL, cs.AI, cs.CV, cs.DB, cs.DC, cs.AR — paginated to the 7-day cutoff, down-sampled evenly to 150/category), Hugging Face daily-papers API (community upvotes, merged deterministically: 🔥 flags + force-inclusion past the skim), the `PAPERS_INTERESTS` secret, `state/served.json`.
- **Pipeline:** fetch 7 categories → merge HF upvotes → **Claude call 1** (haiku) skims everything in chunks of 150 (recall-biased; unparseable chunk kept whole; 🔥 papers force-included) → **Claude call 2** (sonnet) reads full abstracts, writes the sectioned digest + a state tail of picked ids → link validator (URLs must be ones we handed the model) → **Claude call 3** SPOTLIGHT on the #1 pick from its HTML full text → send → served ids saved (90d, so revised resubmissions never repeat).
- **LLM role:** 🧠 2-3 calls — skim, rank/write, spotlight; pagination, down-sampling, HF signal, dedupe and link validation are deterministic.
- **State / memory:** `state/served.json` (picked arxiv ids, 90-day window), committed back by the workflow.
- **Notable design decisions:** weekly on purpose (daily arXiv is noise); section balance enforced so high-volume ML categories can't crowd out vision/data/hardware; the HF community signal can add papers but never remove them.
- **Key dependencies:** `feedparser`, `requests`, `anthropic`, `python-dotenv`.

### eng-blogs
- **Purpose:** My daily engineering reading list — the 10 best unread posts across 38 verified blogs (companies + the individuals every good engineer reads), ranked against my interests, each with a specific blurb, a deterministic read-time and its link. A post is served exactly once, ever.
- **Schedule (IST):** Daily 06:00 (`30 0 * * *` UTC), backup 07:00 with dedupe guard.
- **Inputs / data sources:** 38 probed RSS feeds, the posts' own pages (blurbs + read-times from real text), the `BLOG_INTERESTS` secret, `state/served.json`.
- **Pipeline:** gather the unserved POOL (newest first, feed-rot surfaced) → widen the candidate window (14→45→120→730d) until ≥30 candidates → **Claude call 1** (haiku) ranks vs interests (max 2/source, 1-2 wildcards, timeless-over-thin) with a deterministic top-up to exactly 10 → fetch each pick's full text → **Claude call 2** (sonnet) writes 2-3 specific sentences per pick (marker format, abstract fallback) → code composes the numbered message (headers, read-times at 230 wpm, links — the model never emits a URL) → send → record served links. Posts <48h old are archived to the `data/` JSONL corpus for the RAG project.
- **LLM role:** 🧠 2 calls — rank + annotate; pool mechanics, diversity cap, top-up, read-times, links and composition are deterministic.
- **State / memory:** `state/served.json` (800-day window — never re-serve) and `data/posts-YYYY-MM.jsonl` (full-text corpus), committed back by the workflow.
- **Notable design decisions:** the reading-pool replaces silent-if-quiet — engineering blogs are too low-volume for "10 fresh daily", so quiet weeks reach into the unread archive instead of padding; code-owned composition makes hallucinated links structurally impossible.
- **Key dependencies:** `feedparser`, `requests`, `anthropic`, `python-dotenv`.

### repo-review
- **Purpose:** Every evening it reviews the last 24h of pushes across all of the owner's GitHub repos and delivers a tagged code review, a rotating deep-dive spotlight, and (weekly) portfolio advice to Telegram. Deterministic blocks ride along: 🏅 hygiene score /7 and 📌 TODO/FIXME debt markers on the spotlight, 🔴 CI HEALTH for repos whose latest Actions run failed, Sunday 🗓 WEEK IN CODE (activity memory + open-PR sweep), and 📈 RISING REPOS (new repos crossing ★300 this week, shown once ever).
- **Schedule (IST):** 06:00 primary, 07:00 backup (`30 0 * * *` UTC) with a dedupe guard.
- **Inputs / data sources:** GitHub REST API via `REPOS_READ_TOKEN` (read-only PAT) — `/user/repos` (owner, non-fork, non-archived), per-repo `/commits`, the compare/commit diff endpoints (raw `application/vnd.github.diff`), recursive git tree + raw file contents for the spotlight; `state/findings.json` for memory.
- **Pipeline:**
  1. `my_repos()` lists owned, non-fork, non-archived repos.
  2. For each, `day_diff()` fetches last-24h commits (capped at 20) and ONE combined unified diff (parent-of-oldest…head), then `trim_diff()` cuts over-budget diffs at file boundaries, code first.
  3. `dedupe_changed()` collapses identical diffs pushed to many repos (fleet syncs) by SHA-256 hash.
  4. Pick the spotlight repo: manual override, else `day_of_year % len(repos)` over a name-sorted fixed rotation; `spotlight_source()` fetches up to 12 files / 30k chars (code before docs).
  5. **Claude call 1** — the day's diffs plus recent findings history, cheap model, skipped entirely on quiet days.
  6. **Claude call 2** — the spotlight deep read (+ portfolio inventory on curate days), stronger model.
  7. `split_state()` peels the `===STATE===` JSON memory tail off each reply; assemble header + both sections + any "could not check" footer; `send_telegram()`; then persist state last.
- **LLM role:** 🧠🧠 2 Claude calls. Call 1 (default `claude-haiku-4-5`) decides per-repo `[BUG]/[RISK]/[STYLE]` findings with fixes and acknowledges/escalates prior findings; Call 2 (default `claude-sonnet-5`) decides the spotlight verdict + improvements and, on Sundays, keep/finish/archive/delete portfolio calls. Models overridable via `REVIEW_MODEL_DAILY`/`REVIEW_MODEL_DEEP`.
- **State / memory:** `state/findings.json` (committed back by the workflow) — last 14 days of per-repo one-line findings plus latest spotlight notes per repo; fed into next day's prompts for follow-through. Unreadable/malformed state costs the memory, never the run.
- **Output format:** Header (date, repo-with-commits count, spotlight name, "weekly portfolio check" when curating), then `🔎 TODAY'S CHANGES` (2–4 tagged bullets per changed repo, or "no significant findings"), `💡 SPOTLIGHT: <repo>` (follow-through + 4–6 bullets + first change to make), optional `🗂 PORTFOLIO`, and a "⚠️ Could not check" footer on partial failures. Plain text, chunked to 4000 chars. Always sends — never silent.
- **Notable design decisions:**
  - Two-tier model split (cheap daily diff, strong deep read) to control cost; diff call skipped on quiet days.
  - Fixed name-sorted rotation so every repo gets a spotlight every N days regardless of activity.
  - Diff trimming and spotlight fetch prioritize real code over docs/config/lockfiles so the token budget is spent on code.
  - State persisted after the send, so a state failure never costs the message; per-repo try/except keeps one bad repo from killing the run.
- **Key dependencies:** `anthropic~=0.116`, `requests~=2.34`, `python-dotenv~=1.2`.

---

## 💻 Local systemd agents (run on the laptop)

### repo-audit
- **Purpose:** The on-demand account X-ray — press a button and every repo (~67, forks and archived included) gets triaged and the active ones deep-read, producing a report card each (score /10, blunt verdict, top 3 actions, tagged findings), a published dashboard, and a Telegram summary of what to act on first.
- **Schedule (IST):** none — on-demand via its one-button UI (repo-audit-ui.jayanthapalla.workers.dev: passphrase-gated run, live status, embedded dashboard) or workflow_dispatch/CLI; the fleet's first on-demand member: no cron, no scheduler entry, no watchdog line.
- **Inputs / data sources:** GitHub API via `REPOS_READ_TOKEN` (repo list, git trees, raw file contents, head SHAs) and the Anthropic API. Optional run inputs: `model` (default sonnet) and `limit` (first N repos, for testing).
- **Pipeline:**
  1. Phase 1, deterministic triage of every repo: hygiene /7 (README, description, license, tests, CI, .gitignore, topics), language, size, last-push age, open issues. Forks/archived stop here.
  2. Phase 2, one model call per active repo over budgeted source (12 files / 30k chars, code first) → strict-JSON report card; unparseable replies degrade honestly, never sink the run.
  3. Skip-unchanged: `state/audited.json` stores each repo's head SHA + review; re-audits only pay for repos that moved.
  4. Outputs: `report/report.json` (the future UI's API), `docs/index.html` (self-contained dark dashboard, worst-first, committed to the repo (own deployed site later — deliberately not the portfolio domain)), Telegram summary (grade, bucket counts, five worst with one action each).
- **LLM role:** 🧠 one call per changed repo — scoring and concrete actions; the hygiene checklist, buckets, sorting, HTML and summary are deterministic.
- **State / memory:** `state/audited.json` (SHA-keyed report cards), committed back by the workflow along with the report and dashboard — every audit is versioned in git history.
- **Notable design decisions:**
  - Separate from repo-review on purpose: the daily drip and the on-demand X-ray are different products (trigger, cadence, output, cost).
  - The dashboard is a committed self-contained file; phase two deploys it to its own separate site with an auth-gated run button (not the portfolio domain).
- **Key dependencies:** `requests`, `anthropic`, `python-dotenv`.

### housekeeper
- **Purpose:** Daily root-free laptop health check: disk usage, failed units, the fleet's own local timers, memory pressure/load, CPU temperature, kernel storage errors (the SMART substitute), Obsidian-vault git drift, repo drift across ~/agents + ~/Desktop, security updates, a 🧹 cleanup ledger (cache/trash/journald/autoremove), battery wear, history-powered trends (disk growth; reboot-required escalates after 7 ignored days), the 🐕 fleet watchdog (every cloud agent must show a successful run YESTERDAY — adopted from the retired daily-review agent) and vendored-agentlib drift. Always sends — ✅ one-liner when healthy, ⚠️ summarized action list when not.
- **Schedule (IST):** 06:00 daily (`OnCalendar=*-*-* 06:00:00`, `Persistent=true`, `RandomizedDelaySec=120`).
- **Execution:** Local **systemd** user timer on the laptop (not GitHub Actions).
- **Inputs / data sources:** System probes only — `shutil.disk_usage` on `/` and `/home`; `systemctl --failed` (system + user); Obsidian vault git state at `~/Desktop/Jayanth-Vault`; `apt list --upgradable`; `journalctl -p 3 -b`; `/var/run/reboot-required`; battery sysfs under `/sys/class/power_supply/BAT*`. Anthropic API only when there are issues to summarize.
- **Pipeline:**
  1. `check_disks` — per-mount usage, deduped by `st_dev`; ≥85% → issue.
  2. `check_failed_units` — failed system/user units minus known-benign (`casper-md5check`).
  3. `check_vault` — dirty-with-no-commit-for-14-days or unpushed commits → issue; missing remote → note.
  4. `check_updates` — ≥20 pending security updates → issue, else note.
  5. `check_battery` — wear <80% of design → note.
  6. `gather_context` — journal error count + reboot-required flag → notes.
  7. If no issues → send one-line all-clear (no Claude call). If issues → **one Claude call** turns findings into 2–3 terse action-first sentences; on API failure fall back to raw findings; `send_telegram()`.
- **LLM role:** 🧠 0 or 1 Claude call (default `claude-haiku-4-5`). Only invoked when issues exist, purely to phrase the alert humanely (lead with the action/command). The all-clear path and all detection logic are fully deterministic.
- **State / memory:** none.
- **Output format:** `🩺✅ Housekeeper` all-clear (one line + inline notes) or `🩺⚠️ Housekeeper` + summarized/raw findings. The ✅/⚠️ icon is the at-a-glance signal. Always sends (all-clear included, so absence itself signals the laptop was off).
- **Notable design decisions:**
  - Alert can never be lost to an API failure — falls back to raw findings when the model is unreachable (boot-time runs can beat Wi-Fi).
  - Every probe degrades gracefully: `sh()` returns `''` on any failure so one broken check never crashes the run.
  - Thresholds tuned to avoid noise (battery/journal/reboot are context notes, not alerts); healthy items stay silent.
  - `Persistent=true` catches up missed runs on next wake; `Restart=on-failure` handles boot-time network races.
- **Key dependencies:** `requests~=2.34`, `python-dotenv~=1.2` (imports shared `agentlib.py` from `~/agents/common/` via `sys.path`, not vendored).

