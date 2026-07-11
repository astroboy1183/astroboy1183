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
- **Purpose:** Sends one morning Telegram digest of all Gmail from the previous 24h, sorted into NEEDS ACTION / FYI / NOISE.
- **Schedule (IST):** 06:00 primary, 07:00 backup (`30 0 * * *` / `30 1 * * *` UTC); 19:00 evening sweep.
- **Inputs / data sources:** Gmail API (via `google-api-python-client`, `gmail.readonly` OAuth) — messages list + metadata-only fetch; the Anthropic API for summarization; `VIP_SENDERS` secret; `state/noise.json`.
- **Pipeline:**
  1. `digest_window` — compute the anchored 24h window ending at the most recent 6:00 AM IST.
  2. `gmail_service` — authenticate (silent token refresh; raises in CI if token unusable).
  3. `fetch_emails` — one Gmail search (`after/before -category:spam`), paginated, then per-message metadata fetch (From, Subject, snippet); builds deep link, VIP flag, threadId.
  4. `group_by_thread` — collapse same-thread messages to one representative entry with a count.
  5. `summarize` — **1 Claude call** (`claude-haiku-4-5`, `max_tokens=4000`): sorts the day's threads into a fixed headline / NEEDS ACTION / FYI / NOISE shape and appends a hidden `===STATE===` JSON tail listing the senders it counted as noise. Empty inbox skips the model entirely.
  6. `split_state` separates digest from noise-sender JSON; `validate_links` strips any Gmail link the model didn't copy verbatim.
  7. Prepend deterministic `vip_block`, add Sunday `unsubscribe_block`, `send_telegram`.
  8. After the send, record today's noise senders into `state/noise.json`.
