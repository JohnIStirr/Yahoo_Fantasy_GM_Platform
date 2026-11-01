
"""Fetch daily player stats and calculate league-specific fantasy points."""

import argparse
import csv
import sys
from pathlib import Path

# Reuse the existing Yahoo API client.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from yahoo_client import yahoo_get, save_raw_data


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLAYER_POOL_FILE = PROJECT_ROOT / "data" / "processed" / "nba_player_pool.csv"
SETTINGS_DIR = PROJECT_ROOT / "data" / "raw" / "nba" / "league_settings"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

BATCH_SIZE = 25

# Translate Yahoo stat IDs into readable column names.
STAT_LABELS = {
    "0": "GP",
    "1": "GS",
    "2": "MIN",
    "3": "FGA",
    "4": "FGM",
    "5": "FG_PCT",
    "6": "FTA",
    "7": "FTM",
    "8": "FT_PCT",
    "9": "3PTA",
    "10": "3PTM",
    "11": "3PT_PCT",
    "12": "PTS",
    "13": "OREB",
    "14": "DREB",
    "15": "REB",
    "16": "AST",
    "17": "ST",
    "18": "BLK",
    "19": "TO",
    "20": "A_T",
    "21": "PF",
    "22": "DD",
    "23": "TECH",
    "24": "TD",
    "25": "FF",
}

OUTPUT_COLUMNS = [
    "date",
    "player_key",
    "player_id",
    "player_name",
    "nba_team_abbr",
    "availability_status",
    "fantasy_team_key",
    "roster_position",
    *STAT_LABELS.values(),
    "fantasy_points",
    "played",
]


def load_player_pool():
    """Load the existing player universe without another API request."""
    if not PLAYER_POOL_FILE.exists():
        raise FileNotFoundError(
            f"Player pool not found: {PLAYER_POOL_FILE}\n"
            "Run src/build_player_pool.py first."
        )

    with PLAYER_POOL_FILE.open(
        "r", newline="", encoding="utf-8-sig"
    ) as file:
        players = list(csv.DictReader(file))

    # Keep one entry per Yahoo player key.
    return {
        player["player_key"]: player
        for player in players
        if player.get("player_key")
    }


def load_scoring_modifiers():
    """Read the league's scoring weights from saved Yahoo settings."""
    files = sorted(SETTINGS_DIR.glob("league_settings_*.json"))

    if not files:
        raise FileNotFoundError(
            "Saved league settings not found. "
            "Run src/inspect_league_settings.py first."
        )

    import json

    with files[-1].open("r", encoding="utf-8") as file:
        response = json.load(file)

    # Find the settings object in Yahoo's nested response.
    settings_container = None

    for section in response.get("fantasy_content", {}).get("league", []):
        if isinstance(section, dict) and "settings" in section:
            settings_container = section["settings"]
            break

    if settings_container is None:
        raise ValueError("Could not find settings in the saved response.")

    if isinstance(settings_container, list):
        settings = next(
            (
                item for item in settings_container
                if isinstance(item, dict) and "stat_modifiers" in item
            ),
            None,
        )
    else:
        settings = settings_container

    if not isinstance(settings, dict):
        raise ValueError("Could not extract scoring settings.")

    modifier_entries = (
        settings.get("stat_modifiers", {}).get("stats", [])
    )

    modifiers = {}

    for entry in modifier_entries:
        stat = entry.get("stat", {})
        stat_id = str(stat.get("stat_id", ""))
        value = stat.get("value")

        if stat_id and value is not None:
            modifiers[stat_id] = float(value)

    if not modifiers:
        raise ValueError("No scoring modifiers were found.")

    return modifiers


def get_player_entries(response):
    """Extract player records from a batch API response."""
    players = response.get("fantasy_content", {}).get("players", {})

    if not isinstance(players, dict):
        return []

    # Yahoo numbers player records with keys such as "0", "1", "2".
    indexes = [
        key for key in players
        if str(key).isdigit()
    ]

    return [
        players[key]
        for key in sorted(indexes, key=lambda item: int(item))
    ]


