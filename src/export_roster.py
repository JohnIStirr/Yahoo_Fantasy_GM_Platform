
import csv
import sys
from pathlib import Path

# Ensure Python imports the parser from this project's src directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from inspect_roster import extract_roster


DATA_DIR = Path("data/raw/nba")
OUTPUT_FILE = Path("data/processed/nba_rosters.csv")


def main():
    # Find all saved roster responses for the 12 fantasy teams.
    roster_files = sorted(
        DATA_DIR.glob("roster_team_*/roster_team_*.json")
    )

    all_players = []

    # Parse each team's roster into structured player records.
    for file_path in roster_files:
        players = extract_roster(file_path)
        all_players.extend(players)

    if not all_players:
        print("No player records found.")
        return

    # Remove duplicate records for the same player on the same team.
    unique_players = {}
    for player in all_players:
        key = (player["team_key"], player["player_key"])
        unique_players[key] = player

    all_players = list(unique_players.values())

    # Create the output directory if necessary.
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Write the data to a CSV that Excel can open.
    with OUTPUT_FILE.open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        columns = list(all_players[0].keys())
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(all_players)

    print(f"Roster files found: {len(roster_files)}")
    print(f"Unique player-team records: {len(all_players)}")
    print(f"Output file: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
