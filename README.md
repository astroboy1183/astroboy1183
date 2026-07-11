<div align="center">

# Jayanth Appalla

**Data engineer building AI systems that run themselves**

[![Portfolio](https://img.shields.io/badge/Portfolio-jayanthappalla.com-6f42c1?style=for-the-badge&logo=safari&logoColor=white)](https://jayanthappalla.com)
&nbsp;
[![Fleet](https://img.shields.io/badge/agents-14-1f6feb?style=for-the-badge&logo=githubactions&logoColor=white)](AGENTS.md)
&nbsp;
[![Dispatch](https://img.shields.io/badge/dispatch-~6s-238636?style=for-the-badge&logo=cloudflare&logoColor=white)](ARCHITECTURE.md)

📐 **How the whole fleet works → [ARCHITECTURE.md](ARCHITECTURE.md)** · 🤖 **Every agent, in detail → [AGENTS.md](AGENTS.md)**

</div>

---

Every morning my phone lights up with messages I didn't write — the weather,
what's in my inbox, the ten blog posts worth reading, the papers that
mattered this week. They come from **12 agents I built**, each its own repo, schedule,
and Telegram bot, running on nobody's server for pennies a month. They alert
loudly when something breaks and stay silent when there's nothing to say.

Data engineer by trade. I automate my own life for practice — and build it all
in public.

---

## 🤖 The agent fleet

The full morning-to-night lineup. Each is dispatched at its **exact minute**
by a Cloudflare Worker ([fleet-scheduler](https://github.com/astroboy1183/fleet-scheduler)
— GitHub's own cron ran 4 hours late the morning I measured it; the Worker's
dispatches land in ~6 seconds), with guarded GitHub crons as backups, failure
alerts to Telegram, offline test suites in CI, and state memory the workflows
commit back after every run — so the agents remember yesterday.

| Agent | What it does | When (IST) |
|---|---|---|
| [weather-report](https://github.com/astroboy1183/weather-report) | 24-city forecast + AQI, severe-weather watch, no LLM | 06:00 |
| [mail-digest](https://github.com/astroboy1183/mail-digest) | Gmail → VIP / NEEDS ACTION / CARRIED / deadline ledger, deep links | 06:00 + 19:00 sweep |
| [news-briefing](https://github.com/astroboy1183/news-briefing) | 7-section news from 45 sources (incl. 🏛 India + 🗽 US politics), article-grounded | 06:00 + 21:00 wrap |
| [cricket-scores](https://github.com/astroboy1183/cricket-scores) | Sectioned scores; lunch edition on India days; Sunday Cricsheet stats | 06:00, 13:37, 21:47 |
| [tech-news](https://github.com/astroboy1183/tech-news) | Flagship 9-section briefing, core topics 10-deep, HN TOP + CISA patch-now | 06:00 + 19:15 wrap |
| [finance-tracker](https://github.com/astroboy1183/finance-tracker) | Ledger-backed income/expense from bank alerts — model classifies, Python sums | 06:00 |
| [papers-digest](https://github.com/astroboy1183/papers-digest) | Weekly arXiv: ~2,500 papers → 4 interest sections + HF-trending + spotlight | Sat 06:00 |
| [eng-blogs](https://github.com/astroboy1183/eng-blogs) | Daily top-10 reading list from 38 blogs, interest-ranked, never repeats | 06:00 |
| [repo-review](https://github.com/astroboy1183/repo-review) | Reviews every diff I push, remembers findings; CI health, hygiene scores | 06:00 |
| [repo-audit](https://github.com/astroboy1183/repo-audit) | On-demand X-ray of every repo → report cards + dashboard | button-press |

…plus a local systemd agent —
[housekeeper](https://github.com/astroboy1183/housekeeper) (laptop
health + the fleet watchdog, 06:00) — keeping the machine and the
fleet itself honest.

### 🧱 Fleet infrastructure

| Repo | Role |
|---|---|
| [fleet-scheduler](https://github.com/astroboy1183/fleet-scheduler) | The fleet's **clock**: a Cloudflare Worker dispatching every workflow at its exact minute |
| [common](https://github.com/astroboy1183/common) | The **shared library**: one reference `agentlib.py`; every vendored copy is drift-checked against it nightly |
| [fleet](https://github.com/astroboy1183/fleet) *(private)* | The **workspace hub**: a devcontainer + `clone-all.sh` that assembles all of the above in a Codespace |

> Every repo's README covers what it does, how the code works, and the
> design decisions — start with any of them.

---

## 🔭 Currently building

- A **fleet telemetry lakehouse** — dbt + DuckDB over the fleet's own
  run history (now that the crons fire on time, the delay data has a
  baseline)
- **RAG with real evals** over my engineering-blog archive — the corpus
  is already accumulating daily via eng-blogs; Qdrant + a
  golden-question harness next
- A **streaming pipeline** — Kafka → Spark Structured Streaming — over a
  live feed

---

## 🛠 Projects & apps

| Project | What it is |
|---|---|
| [DocMind](https://github.com/astroboy1183/DocMind) | Document AI — parsing and Q&A over documents (Python) |
| [news-intelligence-platform](https://github.com/astroboy1183/news-intelligence-platform) | News aggregation & analysis platform (Python) |
| [ipl-intelligence-platform](https://github.com/astroboy1183/ipl-intelligence-platform) | IPL cricket analytics (TypeScript) |
| [election-dashboard](https://github.com/astroboy1183/election-dashboard) | Election results dashboard (TypeScript) |
| [SmartDay-App](https://github.com/astroboy1183/SmartDay-App) | Day-planning app (TypeScript) |
| [Quiz-App](https://github.com/astroboy1183/Quiz-App) | Quiz application (Python) |
| [sentiment-analysis](https://github.com/astroboy1183/sentiment-analysis) | Sentiment analysis experiments (Python) |
| [full-stack-ai-python](https://github.com/astroboy1183/full-stack-ai-python) | Full-stack AI app in Python |
| [astroboy1183.github.io](https://github.com/astroboy1183/astroboy1183.github.io) | Source of [jayanthappalla.com](https://jayanthappalla.com) |

---

## 📚 Learning in public

- [Data-Structures-and-Algorithms](https://github.com/astroboy1183/Data-Structures-and-Algorithms)
  — daily DSA practice
- [Leetcode-Problems](https://github.com/astroboy1183/Leetcode-Problems)
  — LeetCode solutions
- [Python-AI](https://github.com/astroboy1183/Python-AI) ·
  [Python-AI-Notes](https://github.com/astroboy1183/Python-AI-Notes)
  — Python for AI engineering: code and notes
- [study-notes](https://github.com/astroboy1183/study-notes)
  — Git & GitHub, core Python concepts
- Coursework archive:
  [IBM Data Science](https://github.com/astroboy1183/Coursera-IBM-Data-Science) ·
  [Machine-Learning](https://github.com/astroboy1183/Machine-Learning) ·
  [kaggle](https://github.com/astroboy1183/kaggle) ·
  [Python-Masterclass](https://github.com/astroboy1183/Python-Masterclass) ·
  [Java-Masterclass](https://github.com/astroboy1183/Java-Programming-Masterclass)

---

## 📌 Stack

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![SQL](https://img.shields.io/badge/SQL-4479A1?style=flat-square&logo=postgresql&logoColor=white)
![Apache Spark](https://img.shields.io/badge/Spark-E25A1C?style=flat-square&logo=apachespark&logoColor=white)
![Apache Kafka](https://img.shields.io/badge/Kafka-231F20?style=flat-square&logo=apachekafka&logoColor=white)
![Airflow](https://img.shields.io/badge/Airflow-017CEE?style=flat-square&logo=apacheairflow&logoColor=white)
![dbt](https://img.shields.io/badge/dbt-FF694B?style=flat-square&logo=dbt&logoColor=white)
![DuckDB](https://img.shields.io/badge/DuckDB-FFF000?style=flat-square&logo=duckdb&logoColor=black)
![Qdrant](https://img.shields.io/badge/Qdrant-DC244C?style=flat-square&logo=qdrant&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white)
![Cloudflare Workers](https://img.shields.io/badge/Cloudflare%20Workers-F38020?style=flat-square&logo=cloudflare&logoColor=white)
![systemd](https://img.shields.io/badge/systemd-000000?style=flat-square&logo=linux&logoColor=white)
![LLM APIs](https://img.shields.io/badge/LLM%20APIs-412991?style=flat-square&logo=anthropic&logoColor=white)
