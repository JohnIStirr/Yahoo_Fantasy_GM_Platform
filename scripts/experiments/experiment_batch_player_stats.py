
"""Test retrieving daily stats for several players in one API call."""

import json
import sys
from pathlib import Path

# Reuse our existing Yahoo API client.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from yahoo_client import yahoo_get
from storage import save_experiment_response


GAME_DATE = "2026-10-27"

# Test a small batch of players from our existing dataset.
PLAYER_KEYS = [
    "478.p.6014",  # Luka Dončić
    "478.p.6404",  # Tyrese Haliburton
    "478.p.6606",  # Austin Reaves
    "478.p.6395",  # LaMelo Ball
    "478.p.6559",  # Trey Murphy III
]


def main():
    # Request date-specific statistics for all selected players.
    player_keys = ",".join(PLAYER_KEYS)
    endpoint = (
        f"/players;player_keys={player_keys}"
        f"/stats;type=date;date={GAME_DATE}"
    )

    print(f"Requesting daily statistics for {len(PLAYER_KEYS)} players")
    response = yahoo_get(endpoint)

    save_experiment_response(
        response,
        experiment="batch_stats",
        resource="batch_date_stats_test",
        request_endpoint=endpoint,
    )

    content = response.get("fantasy_content", {})
    print("\nFantasy content keys:", list(content.keys()))

    # Inspect how Yahoo groups multiple player records.
    players = content.get("players", {})

    if isinstance(players, dict):
        indexes = [
            key for key in players
            if str(key).isdigit()
        ]

        print("Player records returned:", len(indexes))

        for key in indexes[:2]:
            print(f"\nPlayer record {key}:")
            print(
                json.dumps(
                    players[key],
                    indent=2,
                    ensure_ascii=False,
                )[:3000]
            )
    else:
        print("Unexpected players section:")
        print(json.dumps(content, indent=2, ensure_ascii=False)[:5000])


if __name__ == "__main__":
    main()
