# ADR-001: Medallion Data Architecture

**Project:** Yahoo Fantasy GM Platform  
**Status:** Approved  
**Decision date:** October 28, 2026  
**Scope:** NBA fantasy basketball; multiple Yahoo leagues initially  
**Migration status:** Not yet executed; migration requires a reviewed dry run

## 1. Context

The Yahoo Fantasy GM Platform is evolving from API collection scripts into a reusable analytics platform with two primary products:

1. **League Intelligence Dashboard:** daily and historical player performance, rankings, trends, availability insights, and league-wide analytics.
2. **All-Team GM Advisor:** league-specific roster recommendations based on player performance, availability, scoring rules, schedules, and roster constraints.

The initial source is Yahoo Fantasy NBA for the 2026–2027 season. The platform must support multiple Yahoo fantasy leagues with different scoring rules and roster configurations. Additional sports or providers may be considered later, but are not part of the initial implementation scope.

## 2. Decision drivers

The architecture must:

- Preserve original source responses for auditability and replay.
- Separate ingestion, trusted reusable datasets, and business-facing analytics.
- Avoid duplicate API calls and duplicate transformation logic.
- Preserve historical roster and player-availability state.
- Support league-specific scoring profiles and scoring-profile versions.
- Use Parquet for canonical analytical datasets and CSV exports for inspection.
- Provide a stable data contract for a future dashboard webpage.
- Remain straightforward to develop and operate locally.

## 3. Decision: adopt Medallion architecture

The production data flow will be:

`Source → Bronze → Silver → Gold → Dashboard/API`

- **Bronze:** source responses preserved with ingestion metadata.
- **Silver:** validated, normalized, deduplicated, reusable datasets.
- **Gold:** curated metrics, leaderboards, league insights, and GM recommendations.

Production Gold datasets must not depend directly on unprocessed API responses. Exploratory experiments may be stored separately and must not become implicit production dependencies.

## 4. Decision: organize data by layer and domain

The canonical logical layout is:

```text
data/
├── bronze/
│   └── yahoo/
│       └── nba/
│           └── season=2026-2027/
│               ├── players/
│               │   ├── metadata/
│               │   └── stats/
│               ├── teams/
│               │   └── nba_teams/
│               ├── games/
│               │   ├── schedule/
│               │   └── boxscores/
│               └── leagues/
│                   └── league_key=478.l.105854/
│                       ├── settings/
│                       ├── fantasy_teams/
│                       ├── rosters/
│                       ├── player_availability/
│                       ├── matchups/
│                       └── transactions/
├── silver/
│   ├── nba/
│   │   └── season=2026-2027/
│   │       ├── dimensions/
│   │       ├── facts/
│   │       └── snapshots/
│   └── fantasy_basketball/
│       └── season=2026-2027/
│           ├── dimensions/
│           ├── facts/
│           └── snapshots/
├── gold/
│   └── fantasy_basketball/
│       └── season=2026-2027/
│           ├── player_performance/
│           ├── leaderboards/
│           ├── league_insights/
│           └── gm_advisor/
├── exports/
│   └── csv/
└── experiments/
```

This is a logical layout. Directories and datasets should only be created when needed. League-specific Silver and Gold outputs must include the relevant league key in their dataset partition or record keys; league data must not be conflated across leagues.

## 5. Decision: define explicit dataset grains and keys

Every Silver dataset must document its grain, primary or natural key, schema, source, and update behavior.

### NBA domain

- **`dim_player`:** one row per source-identified player. Initially use Yahoo's player key with source and sport context. Provider-independent identity resolution is deferred until another provider is introduced.
- **`dim_nba_team`:** one row per real NBA team.
- **`fact_player_daily_stats`:** one row per player and statistical date, containing normalized basketball statistics. If a reliable game identifier is available later, the model may evolve to include player-game facts.

### Fantasy basketball domain

- **`dim_fantasy_league`:** one row per fantasy league-season, including provider, sport, league key, and season.
- **`dim_fantasy_team`:** one row per fantasy team within its league-season. A fantasy team key must not be treated as globally unique without league context.
- **`dim_scoring_profile`:** one record per distinct scoring configuration version, based on normalized scoring modifiers and relevant roster/scoring configuration.
- **`fact_roster_snapshot`:** one row per player assignment in a fantasy roster snapshot, including league, fantasy team, roster position, observation time, and snapshot ID.
- **`fact_player_availability_snapshot`:** one row per player, league, and availability snapshot. It stores availability status and snapshot metadata without duplicating player descriptions.
- **`fact_league_settings_snapshot`:** a historical record of observed league settings. Current settings are derived from the latest valid snapshot.

## 6. Decision: availability is a slim historical dataset

Availability is league-specific and time-dependent, not a permanent player attribute.

The availability snapshot will contain at minimum:

- `season`
- `league_key`
- `player_key`
- `availability_status`
- `snapshot_id`
- `observed_at`

Initial status values are `ROSTERED`, `FA`, `W`, and `UNKNOWN` where appropriate. Roster ownership and roster position will come from roster snapshots rather than being duplicated in availability.

A current player pool is derived by joining the player dimension with the latest complete availability snapshot and current roster data. A missing player record must not automatically be classified as a free agent. Availability can be published as current only after the roster and availability collection has completed and passed validation. Historical snapshots are retained.

## 7. Decision: fantasy scoring is league-aware and versioned

