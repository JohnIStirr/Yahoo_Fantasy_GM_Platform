import json
import requests
from pathlib import Path
from datetime import datetime, timezone

TOKEN_FILE = "tokens.json"

BASE_URL = "https://fantasysports.yahooapis.com/fantasy/v2"


def load_access_token():
    with open(TOKEN_FILE, "r") as f:
        tokens = json.load(f)

    return tokens["access_token"]


def yahoo_get(endpoint):
    access_token = load_access_token()

    url = BASE_URL + endpoint

    response = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {access_token}"
        },
        params={
            "format": "json"
        },
        timeout=30,
    )

    print("HTTP status:", response.status_code)

    if response.status_code != 200:
        print("Yahoo response:")
        print(response.text)
        response.raise_for_status()

    return response.json()

def get_games_by_sport(sport):
    supported_sports = {
        "football": "nfl",
        "basketball": "nba",
    }

    if sport not in supported_sports:
        raise ValueError(f"Unsupported sport: {sport}")

    game_code = supported_sports[sport]

    return yahoo_get(
        f"/users;use_login=1/games;game_codes={game_code}"
    )

def get_user_games():
    data = yahoo_get("/users;use_login=1/games")
    return data




def save_raw_data(data, sport, resource):
    # Create a timestamp so each extraction gets a unique filename.
    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    # Organize raw data by sport and resource type.
    output_dir = Path("data") / "raw" / sport / resource
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build the output filename using the resource and timestamp.
    output_file = output_dir / f"{resource}_{timestamp}.json"

    # Save the original API response so we can process it later.
    with output_file.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

    # Print the file location so we can verify the extraction.
    print(f"Saved raw data to: {output_file}")


def get_leagues_by_sport(sport):
    return yahoo_get(
        f"/users;use_login=1/games;game_codes={sport}/leagues"
    )


def get_teams_by_league(league_key):
    """Fetch all teams belonging to a specific fantasy league."""
    return yahoo_get(
        f"/league/{league_key}/teams"
    )


def get_roster_by_team(team_key):
    """Fetch the current roster for one fantasy team."""

    # Yahoo defaults to the current roster date when date is omitted.
    return yahoo_get(
        f"/team/{team_key}/roster"
    )




if __name__ == "__main__":
    # Identify the NBA league we want to collect data from.
    league_key = "478.l.105854"

    print(f"\nFetching teams for league {league_key}...")

    # Get the team IDs from Yahoo instead of hardcoding team names.
    teams_data = get_teams_by_league(league_key)

    # Team IDs run from 1 to 12 in this league.
    # Each team's key identifies its roster in the API.
    for team_id in range(1, 13):
        team_key = f"{league_key}.t.{team_id}"

        print(f"\nFetching roster for team {team_id}...")

        # Fetch the roster for this team.
        roster_data = get_roster_by_team(team_key)

        # Give each team its own folder so files don't overwrite each other.
        resource_name = f"roster_team_{team_id}"
        save_raw_data(roster_data, "nba", resource_name)

    print("\nFinished fetching all 12 team rosters.")