def parse_player_record(entry, stat_date, player_pool, modifiers):
    """Normalize a Yahoo player response and calculate fantasy points."""
    parts = entry.get("player", [])
    metadata = {}
    daily_stats = {}

    # Player metadata and statistics are separate parts of the response.
    for part in parts:
        if isinstance(part, list):
            for item in part:
                if isinstance(item, dict):
                    metadata.update(item)

        elif isinstance(part, dict) and "player_stats" in part:
            daily_stats = part["player_stats"]

    player_key = metadata.get("player_key", "")
    if not player_key:
        return None

    # Ensure the API returned stats for the requested date.
    coverage = daily_stats.get("0", {})

    if coverage and (
        coverage.get("coverage_type") != "date"
        or coverage.get("date") != stat_date
    ):
        raise ValueError(
            f"Unexpected stats coverage for {player_key}: {coverage}"
        )

    # Convert numeric strings to numbers; Yahoo uses "-" for no stats.
    stat_values = {}

    for item in daily_stats.get("stats", []):
        stat = item.get("stat", {})
        stat_id = str(stat.get("stat_id", ""))
        raw_value = stat.get("value", "-")

        try:
            stat_values[stat_id] = float(raw_value)
        except (TypeError, ValueError):
            stat_values[stat_id] = 0.0

    # Calculate fantasy points using the actual league scoring weights.
    fantasy_points = sum(
        stat_values.get(stat_id, 0.0) * weight
        for stat_id, weight in modifiers.items()
    )

    pool_record = player_pool.get(player_key, {})
    player_name = metadata.get("name", {})
    if not isinstance(player_name, dict):
        player_name = {}

    row = {
        "date": stat_date,
        "player_key": player_key,
        "player_id": metadata.get("player_id", ""),
        "player_name": (
            player_name.get("full")
            or pool_record.get("player_name", "")
        ),
        "nba_team_abbr": (
            metadata.get("editorial_team_abbr")
            or pool_record.get("nba_team_abbr", "")
        ),
        "availability_status": pool_record.get(
            "availability_status", "UNKNOWN"
        ),
        "fantasy_team_key": pool_record.get("fantasy_team_key", ""),
        "roster_position": pool_record.get("roster_position", ""),
    }

    for stat_id, label in STAT_LABELS.items():
        row[label] = stat_values.get(stat_id, 0.0)

    row["fantasy_points"] = round(fantasy_points, 2)
    row["played"] = int(row["MIN"] > 0)

    return row


def fetch_daily_stats(stat_date, player_pool, modifiers):
    """Fetch daily stats for the player pool in manageable batches."""
    player_keys = sorted(player_pool.keys())
    batches = [
        player_keys[index:index + BATCH_SIZE]
        for index in range(0, len(player_keys), BATCH_SIZE)
    ]

    results = {}

    for batch_number, batch in enumerate(batches, start=1):
        keys = ",".join(batch)

        endpoint = (
            f"/players;player_keys={keys}"
            f"/stats;type=date;date={stat_date}"
        )

        print(
            f"Batch {batch_number}/{len(batches)}: "
            f"requesting {len(batch)} players"
        )

        response = yahoo_get(endpoint)

        # Save each original response for troubleshooting and reuse.
        resource = (
            f"daily_stats_{stat_date}_batch_{batch_number:03d}"
        )
        save_raw_data(response, "nba", resource)

        entries = get_player_entries(response)
        print(f"  Records returned: {len(entries)}")

        for entry in entries:
            row = parse_player_record(
                entry, stat_date, player_pool, modifiers
            )

            if row:
                # Use player_key to prevent duplicate records.
                results[row["player_key"]] = row

    return results


def write_csv(path, rows, columns):
    """Write normalized records to a CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch daily Yahoo Fantasy player statistics."
    )
    parser.add_argument(
        "--date",
        default="2026-10-27",
        help="Game date in YYYY-MM-DD format.",
    )
    stat_date = parser.parse_args().date

    player_pool = load_player_pool()
    modifiers = load_scoring_modifiers()

    print(f"Player pool size: {len(player_pool)}")
    print(f"Scoring modifiers loaded: {len(modifiers)}")
    print(f"Fetching daily stats for {stat_date}...\n")

    stats_by_key = fetch_daily_stats(
        stat_date, player_pool, modifiers
    )
    all_rows = list(stats_by_key.values())

    # Export all returned players, including those without game stats.
    stats_file = (
        OUTPUT_DIR / f"nba_daily_player_stats_{stat_date}.csv"
    )
    write_csv(stats_file, all_rows, OUTPUT_COLUMNS)

    # Rank players who recorded playing time.
    played_rows = [
        row for row in all_rows if row["played"] == 1
    ]
    played_rows.sort(
        key=lambda row: row["fantasy_points"],
        reverse=True,
    )

    leaderboard_columns = ["rank", *OUTPUT_COLUMNS]

    for rank, row in enumerate(played_rows, start=1):
        row["rank"] = rank

    leaderboard_file = (
        OUTPUT_DIR / f"nba_daily_leaderboard_{stat_date}.csv"
    )
    write_csv(
        leaderboard_file,
        played_rows,
        leaderboard_columns,
    )

    # Report coverage so incomplete batches are visible.
    missing_keys = set(player_pool) - set(stats_by_key)

    print("\nDaily stats collection complete.")
    print(f"Players in pool: {len(player_pool)}")
    print(f"Player records received: {len(stats_by_key)}")
    print(f"Players with missing responses: {len(missing_keys)}")
    print(f"Players with minutes played: {len(played_rows)}")
    print(f"Daily stats file: {stats_file}")
    print(f"Leaderboard file: {leaderboard_file}")

    if missing_keys:
        print(
            "WARNING: The dataset is incomplete. "
            "Check the batch responses before relying on rankings."
        )
    else:
        print("\nTop 5 fantasy performers:")
        for row in played_rows[:5]:
            print(
                f'{row["rank"]}. {row["player_name"]} '
                f'({row["nba_team_abbr"]}) — '
                f'{row["fantasy_points"]:.2f} FP'
            )


if __name__ == "__main__":
    main()