Basketball statistics and fantasy points are separate data products. Silver retains underlying player statistics independently of league scoring rules.

A derived dataset, **`fact_player_league_daily_score`**, contains one player's score for a statistical date under a specific league-season and scoring-profile version. Its logical key includes:

- `league_key`
- `season`
- `player_key`
- `stat_date`
- `scoring_profile_id`

Fantasy points are calculated using the relevant modifiers, and the calculation version is recorded. Historical scores must not silently change when league settings change. If a scoring profile changes, the pipeline must retain sufficient information to reproduce or explicitly recalculate scores. If the historical effective date of rules is unknown, it must be recorded as an assumption.

## 8. Decision: use Parquet as the canonical Silver and Gold format

- **Bronze:** original JSON responses, preserved with timestamped filenames and ingestion metadata.
- **Silver:** Parquet datasets with validated schemas and explicit types.
- **Gold:** Parquet datasets containing reusable, dashboard-ready metrics.
- **CSV exports:** generated for inspection and debugging under `data/exports/csv/`; they are not authoritative sources.

Parquet is a columnar file format. It does not provide transactional table management or merge semantics by itself. Initial pipelines will use deterministic rebuilds or controlled file replacement for small datasets, and writes must not leave partially written canonical outputs. A database or table format such as Delta Lake will not be introduced solely to implement this architecture; transaction management can be revisited if concurrency or data volume requires it.

## 9. Decision: Gold is the dashboard data contract

Gold datasets are designed around business questions, not API endpoints. Initial products include:

- Daily player-performance leaderboards.
- Weekly and monthly player-performance summaries.
- Available-player rankings and league-wide insights.
- League-specific team and roster analysis.
- GM Advisor add/drop recommendations.

Gold outputs must include relevant league and season context, reporting period, scoring-profile version where applicable, and calculation/refresh timestamp. The future webpage consumes Gold through a backend or query interface; it does not independently fetch Yahoo responses or implement a separate fantasy-scoring formula in the frontend. Web framework and serving infrastructure are deferred.

## 10. Data quality and operational conventions

- Dates use ISO format; timestamps use UTC.
- `stat_date`, `observed_at`, and `ingested_at` have distinct meanings.
- Bronze source responses are append-only and are not edited to correct data.
- API requests are identifiable through source, resource, timestamp, and ingestion-run metadata.
- Credentials and OAuth tokens must never be stored in published datasets or committed to GitHub.
- Silver pipelines validate schema, key uniqueness, missing identifiers, and expected completeness.
- Gold datasets are reproducible from documented Silver inputs and transformations.
- Generated data and CSV exports remain outside version control unless a small, sanitized sample is intentionally added for documentation or testing.
- Partitioning must remain conservative; avoid excessive small files or directories for every player, team, or request.

## 11. Alternatives considered

### Continue with `data/raw/` and `data/processed/`

Rejected as the long-term naming convention because it does not explicitly express the distinct quality and consumption stages.

### Organize all data only by entity

Rejected as the only organizing principle. Entity-oriented folders are useful within layers, but do not distinguish original source evidence from validated data and business metrics.

### Introduce a database or full lakehouse immediately

Deferred. The current workload does not justify the additional infrastructure. The architecture retains a migration path if local file-based processing becomes insufficient.

### Store availability and fantasy scoring directly in the player dimension

Rejected. Availability is league- and time-dependent, while fantasy scoring depends on league settings.

## 12. Consequences and trade-offs

**Benefits:** clear layer responsibilities; shared NBA statistics across leagues; historical roster and availability analysis; separation of NBA identity, fantasy ownership, and scoring context; reusable dashboard and GM Advisor data; future extensibility.

**Costs:** more explicit schemas, keys, and joins; snapshot history increases storage and requires complete-run semantics; Parquet pipelines require deliberate rebuild and schema evolution behavior; scoring-profile versioning adds complexity; future providers require source-identity mapping.

These costs are accepted because long-term platform value depends on historical accuracy, reusable statistics, and league-specific recommendations.

## 13. Migration and implementation plan

No existing data is moved until the ADR is approved and a migration dry run is reviewed.

1. Implement shared paths and layer/domain configuration.
2. Define table schemas, keys, and dataset grain before migrating data.
3. Update the raw-response writer to use explicit resource categories and ingestion metadata.
4. Map every existing JSON and CSV file to a destination.
5. Run a dry run and verify file counts, destination collisions, and content preservation.
6. Execute migration without discarding source data.
7. Update readers and writers to use the new locations and Parquet schemas.
8. Validate the player pool, availability, scoring rules, daily stats, and existing leaderboard results.
9. Resume historical-statistics and leaderboard work only after validation.

The baseline daily leaderboard should reproduce the previously validated October 27, 2026 result, including Luka Dončić's 56.70 fantasy points under the scoring profile used for that calculation.

## 14. Scope exclusions

This ADR does not commit the project to immediate non-Yahoo provider support, additional sports, distributed processing, a specific database or web framework, schedule ingestion before a reliable source is chosen, or a full historical backfill before pipelines are validated.

## 15. Approval

**Approved by project owner on October 28, 2026.**

The approved baseline is Medallion layers, domain-oriented datasets, Parquet-based Silver and Gold, historical snapshots, and league-aware scoring. Implementation and migration must follow the reviewed dry-run process.
