
"""Test Yahoo Fantasy player rankings for different time periods."""

import json
import sys
from pathlib import Path

# Let this script import the existing Yahoo client.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from yahoo_client import yahoo_get
from storage import save_experiment_response

LEAGUE_KEY = "478.l.105854"

# Test yesterday, last week, and last month.
REPORTS = [
    (
        "yesterday_top5",
        "date",
        "2026-10-27",
        5,
    ),
    (
        "lastweek_top10",
        "lastweek",
        None,
        10,
    ),
    (
        "lastmonth_top20",
        "lastmonth",
        None,
        20,
    ),
]



def find_player_entries(response):
    """Find player records in Yahoo's nested response."""
    content = response.get("fantasy_content", {})

    for section in content.get("league", []):
        if not isinstance(section, dict):
            continue

        # Skip league metadata sections without player data.
        players = section.get("players")

        if not isinstance(players, dict):
            continue

        indexes = [
            key for key in players
            if str(key).isdigit()
        ]

        # Keep searching if this section has no player records.
        if not indexes:
            continue

        return [
            players[key]
            for key in sorted(indexes, key=lambda x: int(x))
        ]

    return []

def main():
    for report_name, sort_type, sort_date, count in REPORTS:
        # Build the request for the selected time period.
        endpoint = (
            f"/league/{LEAGUE_KEY}/players"
            f";sort=PTS;sort_type={sort_type}"
        )

        if sort_date:
            endpoint += f";sort_date={sort_date}"

        endpoint += f";start=0;count={count};out=stats"

        print(f"\nTesting report: {report_name}")
        print(f"Request: {endpoint}")

        response = yahoo_get(endpoint)

        # Save the raw response so we can inspect it later.
        save_experiment_response(
            response,
            experiment="leaderboards",
            resource=report_name,
            request_endpoint=endpoint,
        )

        entries = find_player_entries(response)

        print(f"Player records returned: {len(entries)}")

        # Print the first player to inspect the stats structure.
        if entries:
            print("First player response:")
            print(
                json.dumps(
                    entries[0],
                    indent=2,
                    ensure_ascii=False,
                )[:5000]
            )
        else:
            print("No player records found in the response.")


if __name__ == "__main__":
    main()
