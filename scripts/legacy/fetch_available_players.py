
"""Fetch a small sample of available players from Yahoo Fantasy."""

import json

from yahoo_client import yahoo_get, save_raw_data

# Your current NBA fantasy league.
LEAGUE_KEY = "478.l.105854"

# Start with a small page to verify the API response.
PAGE_SIZE = 25


def main():
    # Free agents and waiver players are fetched separately.
    for status in ["FA", "W"]:
        endpoint = (
            f"/league/{LEAGUE_KEY}/players"
            f";status={status};start=0;count={PAGE_SIZE}"
        )

        print(f"\nFetching players with status: {status}")

        # Fetch and save the original Yahoo response.
        response = yahoo_get(endpoint)
        save_raw_data(
            response,
            "nba",
            f"available_players_{status.lower()}",
        )

        # Print a sample so we can inspect the response structure.
        if isinstance(response, dict):
            print("Top-level keys:", list(response.keys()))
            print(json.dumps(response, indent=2, ensure_ascii=False)[:4000])
        else:
            print("Response type:", type(response).__name__)
            print(str(response)[:4000])


if __name__ == "__main__":
    main()
