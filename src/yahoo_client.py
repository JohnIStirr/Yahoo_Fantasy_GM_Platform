import json
import requests

from paths import PROJECT_ROOT
from storage import save_bronze_response

TOKEN_FILE = PROJECT_ROOT / "tokens.json"
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




def walk_for_key(value, target_key):
    """Find values for a key inside Yahoo's nested response."""
    if isinstance(value, dict):
        if target_key in value:
            yield value[target_key]

        for child in value.values():
            yield from walk_for_key(child, target_key)

    elif isinstance(value, list):
        for child in value:
            yield from walk_for_key(child, target_key)


if __name__ == "__main__":
    league_key = "478.l.105854"

    print(f"\nFetching teams for league {league_key}...")

    # Save the fantasy-team response in the league-specific Bronze layer.
    teams_endpoint = f"/league/{league_key}/teams"
    teams_data = get_teams_by_league(league_key)

    save_bronze_response(
        teams_data,
        resource="fantasy_teams",
        category="league/fantasy_teams",
        league_key=league_key,
        request_endpoint=teams_endpoint,
    )

    # Discover team keys from Yahoo instead of assuming 12 teams.
    team_keys = sorted({
        key
        for key in walk_for_key(teams_data, "team_key")
        if isinstance(key, str)
        and key.startswith(f"{league_key}.t.")
    })

    if not team_keys:
        raise RuntimeError(
            "No fantasy team keys found in Yahoo's response."
        )

    print(f"Found {len(team_keys)} fantasy teams.")

    for team_key in team_keys:
        team_id = team_key.rsplit(".t.", 1)[-1]
        endpoint = f"/team/{team_key}/roster"

        print(f"\nFetching roster for team {team_id}...")

        roster_data = get_roster_by_team(team_key)

        save_bronze_response(
            roster_data,
            resource=f"roster_team_{team_id}",
            category="league/rosters",
            league_key=league_key,
            request_endpoint=endpoint,
        )

    print("\nFinished fetching all fantasy-team rosters.")



