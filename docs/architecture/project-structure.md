@'
# Project Structure

## Overview

The project separates production application code, operational scripts,
experiments, documentation, and data storage.

The purpose is to keep the production ingestion pipeline stable while
allowing diagnostics and exploratory development to evolve independently.

## Directory Layout

```text
Fantasy_GM_Platform/
├── src/
│   ├── yahoo_auth.py
│   ├── yahoo_client.py
│   ├── paths.py
│   ├── storage.py
│   ├── ingestion/
│   │   ├── ingest_yahoo_leagues.py
│   │   ├── ingest_league_settings.py
│   │   ├── ingest_rosters.py
│   │   ├── ingest_player_availability.py
│   │   └── ingest_player_daily_stats.py
│   └── parsers/
│       ├── leagues.py
│       ├── rosters.py
│       └── teams.py
│
├── scripts/
│   ├── exports/
│   ├── diagnostics/
│   ├── analysis/
│   ├── experiments/
│   ├── maintenance/
│   └── legacy/
│
├── docs/
│   ├── architecture/
│   └── operations/
│
├── data/
│   ├── bronze/
│   ├── silver/
│   ├── gold/
│   ├── experiments/
│   └── exports/
│
└── README.md