<!-- GENERATED FILE — do not edit directly.
     Facts live in profile.yaml, the skeleton in template.md;
     scripts/build_readme.py rebuilds this every morning. -->
<div align="center">

# Jayanth Appalla

**Data Engineer — data platforms, AI systems, and automation that runs itself**

[![Portfolio](https://img.shields.io/badge/Portfolio-jayanthappalla.com-6f42c1?style=for-the-badge&logo=safari&logoColor=white)](https://jayanthappalla.com)
&nbsp;
[![LinkedIn](https://img.shields.io/badge/LinkedIn-jayanth--appalla-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/jayanth-appalla/)
&nbsp;
[![Email](https://img.shields.io/badge/Email-jayanthapalla%40gmail.com-EA4335?style=for-the-badge&logo=gmail&logoColor=white)](mailto:jayanthapalla@gmail.com)

🏢 ex-AWS (DynamoDB) · 🎓 MS CS, University of Illinois Chicago · 📜 6 certifications · 📝 published researcher

</div>

---

## 👋 About me

I'm a data engineer at **[trigyan.io](https://trigyan.io)**, building the data platform behind a healthcare product.
Before this: **AWS**, on the DynamoDB
team — backup/restore and import at multi-TB scale — and Azure
Databricks lakehouse work in consulting. ~3 years in industry, MS in
Computer Science from UIC.

What I like working on: pipelines that move serious data (Spark, Kafka,
Databricks, medallion architectures), and **LLM systems with real
engineering discipline** — deterministic where possible, model calls only
where judgment helps, everything tested and observable. To practice
what I preach, I built a fleet of autonomous agents that runs my
mornings — more below.

**Certifications:** Databricks Certified Associate Data Engineer (2025) ·
Microsoft Certified Administrator Associate (2025) ·
Microsoft Certified Fabric Data Engineer (2025) ·
[PCEP-30-02] PCEP™ – Certified Entry-Level Python Programmer (2025) ·
Tableau Certified Desktop Specialist (2024) ·
AWS Certified Cloud Practitioner (2023)

---

## 🔄 Now

*This section updates itself every morning — data from my own repos and
agents, no hands involved.*

<!--NOW-START-->
⚙️ **156 commits** across 12 repos this week

🚢 last shipped: *"style all sections as terminal windows with typed commands"* in `astroboy1183.github.io`

🤖 agent fleet: **1/8 green** yesterday

<sub>last updated 15 Jul 2026 — automatically</sub>
<!--NOW-END-->

---

## 💼 Experience, briefly

- **Trigyan** — Data Engineer *(current)*: data platform for a healthcare product
- **SPV Consulting** — Data Engineer: Azure Databricks pipelines at gigabyte scale (partitioning, Z-ordering, caching), Bronze/Silver/Gold modeling, Power BI delivery
- **Amazon Web Services** — SDE, DynamoDB: multi-TB backup/import/restore service; raised the import S3-object limit 10k → 100k, cutting large import times ~20%; on-call for a tier-1 service
- **Earlier**: ServiceNow ITSM/ITOM integration and AWS-ServiceNow integration at I-ConnectResources (certified ServiceNow Administrator, certified Appian developer); SAP Analytics + Java/Spring microservices at Incture; NLP chatbots intern at Hindustan Unilever

**Publication:** *"Real-time Object Detection and Face Recognition System to Assist the Visually Impaired"* — Journal of Physics: Conference Series, Vol. 1706 (IOP), 2020 — YOLO + Kafka-streamed video on Android.

Full resume on [my site](https://jayanthappalla.com) · full history on [LinkedIn](https://www.linkedin.com/in/jayanth-appalla/).

---

## 🛠 Projects

| Project | What it is |
|---|---|
| [news-intelligence-platform](https://github.com/astroboy1183/news-intelligence-platform) | Async FastAPI backend for news aggregation and querying (Python) |
| [election-dashboard](https://github.com/astroboy1183/election-dashboard) | Election-results dashboard with real data modeling and caching (TypeScript) |
| [SmartDay-App](https://github.com/astroboy1183/SmartDay-App) | Day-planner mobile app — Expo + SQLite (TypeScript) |
| [Quiz-App](https://github.com/astroboy1183/Quiz-App) | Quiz backend with async plumbing, auth and migrations (Python) |
| [sentiment-analysis](https://github.com/astroboy1183/sentiment-analysis) | Sentiment-analysis baseline with a real test suite (Python) |
| [DocMind](https://github.com/astroboy1183/DocMind) | RAG document Q&A — parse, embed, ask (Python) |
| [ipl-intelligence-platform](https://github.com/astroboy1183/ipl-intelligence-platform) | IPL cricket analytics API (TypeScript) |

**Currently building:** a fleet telemetry lakehouse (dbt + DuckDB over my agents' run history) · RAG with real evals over a daily-growing engineering-blog corpus · a Kafka → Spark Structured Streaming pipeline.

---

## 🤖 The agent fleet (the side project that runs my life)

Twelve autonomous agents — each its own repo, schedule, Telegram bot
and memory — built to deliver my mornings at 06:00 IST sharp: weather,
mail triage, 7-section news, a 9-section tech briefing, my own money
movement, a code review of everything I pushed yesterday, a top-10
reading list. Zero servers: a Cloudflare Worker dispatches GitHub
Actions at exact minutes (~6s, after GitHub's own cron once ran 4
hours late), state is committed back after every run, and a watchdog
notices any agent that silently dies. The fleet scales with my needs —
3 agents are dispatched daily right now, the rest pause
and resume with a one-line scheduler change.

**The engineering story → [ARCHITECTURE.md](ARCHITECTURE.md)** ·
**every agent in detail → [AGENTS.md](AGENTS.md)**

---

## 🧰 Skills

**Data engineering**  
![Apache Spark](https://img.shields.io/badge/Spark%20%2F%20PySpark-E25A1C?style=flat-square&logo=apachespark&logoColor=white)
![Apache Kafka](https://img.shields.io/badge/Kafka-231F20?style=flat-square&logo=apachekafka&logoColor=white)
![Databricks](https://img.shields.io/badge/Azure%20Databricks-FF3621?style=flat-square&logo=databricks&logoColor=white)
![Snowflake](https://img.shields.io/badge/Snowflake-29B5E8?style=flat-square&logo=snowflake&logoColor=white)
![Delta Lake](https://img.shields.io/badge/Delta%20Lake-003366?style=flat-square&logo=delta&logoColor=white)
![dbt](https://img.shields.io/badge/dbt-FF694B?style=flat-square&logo=dbt&logoColor=white)
![DuckDB](https://img.shields.io/badge/DuckDB-FFF000?style=flat-square&logo=duckdb&logoColor=black)
![Airflow](https://img.shields.io/badge/Airflow-017CEE?style=flat-square&logo=apacheairflow&logoColor=white)
![Azure Data Factory](https://img.shields.io/badge/Azure%20Data%20Factory-0078D4?style=flat-square&logo=microsoftazure&logoColor=white)

**Languages & backend**  
![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![SQL](https://img.shields.io/badge/SQL-4479A1?style=flat-square&logo=postgresql&logoColor=white)
![Java](https://img.shields.io/badge/Java%20%2F%20Spring-6DB33F?style=flat-square&logo=spring&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white)

**AI / ML systems**  
![RAG](https://img.shields.io/badge/RAG%20%2B%20hybrid%20search-412991?style=flat-square&logo=anthropic&logoColor=white)
![Vector DBs](https://img.shields.io/badge/Vector%20DBs%20%2F%20Qdrant-DC244C?style=flat-square&logo=qdrant&logoColor=white)
![MCP](https://img.shields.io/badge/Model%20Context%20Protocol-000000?style=flat-square&logo=anthropic&logoColor=white)
![Hugging Face](https://img.shields.io/badge/Hugging%20Face-FFD21E?style=flat-square&logo=huggingface&logoColor=black)
![TensorFlow](https://img.shields.io/badge/TensorFlow-FF6F00?style=flat-square&logo=tensorflow&logoColor=white)

**Analytics & infra**  
![Power BI](https://img.shields.io/badge/Power%20BI-F2C811?style=flat-square&logo=powerbi&logoColor=black)
![Tableau](https://img.shields.io/badge/Tableau-E97627?style=flat-square&logo=tableau&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white)
![Cloudflare Workers](https://img.shields.io/badge/Cloudflare%20Workers-F38020?style=flat-square&logo=cloudflare&logoColor=white)
![systemd](https://img.shields.io/badge/Linux%20%2F%20systemd-000000?style=flat-square&logo=linux&logoColor=white)

---

## 📚 Learning in public

Daily DSA practice ([Data-Structures-and-Algorithms](https://github.com/astroboy1183/Data-Structures-and-Algorithms), [Leetcode-Problems](https://github.com/astroboy1183/Leetcode-Problems)) · Python for AI engineering ([code](https://github.com/astroboy1183/Python-AI), [notes](https://github.com/astroboy1183/Python-AI-Notes)) · tooling notes ([study-notes](https://github.com/astroboy1183/study-notes))

---

<div align="center">

**🌐 [jayanthappalla.com](https://jayanthappalla.com)** — portfolio,
projects and a working [contact form](https://jayanthappalla.com/#contact)

</div>