# Hi, I'm Jayanth 👋

Data engineer building AI systems. I study DSA daily and run a fleet of
autonomous agents that manage my mornings, my money, my machine, and my
code.

## 🤖 The agent fleet

Fourteen single-purpose agents — each its own repo, schedule, and
Telegram bot. Dispatched at their **exact minute** by a Cloudflare
Worker ([fleet-scheduler](https://github.com/astroboy1183/fleet-scheduler)
— GitHub's own cron ran 4 hours late the morning I measured it; the
Worker's dispatches land in ~6 seconds), with guarded GitHub crons as
backups, failure alerts to Telegram, offline test suites running in CI,
and state memory the workflows commit back after every run — the agents
remember yesterday.

| Agent | What it does | When (IST) |
|---|---|---|
| [weather-report](https://github.com/astroboy1183/weather-report) | 24-city forecast + AQI, severe-weather watch, no LLM | 06:03 |
| [mail-digest](https://github.com/astroboy1183/mail-digest) | Gmail → NEEDS ACTION / FYI / NOISE, deep links, unsubscribe trends | 06:07 |
| [news-briefing](https://github.com/astroboy1183/news-briefing) | India / US / geopolitics, deduped across days, sourced | 06:13 |
| [cricket-scores](https://github.com/astroboy1183/cricket-scores) | Notable matches only — silent otherwise | 06:17 & 21:47 |
| [tech-news](https://github.com/astroboy1183/tech-news) | Sectioned tech briefing, HN ranked by real points | 06:59 |
| [markets-brief](https://github.com/astroboy1183/markets-brief) | Nifty · Sensex · S&P · Nasdaq · USD/INR · gold · BTC | 07:33 |
| [release-radar](https://github.com/astroboy1183/release-radar) | Weekly releases across my dependency stack, security first | Mon 07:37 |
| [study-coach](https://github.com/astroboy1183/study-coach) | One DSA problem/day, aimed at my practice gaps | 08:07 |
| [finance-tracker](https://github.com/astroboy1183/finance-tracker) | Income/expense from bank alerts — model classifies, Python sums | 08:31 |
| [papers-digest](https://github.com/astroboy1183/papers-digest) | Weekly arXiv, two-stage model review of ~1500 papers | Sat 09:07 |
| [eng-blogs](https://github.com/astroboy1183/eng-blogs) | 18 company engineering blogs + a growing full-text corpus | 19:07 |
| [repo-review](https://github.com/astroboy1183/repo-review) | Reviews every diff I push, remembers its findings, follows through | 19:37 |

…plus two local systemd agents —
[housekeeper](https://github.com/astroboy1183/housekeeper) (laptop
health, 21:30) and
[daily-review](https://github.com/astroboy1183/daily-review) (day
review + fleet watchdog, 22:15) — that keep the machine and the fleet
itself honest. The whole workspace assembles itself in a Codespace from
the [fleet hub repo](https://github.com/astroboy1183/fleet).

Every repo's README covers what it does, how the code works, and the
design decisions — start with any of them.

## 🔭 Currently building

- A **fleet telemetry lakehouse** — dbt + DuckDB over the fleet's own
  run history (now that the crons fire on time, the delay data has a
  baseline)
- **RAG with real evals** over my engineering-blog archive — the corpus
  is already accumulating daily via eng-blogs; Qdrant + a
  golden-question harness next
- A **streaming pipeline** — Kafka → Spark Structured Streaming — over a
  live feed

## 📌 Stack

Python · SQL · Spark · Kafka · Airflow · dbt · DuckDB · Qdrant ·
GitHub Actions · Cloudflare Workers · systemd · LLM APIs
