
"""Build a unified player pool for the fantasy basketball league."""

import csv
import sys
from collections import Counter
from pathlib import Path

# Make the existing Yahoo client available to this script.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from yahoo_client import yahoo_get, save_raw_data


# Find project folders relative to this script.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ROSTER_FILE = PROJECT_ROOT / "data" / "processed" / "nba_rosters.csv"
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "nba_player_pool.csv"

LEAGUE_KEY = "478.l.105854"
PAGE_SIZE = 25

COLUMNS = [
    "player_key",
    "player_id",
    "player_name",
    "nba_team_abbr",
    "nba_team_name",
    "primary_position",
    "eligible_positions",
    "injury_status",
    "injury_status_full",
    "injury_note",
    "availability_status",
    "fantasy_team_key",
    "roster_position",
]


def flatten_fields(value, fields=None):
    """Collect player fields from Yahoo's nested response format."""
    if fields is None:
        fields = {}

    if isinstance(value, dict):
        for key, item in value.items():
            # Keep the first occurrence of each field.
            fields.setdefault(key, item)

            if isinstance(item, (dict, list)):
                flatten_fields(item, fields)

    elif isinstance(value, list):
        for item in value:
            flatten_fields(item, fields)

    return fields


def get_player_entries(response):
    """Locate individual player records in a Yahoo API response."""
    fantasy_content = response.get("fantasy_content", {})
    league_sections = fantasy_content.get("league", [])

    for section in league_sections:
        if not isinstance(section, dict):
            continue

        players = section.get("players")
        if not isinstance(players, dict):
            continue

        # Yahoo numbers the player records as "0", "1", "2", etc.
        player_indexes = [
            key for key in players
            if str(key).isdigit()
        ]

        return [
            players[key]
            for key in sorted(player_indexes, key=lambda x: int(x))
        ]

    return []


def normalize_player(entry, availability_status):
    """Convert one Yahoo player record into a consistent row."""
    player_data = entry.get("player", [])
    fields = flatten_fields(player_data)

    name_data = fields.get("name", {})
    if not isinstance(name_data, dict):
        name_data = {}

    eligible = fields.get("eligible_positions", [])
    if isinstance(eligible, list):
        positions = [
            item["position"]
            for item in eligible
            if isinstance(item, dict) and item.get("position")
        ]
    else:
        positions = []

    return {
        "player_key": fields.get("player_key", ""),
        "player_id": fields.get("player_id", ""),
        "player_name": name_data.get("full", ""),
        "nba_team_abbr": fields.get("editorial_team_abbr", ""),
        "nba_team_name": fields.get("editorial_team_full_name", ""),
        "primary_position": fields.get("primary_position", ""),
        "eligible_positions": ",".join(positions),
        "injury_status": fields.get("status", ""),
        "injury_status_full": fields.get("status_full", ""),
        "injury_note": fields.get("injury_note", ""),
        "availability_status": availability_status,
        "fantasy_team_key": "",
        "roster_position": "",
    }


def fetch_available_players(status):
    """Fetch every page of free agents or waiver players."""
    all_players = []
    start = 0

    while True:
        endpoint = (
            f"/league/{LEAGUE_KEY}/players"
            f";status={status};start={start};count={PAGE_SIZE}"
        )

        print(f"Fetching {status} players starting at {start}...")

        response = yahoo_get(endpoint)

        # Save each page so the original response is available for debugging.
        resource = f"available_players_{status.lower()}_start_{start}"
        save_raw_data(response, "nba", resource)

        entries = get_player_entries(response)
        print(f"  Records returned: {len(entries)}")

        for entry in entries:
            player = normalize_player(entry, status)

            # Skip malformed records without a stable player identifier.
            if player["player_key"]:
                all_players.append(player)

        # A short page means there are no more records to fetch.
        if len(entries) < PAGE_SIZE:
            break

        start += len(entries)

    return all_players


def load_rostered_players():
    """Load the existing roster dataset without calling the API again."""
    if not ROSTER_FILE.exists():
        raise FileNotFoundError(
            f"Roster CSV not found: {ROSTER_FILE}\n"
            "Run src/export_rosters.py first."
        )

    rostered_players = []

    with ROSTER_FILE.open(
        "r", newline="", encoding="utf-8-sig"
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            player_key = row.get("player_key", "")
            if not player_key:
                continue

            rostered_players.append({
                "player_key": player_key,
                "player_id": row.get("player_id", ""),
                "player_name": row.get("player_name", ""),
                "nba_team_abbr": row.get("editorial_team_abbr", ""),
                "nba_team_name": "",
                "primary_position": row.get("primary_position", ""),
                "eligible_positions": row.get("eligible_positions", ""),
                "injury_status": "",
                "injury_status_full": "",
                "injury_note": "",
                "availability_status": "ROSTERED",
                "fantasy_team_key": row.get("team_key", ""),
                "roster_position": row.get("roster_position", ""),
            })

    return rostered_players


def main():
    # Rostered players are loaded from our existing dataset.
    rostered_players = load_rostered_players()

    # Fetch free agents and waiver players from Yahoo.
    available_players = []
    available_players.extend(fetch_available_players("FA"))
    available_players.extend(fetch_available_players("W"))

    # Use player_key to make one row per player.
    player_pool = {}

    for player in rostered_players:
        player_pool[player["player_key"]] = player

    duplicate_available_records = 0

    for player in available_players:
        key = player["player_key"]

        if key in player_pool:
            # Keep the roster record if the player is already rostered.
            duplicate_available_records += 1
            continue

        player_pool[key] = player

    # Write the standardized player dataset.
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(player_pool.values())

    # Print basic data-quality checks.
    players = list(player_pool.values())
    status_counts = Counter(
        player["availability_status"] for player in players
    )

    missing_names = sum(
        not player["player_name"] for player in players
    )

    print("\nPlayer pool built successfully.")
    print(f"Rostered records loaded: {len(rostered_players)}")
    print(f"Available-player records fetched: {len(available_players)}")
    print(f"Duplicate records skipped: {duplicate_available_records}")
    print(f"Unique players in output: {len(players)}")
    print(f"Players missing names: {missing_names}")
    print(f"Availability breakdown: {dict(status_counts)}")
    print(f"Output file: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
