
"""Inspect a saved Yahoo leaderboard response."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "nba"
REPORT_FOLDER = DATA_DIR / "yesterday_top5"

# Find the newest saved response for this report.
files = sorted(REPORT_FOLDER.glob("yesterday_top5_*.json"))

if not files:
    print(f"No response files found in {REPORT_FOLDER}")
    raise SystemExit(1)

response_file = files[-1]
print(f"Reading: {response_file}")

with response_file.open("r", encoding="utf-8") as file:
    response = json.load(file)

# Inspect the response structure before trying to extract players.
print("\nTop-level keys:")
print(list(response.keys()) if isinstance(response, dict) else type(response).__name__)

content = response.get("fantasy_content", {})
print("\nFantasy content type:", type(content).__name__)

if isinstance(content, dict):
    print("Fantasy content keys:", list(content.keys()))

    league = content.get("league")
    print("\nLeague value type:", type(league).__name__)

    if isinstance(league, list):
        for index, section in enumerate(league):
            if isinstance(section, dict):
                print(f"League section {index} keys:", list(section.keys()))
            else:
                print(f"League section {index} type:", type(section).__name__)

    elif isinstance(league, dict):
        print("League keys:", list(league.keys()))

    # Show the response opening, which may reveal an API message.
    print("\nResponse preview:")
    print(json.dumps(response, indent=2, ensure_ascii=False)[:5000])

else:
    print("\nUnexpected fantasy_content value:")
    print(repr(content))
