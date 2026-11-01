
"""Test Yahoo player statistics for a specified player and date."""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

# Allow imports from the src directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from yahoo_client import yahoo_get
from storage import save_experiment_response


def parse_arguments():
    """Read the player key and game date from the command line."""
    parser = argparse.ArgumentParser(
        description="Fetch a player's Yahoo Fantasy stats for one date."
    )

    parser.add_argument(
        "--player-key",
        required=True,
        help="Yahoo player key, for example 478.p.6014",
    )
    parser.add_argument(
        "--date",
        required=True,
        help="Statistical date in YYYY-MM-DD format",
    )

    args = parser.parse_args()

    # Validate the date before making an API request.
    try:
        date.fromisoformat(args.date)
    except ValueError:
        parser.error("--date must use YYYY-MM-DD format")

    # Validate the expected Yahoo player-key format.
    if not re.fullmatch(r"\d+\.p\.\d+", args.player_key):
        parser.error("--player-key must look like 478.p.6014")

    return args


def main():
    args = parse_arguments()

    # Construct the request from the supplied inputs.
    endpoint = (
        f"/player/{args.player_key}/stats"
        f";type=date;date={args.date}"
    )

    print(f"Player key: {args.player_key}")
    print(f"Stat date: {args.date}")
    print(f"Request: {endpoint}")

    response = yahoo_get(endpoint)

    # Save the response as an experiment, not production Bronze data.
    resource = (
        f"player_date_stats_{args.player_key.replace('.', '_')}"
        f"_{args.date}"
    )

    save_experiment_response(
        response,
        experiment="player_date_stats",
        resource=resource,
        request_endpoint=endpoint,
    )

    # Print a response preview for inspection.
    print("\nResponse preview:")
    print(json.dumps(response, indent=2, ensure_ascii=False)[:6000])


if __name__ == "__main__":
    main()
