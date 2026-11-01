
import csv
from pathlib import Path

from parsers.leagues import extract_leagues


# Read raw data and save the combined league summary here.
DATA_DIR = Path("data/raw")
OUTPUT_FILE = Path("data/processed/leagues.csv")


def main():
    # Find every saved league response for both sports.
    league_files = sorted(DATA_DIR.glob("*/leagues/*.json"))

    all_leagues = []
        
    # Extract league records from every saved API response.
    for file_path in league_files:
        all_leagues.extend(extract_leagues(file_path))

    # Keep only one record per league key.
    # If a league appears in multiple snapshots, retain the last one.
    unique_leagues = {}

    for league in all_leagues:
        unique_leagues[league["league_key"]] = league

    all_leagues = list(unique_leagues.values())


    if not all_leagues:
        print("No league records found.")
        return

    # Create the output folder if it doesn't exist yet.
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Use the fields from the first record as CSV columns.
    columns = list(all_leagues[0].keys())

    # Write the structured league data into a CSV file.
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(all_leagues)

    print(f"Exported {len(all_leagues)} league records.")
    print(f"Output file: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
