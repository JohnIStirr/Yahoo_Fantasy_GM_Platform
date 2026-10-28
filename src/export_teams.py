
import csv
from pathlib import Path
from inspect_teams import extract_teams

DATA_DIR = Path("data/raw/nba/teams")
OUTPUT_FILE = Path("data/processed/teams.csv")


def main():
    # Find every saved NBA team snapshot.
    team_files = sorted(DATA_DIR.glob("teams_*.json"))
    all_teams = []

    for file_path in team_files:
        all_teams.extend(extract_teams(file_path))

    if not all_teams:
        print("No team records found.")
        return

    # Keep one current record per team if multiple snapshots exist.
    unique_teams = {}
    for team in all_teams:
        unique_teams[team["team_key"]] = team

    all_teams = list(unique_teams.values())

    # Create the output folder if it doesn't exist.
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Write the team records to a CSV file.
    with OUTPUT_FILE.open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        columns = list(all_teams[0].keys())
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(all_teams)

    print(f"Exported {len(all_teams)} teams.")
    print(f"Output file: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
