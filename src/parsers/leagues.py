
"""Extract fantasy league information from Yahoo API responses."""

import json
from pathlib import Path


def extract_leagues(file_path):
    """Extract league metadata from one saved Yahoo response."""
    with Path(file_path).open("r", encoding="utf-8") as file:
        data = json.load(file)

    fantasy_content = data["fantasy_content"]
    user_data = fantasy_content["users"]["0"]["user"]
    games = user_data[1]["games"]

    leagues = []

    for game_index, game_entry in games.items():
        if game_index == "count":
            continue

        game_data = game_entry["game"]
        game_info = game_data[0]
        league_section = game_data[1].get("leagues", {})

        for league_index, league_entry in league_section.items():
            if league_index == "count":
                continue

            league_items = league_entry.get("league", [])

            if isinstance(league_items, list):
                league_info = next(
                    (
                        item for item in league_items
                        if isinstance(item, dict)
                    ),
                    {},
                )
            elif isinstance(league_items, dict):
                league_info = league_items
            else:
                league_info = {}

            leagues.append({
                "sport": game_info.get("code"),
                "season": league_info.get(
                    "season", game_info.get("season")
                ),
                "league_name": league_info.get("name"),
                "league_key": league_info.get("league_key"),
                "num_teams": league_info.get("num_teams"),
                "scoring_type": league_info.get("scoring_type"),
                "draft_status": league_info.get("draft_status"),
                "is_finished": league_info.get("is_finished"),
            })

    return leagues
