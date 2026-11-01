"""Centralized storage paths for the Yahoo Fantasy GM Platform.

This module defines the logical Bronze, Silver, Gold, export, and experiment
locations. It does not create directories automatically; writers should create
their destination directory when writing data.
"""

from pathlib import Path
from typing import Optional, Union

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = PROJECT_ROOT / "data"

SPORT = "nba"
SEASON = "2026-2027"
SOURCE = "yahoo"

# Bronze: source-preserving ingestion data.
BRONZE_ROOT = DATA_ROOT / "bronze"
BRONZE_YAHOO_NBA_ROOT = (
    BRONZE_ROOT / SOURCE / SPORT / f"season={SEASON}"
)

# League-independent Yahoo source domains.
BRONZE_PLAYERS_DIR = BRONZE_YAHOO_NBA_ROOT / "players"
BRONZE_PLAYER_METADATA_DIR = BRONZE_PLAYERS_DIR / "metadata"
BRONZE_PLAYER_STATS_DIR = BRONZE_PLAYERS_DIR / "stats"
BRONZE_TEAMS_DIR = BRONZE_YAHOO_NBA_ROOT / "teams"
BRONZE_NBA_TEAMS_DIR = BRONZE_TEAMS_DIR / "nba_teams"
BRONZE_GAMES_DIR = BRONZE_YAHOO_NBA_ROOT / "games"
BRONZE_GAME_SCHEDULE_DIR = BRONZE_GAMES_DIR / "schedule"
BRONZE_GAME_BOXSCORES_DIR = BRONZE_GAMES_DIR / "boxscores"

# League-specific Yahoo source domains are rooted by league key.
BRONZE_LEAGUES_DIR = BRONZE_YAHOO_NBA_ROOT / "leagues"

# Bronze experimental payloads are kept outside normal production resources.
EXPERIMENTS_ROOT = DATA_ROOT / "experiments"

# Silver: trusted, normalized datasets. Each dataset has a stable grain/schema.
SILVER_ROOT = DATA_ROOT / "silver"
SILVER_NBA_ROOT = SILVER_ROOT / "nba" / f"season={SEASON}"
SILVER_FANTASY_ROOT = (
    SILVER_ROOT / "fantasy_basketball" / f"season={SEASON}"
)

SILVER_NBA_DIMENSIONS_DIR = SILVER_NBA_ROOT / "dimensions"
SILVER_NBA_FACTS_DIR = SILVER_NBA_ROOT / "facts"
SILVER_NBA_SNAPSHOTS_DIR = SILVER_NBA_ROOT / "snapshots"

SILVER_FANTASY_DIMENSIONS_DIR = SILVER_FANTASY_ROOT / "dimensions"
SILVER_FANTASY_FACTS_DIR = SILVER_FANTASY_ROOT / "facts"
SILVER_FANTASY_SNAPSHOTS_DIR = SILVER_FANTASY_ROOT / "snapshots"

# Gold: business-facing datasets consumed by dashboards and the GM Advisor.
GOLD_ROOT = DATA_ROOT / "gold"
GOLD_FANTASY_ROOT = GOLD_ROOT / "fantasy_basketball" / f"season={SEASON}"
GOLD_PLAYER_PERFORMANCE_DIR = GOLD_FANTASY_ROOT / "player_performance"
GOLD_LEADERBOARDS_DIR = GOLD_FANTASY_ROOT / "leaderboards"
GOLD_LEAGUE_INSIGHTS_DIR = GOLD_FANTASY_ROOT / "league_insights"
GOLD_GM_ADVISOR_DIR = GOLD_FANTASY_ROOT / "gm_advisor"

# CSV is for inspection/export, not the canonical Silver/Gold representation.
EXPORTS_ROOT = DATA_ROOT / "exports" / "csv"

# Explicit resource names keep the writer from guessing by inspecting strings.
LEAGUE_BRONZE_CATEGORIES = {
    "league/settings",
    "league/fantasy_teams",
    "league/rosters",
    "league/player_availability",
    "league/matchups",
    "league/transactions",
}
NON_LEAGUE_BRONZE_CATEGORIES = {
    "players/metadata",
    "players/stats",
    "teams/nba_teams",
    "games/schedule",
    "games/boxscores",
    "user/leagues",
}
ALL_BRONZE_CATEGORIES = (
    LEAGUE_BRONZE_CATEGORIES | NON_LEAGUE_BRONZE_CATEGORIES
)


def bronze_resource_dir(
    category: str,
    *,
    league_key: Optional[str] = None,
    sport: str = SPORT,
    season: str = SEASON,
    source: str = SOURCE,
) -> Path:
    """Return the Bronze directory for an explicitly declared resource.

    League-specific categories require a Yahoo league key. Unknown categories
    fail loudly so new resource types are intentionally classified.
    """
    if category not in ALL_BRONZE_CATEGORIES:
        raise ValueError(
            f"Unknown Bronze category {category!r}. "
            f"Choose one of: {sorted(ALL_BRONZE_CATEGORIES)}"
        )

    base = DATA_ROOT / "bronze" / source / sport / f"season={season}"

    if category in LEAGUE_BRONZE_CATEGORIES:
        if not league_key:
            raise ValueError(
                f"category={category!r} requires a league_key"
            )
        if not all(char.isalnum() or char in ".-_" for char in league_key):
            raise ValueError("league_key contains unsupported path characters")
        return (
            base
            / "leagues"
            / f"league_key={league_key}"
            / Path(category.split("/", 1)[1])
        )

    return base / Path(category)


def silver_dataset_dir(
    domain: str,
    dataset_type: str,
    dataset_name: str,
    *,
    season: str = SEASON,
    league_key: Optional[str] = None,
) -> Path:
    """Return a Silver dataset directory for dimensions, facts, or snapshots."""
    if dataset_type not in {"dimensions", "facts", "snapshots"}:
        raise ValueError("dataset_type must be dimensions, facts, or snapshots")
    if domain not in {"nba", "fantasy_basketball"}:
        raise ValueError("domain must be 'nba' or 'fantasy_basketball'")

    path = (
        SILVER_ROOT
        / domain
        / f"season={season}"
        / dataset_type
        / dataset_name
    )
    if domain == "fantasy_basketball" and league_key:
        if not all(char.isalnum() or char in ".-_" for char in league_key):
            raise ValueError("league_key contains unsupported path characters")
        path = path / f"league_key={league_key}"
    return path


def gold_dataset_dir(
    dataset_name: str,
    *,
    season: str = SEASON,
    league_key: Optional[str] = None,
) -> Path:
    """Return a Gold output directory, optionally scoped to one league."""
    path = (
        GOLD_ROOT
        / "fantasy_basketball"
        / f"season={season}"
        / dataset_name
    )
    if league_key:
        if not all(char.isalnum() or char in ".-_" for char in league_key):
            raise ValueError("league_key contains unsupported path characters")
        path = path / f"league_key={league_key}"
    return path


def ensure_directory(path: Union[str, Path]) -> Path:
    """Create a directory when needed and return its Path."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path