- **LLM role:** 🧠 1 Claude call — the model decides classification (needs-action vs. FYI vs. noise) and per-item summaries; VIP surfacing and link validity are enforced deterministically around it.
- **State / memory:** `state/noise.json` — `{sender: [dates filed as noise]}`, pruned to a 14-day window, committed back by the workflow; drives Sunday unsubscribe suggestions (noise on ≥5 of last 14 days).
- **Output format:** Header (date + exact window + raw email count), optional 🔔 VIP block, then the model's headline + NEEDS ACTION / FYI / NOISE sections; on Sundays an optional 📉 Unsubscribe-candidates block. An empty inbox sends "Quiet inbox: no email in 24h ☕".
- **Notable design decisions:**
  - Anchored (not rolling) window so a delayed backup run covers the exact same day with no gaps/overlap.
  - VIP mail guaranteed visible via a code-generated block, independent of model behavior.
  - Hallucinated Gmail links replaced with `[invalid link removed]`.
  - State saved only after the send, and OAuth files are materialized from secrets at run time (never committed).
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
- **Purpose:** Filters the ESPN Cricinfo live-scores board down to matches worth attention (India at any level, majors' internationals, IPL/WPL) and delivers them to Telegram twice a day.
- **Schedule (IST):** 06:00 (overnight matches, backup 07:00), 13:37 lunch (India match days) and ~21:47 (day's results, backup 22:47).
- **Inputs / data sources:** Cricinfo live-scores RSS (`https://static.cricinfo.com/rss/livescores.xml`) — up to 25 score-line titles.
- **Pipeline:**
  1. `gather_scores()` parses the RSS with feedparser; returns `None` if unreachable (network error / HTTP ≥400 / bozo with no entries), `[]` if reached but empty, else up to 25 titles.
  2. `notable(scores)` makes **1 Claude call** (`max_tokens=300`) used as a filter: keeps only qualifying lines verbatim (max 5), or outputs the sentinel `NONE` → empty list.
  3. `main()` raises on a dead feed (loud failure), stays silent on empty/no-notable, else sends. `CRICKET_FORCE=1` overrides silence with a placeholder line.
- **LLM role:** 🧠 1 Claude call — the model decides which score lines qualify as notable and copies them verbatim (it must not paraphrase scores); `NONE` when nothing qualifies.
- **State / memory:** none.
- **Output format:** `🏏 Cricket — <date>` header then the kept score lines, one per line. Silent when the board is empty or nothing qualifies (a message always means a match worth checking).
- **Notable design decisions:**
  - Three-way `None`/`[]`/`[...]` contract separates real breakage (raise, fires failure alert) from a genuinely quiet day (silent).
  - Machine-checkable `NONE` sentinel instead of parsing prose.
  - Upcoming India fixtures on the board are kept so a match never starts unannounced.
  - Dedupe guard uses a 3-hour window (not "today") so each backup pairs with its own edition while the evening edition still runs after the morning one.
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

### markets-brief
- **Purpose:** Sends a daily one-line-per-instrument market snapshot (last close and day-over-day move) for Indian/US indices, USD/INR, gold and Bitcoin.
- **Schedule (IST):** 06:00 daily including weekends (`30 0 * * *` UTC), backup 07:00.
- **Inputs / data sources:** Yahoo Finance public chart endpoint (`/v8/finance/chart/<symbol>`, `interval=1d&range=5d`, no key, browser User-Agent) across `query1`/`query2` hosts. Symbols: Nifty 50 `^NSEI`, Sensex `^BSESN`, S&P 500 `^GSPC`, Nasdaq `^IXIC`, USD/INR `USDINR=X`, Gold `GC=F`, Bitcoin `BTC-USD`.
- **Pipeline:**
  1. `quote(symbol)` GETs daily candles (falls through to the query2 mirror on host failure); takes the last two non-null closes for point + % change, and the timestamp paired with the final close for its real session date.
  2. `fmt(...)` builds one line: comma-grouped price (2 decimals under 1000, else whole units), ▲/▼/▬ arrow with a ±0.05% dead zone, signed percent, absolute move; tags the line with the session day when the close isn't today's (IST).
  3. `main()` loops symbols with per-symbol try/except and sends the assembled message.
- **LLM role:** ⚙️ deterministic — no Claude call, no API key.
- **State / memory:** none.
- **Output format:** `📈 Markets — <date>` header then one line per instrument (e.g. `Nifty 50: 24,010 ▲ +1.2% (+310)`), stale lines tagged like `(Fri close)`. Never silent; a broken symbol degrades to one `unavailable (<ErrorType>)` line.
- **Notable design decisions:**
  - Uses the last two non-null closes, deliberately not the metadata `chartPreviousClose` (which is the pre-range close, not the prior session).
  - Timestamp kept paired with each close so dropping nulls can't drift the labelled session date.
  - Dual-host fallback (query1 → query2) so a single-host flake doesn't drop a symbol; per-symbol isolation keeps one failure from killing the brief.
  - Runs every day since FX/Bitcoin move on weekends; honest weekend/holiday session-date tagging.
- **Key dependencies:** `requests`, `python-dotenv` (send-only; no `anthropic`).

---

## ☀️ Daytime &amp; weekly agents

### release-radar
- **Purpose:** Weekly Telegram digest of the last 7 days of GitHub releases across ten data/LLM-infra repos, condensed into "what this means for you" developer bullets.
- **Schedule (IST):** Mondays 06:00 IST (dispatched on the minute); GitHub cron `30 1 * * 1` UTC = Mon 07:00 IST is a guarded backup.
- **Inputs / data sources:** GitHub REST API — `/repos/{repo}/releases` (paged, newest-first) and, as a fallback, `/repos/{repo}/tags` + each tag's commit endpoint for commit dates. Watch list is the hardcoded `REPOS` (qdrant, langchain, spark, anthropic-sdk-python, airflow, kafka, dbt-core, duckdb, polars, delta). Optional `GITHUB_TOKEN` only for higher rate limits.
- **Pipeline:**
  1. Fetch releases per repo, paging (100/page, up to 5 pages) and stopping once a release predates the 7-day cutoff; skip drafts and pre-releases.
  2. If a repo yielded no releases, fall back to `recent_tags()` — resolve each candidate tag's commit date (bounded to 5 lookups), skipping RC/beta/alpha/milestone/preview names.
  3. Keyword-scan each release for security markers (CVE/GHSA/security/vulnerabilit) and tag `[SECURITY]`.
  4. If nothing found, send a one-line "Quiet week" message with no model call; otherwise assemble one blob and make **1 Claude call** (`max_tokens=1500`) to turn all notes into 1–3 bullets per release.
  5. Append a "⚠️ Could not check" footer for any repo whose fetch raised, then `send_telegram`.
- **LLM role:** 🧠 1 Claude call — summarizes/prioritizes release notes into developer-relevant bullets, ordering `[SECURITY]` items first with patch urgency and flagging breaking changes. All fetching/filtering/security detection is deterministic Python.
- **State / memory:** none.
- **Output format:** Header `📡 Release radar — week ending <date>`, then either "Quiet week: no new releases in …" or the model's plain-text bullets (security items first as `🔴 SECURITY`, `⚠ breaking:` callouts); optional failure footer. Never fully silent — a quiet week still sends the one-liner.
- **Notable design decisions:**
  - Per-repo `try/except` so one failing repo can't kill the digest; failures are surfaced in a footer.
  - Pagination-with-cutoff avoids truncating high-cadence repos (duckdb/polars) while `MAX_PAGES`/`MAX_TAG_LOOKUPS` bound runaway loops.
  - Timestamp parsing via `fromisoformat` tolerates format drift so one odd timestamp can't drop a repo; notes truncated to 3000 chars to bound prompt size.
  - Tag-only fallback surfaces Apache-style projects that tag without publishing Releases.
- **Key dependencies:** `requests`, `python-dotenv`, `anthropic`.

### study-coach
- **Purpose:** Sends one LeetCode-style DSA practice problem to Telegram each morning, targeting the syllabus topic least represented in the user's recent practice.
- **Schedule (IST):** Daily 06:00 IST (`30 0 * * *` UTC); backup at 07:00 IST with a dedupe guard.
- **Inputs / data sources:** GitHub API `/repos/astroboy1183/Data-Structures-and-Algorithms/commits` (latest 30 commit subjects, public, no token); local `state/served.json` history.
- **Pipeline:**
  1. Fetch recent commit subjects (`recent_practice()`, `[]` on failure); load `served.json`.
  2. Deterministically pick the topic: `classify()` maps each commit subject to one syllabus topic via `TOPIC_KEYWORDS`; `least_covered_topic()` targets the fewest-covered topic (day-of-year fallback when no signal), excluding yesterday's served topic so it never repeats two days running.
  3. Pick difficulty by day-of-year (`tm_yday % 3` → easy/medium/hard).
  4. **1 Claude call** (`max_tokens=1200`) to write exactly one problem at that difficulty/topic in a fixed shape (TOPIC / statement / 2 examples / constraints / fold line / HINT 1 / HINT 2 / APPROACH).
  5. Validate the model's echoed `TOPIC:` against the syllabus (`resolve_topic`) and force the header (`set_topic_header`) so it always names a real topic.
  6. Send; on Sundays append a deterministic "WEEK IN REVIEW". Record the served entry to `served.json` **after** the send.
- **LLM role:** 🧠 1 Claude call — writes the problem text only; topic and difficulty selection are decided in Python, and the model's topic label is overridden if it drifts off-syllabus.
- **State / memory:** `state/served.json` — list of `{date, topic, difficulty}`, last 60 kept; used for the never-repeat exclusion and Sunday's follow-through recap. Committed back by the workflow.
- **Output format:** Header `🧠 Study coach — <day date>`, then the problem with hints/approach below a "--- try it before reading on ---" spoiler line; Sundays append "— WEEK IN REVIEW —" cross-checking served topics against commits (✓ practiced / not seen, "Followed through on N/M"). Always sends daily (never silent).
- **Notable design decisions:**
  - Weakness targeting and rotation are guaranteed in Python, not on model behavior; day-of-year fallback keeps rotating even when the API fails or nothing classifies.
  - Hints below the fold keep it to one self-contained message a day (the scroll is the spoiler wall) instead of a separate answer message.
  - State saved only after the send, so a state-write failure never costs the problem.
  - First-matching-topic-in-syllabus-order rule ensures each commit counts toward exactly one topic.
- **Key dependencies:** `requests`, `python-dotenv`, `anthropic`.

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
- **Purpose:** Every Saturday morning, deliver one Telegram message with the week's 6-8 most relevant AI/data-engineering arXiv papers, each with a title, two-sentence takeaway, and link.
- **Schedule (IST):** Saturday 06:00 IST — dispatched on the minute; guarded GitHub cron backup an hour later (`30 1 * * 6` UTC = 07:00 IST).
- **Inputs / data sources:** arXiv Atom API (`export.arxiv.org/api/query`), categories `cs.LG`, `cs.CL`, `cs.AI`, `cs.DB`, over a 7-day lookback window.
- **Pipeline:**
  1. **Fetch** — `fetch_recent()` paginates each category newest-first in pages of 100, stopping when an entry predates the 7-day cutoff or the feed empties, hard-capped at 12 pages (≤1200 entries/category), with a 3s pause between pages.
  2. **Down-sample** — each category's pool is trimmed to `MAX_PER_CATEGORY` (150) *evenly across the week* so ML categories don't crowd out cs.DB and the total fits model context (a busy week is ~1500 papers).
  3. **Dedupe** — `main()` merges categories, dropping cross-listed duplicates by title; per-category `try/except` collects failures.
  4. **Stage 1 skim (LLM)** — `shortlist()` chunks candidates (150/chunk), showing the cheap model each paper's category + title + 200-char snippet; it returns JSON indices of up to 12 keeps per chunk, recall-biased (unparseable reply keeps the whole chunk). Skipped if the pool is already ≤12; an empty result falls back to the full pool.
  5. **Stage 2 rank (LLM)** — the survivors' full 600-char abstracts go to the stronger model, which picks and ranks 6-8, balancing across topics, formatting title + 2 sentences + link.
  6. **Deliver** — silent if <3 papers and no fetch failures; if thinness is due to fetch failures, it raises to trigger the workflow's loud alert. Otherwise sends.
- **LLM role:** 🧠🧠 Two stages, N+1 calls. Stage 1 = one call per chunk (cheap model, `PAPERS_MODEL_FILTER`, default `claude-haiku-4-5`) deciding which papers are worth reading in full. Stage 2 = one call (strong model, `PAPERS_MODEL_RANK`, default `claude-sonnet-5`) deciding the final ranked 6-8 and writing the prose.
- **State / memory:** none — each week is computed fresh from the 7-day arXiv window.
- **Output format:** Header `📄 Papers digest — week ending <DD Mon YYYY>` plus a scanned/read-in-full count, then the model's ranked plain-text list (title line, 2 terse sentences, link on its own line); a `⚠️ Could not check:` footer lists failed categories.
- **Notable design decisions:**
  - Weekly not daily — daily arXiv is noise; large volume in, 6-8 out.
  - Two-tier model split for cost — one model can't judge ~600 abstracts, so a cheap skim feeds a strong re-rank "for pennies."
  - Recall-biased stage 1 and full-pool fallbacks — never silently drop a chunk or go empty from a broken filter.
  - Silence over filler on a genuinely quiet week, but loud failure when fetches break.
- **Key dependencies:** `feedparser`, `requests`, `python-dotenv`, `anthropic`.

---

## 🌆 Evening cloud agents

### eng-blogs
- **Purpose:** Every evening, deliver one Telegram message summarizing new posts from 18 company engineering blogs for a data engineer, while archiving each post into a growing full-text corpus for a future RAG project.
- **Schedule (IST):** Daily 06:00 IST (`30 0 * * *` UTC), with a dedupe-guarded backup cron at 07:00 IST.
- **Inputs / data sources:** 18 RSS/Atom feeds in three categories — Data & Analytics (Databricks, Confluent, Snowflake, AWS Big Data, dbt, DuckDB), Systems & Scale (Netflix, Uber, Meta, Cloudflare, Discord, Slack, Stripe, Dropbox), Product & ML Eng (Spotify, Airbnb, Pinterest, Canva). Default 24h lookback; also reads the current month's corpus file for dedup.
- **Pipeline:**
  1. **Fetch** — `gather_posts()` requests each feed over HTTP with a 20s timeout and a custom User-Agent (bare python-requests UA is rejected by some corporate feeds), then `feedparser.parse(resp.content)`.
  2. **Cap** — takes the first `ENTRIES_PER_FEED` (8) entries, or a raised `PER_FEED_LIMIT` (30) for high-volume whole-blog feeds (Databricks, AWS Big Data, Stripe) so a busy day isn't truncated before the freshness check.
  3. **Freshness filter** — `fresh()` keeps entries newer than the cutoff using the publish date (falling back to updated date only when there's no publish date); undated entries are dropped.
  4. **Clean** — `clean()` strips HTML tags and collapses whitespace; summaries truncated to 400 chars.
  5. **Archive (corpus growth)** — if any posts, `archive_posts()` appends new posts (deduped by link) to the monthly JSONL, fetching each post's full readable text first.
  6. **Summarize (LLM)** — `summarize()` sends all posts grouped by category to one model call producing the sectioned digest.
  7. **Deliver** — silent only when zero posts AND no feed failures (unless `ENG_BLOGS_FORCE=1`); a dead feed still triggers a send with a rot footer even on an otherwise-quiet day.
- **LLM role:** 🧠 One Claude call per run — decides which posts to keep vs. drop as pure marketing, ranks within each section (deep-dives/postmortems above release notes), and writes each post's 1-2 sentence technical takeaway.
- **State / memory:** `data/posts-YYYY-MM.jsonl` — one JSONL file per month, committed back by the workflow. Each record: `date`, `category`, `source`, `title`, `summary`, `link`, and `text` — the post's full readable text (`fetch_full_text` strips script/style/head/nav/footer/header then all tags, capped at 20,000 chars; blocked/paywalled hosts store an abstract-only record with empty text). Deduped by link against the current month's file. This is the raw corpus for the planned "ask-my-library" RAG project.
- **Output format:** Header `📚 Engineering blogs — <Day DD Mon YYYY>` plus a new-post count, then plain-text sections `🗄 DATA & ANALYTICS`, `⚙️ SYSTEMS & SCALE`, `🚀 PRODUCT & ML ENG` (empty sections skipped); each post is "Source — title", 1-2 sentences, link on its own line. A `⚠️ feeds not responding:` footer lists failed feeds.
- **Notable design decisions:**
  - Silent-by-default — blogs post rarely, so any message means there's something to read; the sole exception is a feed-rot footer on an otherwise-silent day.
  - Corpus is decoupled from delivery — full text is fetched and archived best-effort (an archive/OSError failure never costs the digest).
  - Freshness uses publish-over-updated date to stop lightly-edited old posts re-entering the window; undated posts dropped since corporate feeds are reliably dated.
  - Per-feed limit overrides and explicit timeouts protect against high-volume feeds being clipped and hanging hosts stalling the run.
- **Key dependencies:** `feedparser`, `requests`, `python-dotenv`, `anthropic`.

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
- **Schedule (IST):** none — `workflow_dispatch` only (GitHub's "Run workflow" button / `gh workflow run audit.yml`); the fleet's first on-demand member: no cron, no scheduler entry, no watchdog line.
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
- **Purpose:** Nightly health check of the owner's Linux Mint laptop that alerts (or sends an all-clear) to Telegram.
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

### daily-review
- **Purpose:** Nightly end-of-day digest of the owner's coding activity plus a fleet watchdog over all cloud agents, delivered to Telegram.
- **Schedule (IST):** 22:15 nightly (`OnCalendar=*-*-* 22:15:00`, `Persistent=true`, `RandomizedDelaySec=60`) — the one agent kept at day's end, since it reviews the day.
- **Execution:** Local **systemd** user timer on the laptop (not GitHub Actions).
- **Inputs / data sources:** Local git repos under `~/Desktop` and `~/agents` (`REVIEW_ROOTS`-overridable) via `git log/status/rev-list`; GitHub Actions run history via authenticated `gh api` for each rostered cloud agent; `systemctl --user show` for the housekeeper service; byte-comparison of every `~/agents/*/agentlib.py` against `common/agentlib.py`. Anthropic API for the writeup.
- **Pipeline:**
  1. `find_repos()` + `repo_report()` — today's commit subjects per repo, backward-walked streak, dirty/unpushed state.
  2. `cloud_agent_status()` for each of ~10 daily agents (+ weekly agents on their weekday) — queries today's workflow runs and classifies ran-ok / fired-but-no-success / not-due-yet / DID NOT FIRE, with a `CRON_GRACE_MIN=105` window.
  3. `housekeeper_status()` — did the local housekeeper run and exit 0 today.
  4. `agentlib_drift()` — flags any vendored agentlib copy diverging from `common/`.
  5. Sundays: `week_report()` — per-repo commit counts over 7 days.
  6. Assemble the findings block → **one Claude call** → `send_telegram()`; findings also printed to journald.
- **LLM role:** 🧠 1 Claude call (default `claude-haiku-4-5`, `max_tokens` 800 Sunday / 600 otherwise). The model composes the 8–14 line review: infers the day's theme from commit subjects, notes streaks, gives a gentle uncommitted/unpushed reminder, collapses the fleet to "✓ all agents ran" unless there's a problem, adds a Sunday WEEK IN REVIEW, and ends with exactly one suggestion for tomorrow. All data gathering is deterministic.
- **State / memory:** none (relies on live git history and GitHub run history).
- **Output format:** `🌙 Daily review — <day date>` + the model's plain-text review (built from a fixed findings block: TODAY'S WORK, AGENT FLEET, and Sunday's THIS WEEK). Always sends — it's a review, not an alarm.
- **Notable design decisions (fleet-watchdog role):**
  - Acts as the fleet's supervisor: independently verifies from the laptop that every cloud agent's cron actually fired that day (counting both GitHub `schedule` and fleet-scheduler `workflow_dispatch` events), catching a silently dead agent that its own "stay silent when nothing to say" design would otherwise hide.
  - `CRON_GRACE_MIN=105` accounts for the +60min backup cron and `Persistent=true` morning catch-up runs, so "not due yet" is never misreported as a miss.
  - Also watches the other local agent (housekeeper via systemd) and guards against silent `agentlib.py` drift across the fleet.
  - Roster (`CLOUD_AGENTS`/`WEEKLY_AGENTS`) is hand-maintained in sync with the fleet; repo roots are portable via `REVIEW_ROOTS`.
- **Key dependencies:** `requests~=2.34`, `python-dotenv~=1.2` (imports shared `agentlib.py` from `~/agents/common/`; also requires an authenticated `gh` CLI at runtime).

---

*Each agent's own repo README carries the fullest detail and rationale — this
page is the cross-fleet index. For the shared system all these agents run on,
see **[ARCHITECTURE.md](ARCHITECTURE.md)**.*
