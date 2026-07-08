# Hi, I'm Jayanth 👋

Data engineer building AI systems. I study DSA daily and run a fleet of
autonomous agents that manage my mornings, my machine, and my code.

## 🤖 The agent fleet

Fourteen single-purpose agents — each its own repo, schedule, and
Telegram bot. Built on GitHub Actions + systemd with dedupe-guarded
backup crons, instant failure alerts, and a nightly watchdog that
notices when any cron doesn't fire.

| Agent | What it does | When (IST) |
|---|---|---|
| [weather-report](https://github.com/astroboy1183/weather-report) | 24-city forecast, region-grouped, no LLM | 06:03 |
| [mail-digest](https://github.com/astroboy1183/mail-digest) | Gmail → NEEDS ACTION / FYI / NOISE with deep links | 06:07 |
| [news-briefing](https://github.com/astroboy1183/news-briefing) | India / US / geopolitics, deduped with sources | 06:13 |
| [cricket-scores](https://github.com/astroboy1183/cricket-scores) | Notable matches only — silent otherwise | 06:17 & 21:47 |
| [tech-news](https://github.com/astroboy1183/tech-news) | Sectioned tech briefing | 06:59 |
| [markets-brief](https://github.com/astroboy1183/markets-brief) | Nifty · Sensex · S&P · Nasdaq · USD/INR · gold · BTC | 07:33 |
| [release-radar](https://github.com/astroboy1183/release-radar) | Weekly releases across my dependency stack | Mon 07:37 |
| [study-coach](https://github.com/astroboy1183/study-coach) | One DSA problem/day, picked from my practice gaps | 08:07 |
| [finance-tracker](https://github.com/astroboy1183/finance-tracker) | Income/expense tracking from bank alert emails | 08:31 |
| [papers-digest](https://github.com/astroboy1183/papers-digest) | Weekly arXiv picks for LLM/data engineers | Sat 09:07 |
| [eng-blogs](https://github.com/astroboy1183/eng-blogs) | 18 company engineering blogs, silent on quiet days | 19:07 |
| [repo-review](https://github.com/astroboy1183/repo-review) | Reviews my whole account's diffs daily + portfolio advice | 19:37 |

…plus two local systemd agents (laptop housekeeper, end-of-day review)
that keep the machine and the fleet itself honest.

Every repo's README covers what it does, how the code works, and the
design decisions — start with any of them.

## 🔭 Currently building

- A **fleet telemetry lakehouse** — dbt + DuckDB over the fleet's own
  run history (how late do GitHub crons really fire?)
- **RAG with real evals** over my engineering-blog archive (Qdrant +
  golden-question harness)
- A **streaming pipeline** — Kafka → Spark Structured Streaming — over a
  live feed

## 📌 Stack

Python · SQL · Spark · Kafka · Airflow · dbt · DuckDB · Qdrant ·
GitHub Actions · systemd · LLM APIs
