
"""Extract fantasy-team information from Yahoo responses."""

import json
from pathlib import Path


def extract_teams(file_path):
    """Extract fantasy-team metadata and manager information."""
    with Path(file_path).open("r", encoding="utf-8") as file:
        data = json.load(file)

    fantasy_content = data["fantasy_content"]
    league_sections = fantasy_content.get("league", [])

    # Find league metadata and the team collection.
    league_key = None
    team_section = None

    for section in league_sections:
        if not isinstance(section, dict):
            continue

        if league_key is None:
            league_key = section.get("league_key")

        if "teams" in section:
            team_section = section["teams"]
            break

    if not isinstance(team_section, dict):
        raise ValueError("Could not find a valid teams section.")

    teams = []

    for key, team_entry in team_section.items():
        if key == "count":
            continue

        team_container = team_entry.get("team", [])

        if not team_container:
            continue

        team_parts = team_container[0]
        team_info = {}

        for part in team_parts:
            if isinstance(part, dict):
                team_info.update(part)

        managers = team_info.get("managers", [])
        manager_info = {}

        if isinstance(managers, list) and managers:
            first_manager = managers[0]

            if isinstance(first_manager, dict):
                manager_info = first_manager.get("manager", {})

        teams.append({
            "league_key": league_key,
            "team_key": team_info.get("team_key"),
            "team_id": team_info.get("team_id"),
            "team_name": team_info.get("name"),
            "manager_nickname": manager_info.get("nickname"),
            "waiver_priority": team_info.get("waiver_priority"),
            "number_of_moves": team_info.get("number_of_moves"),
            "number_of_trades": team_info.get("number_of_trades"),
            "auction_budget_total": team_info.get(
                "auction_budget_total"
            ),
            "auction_budget_spent": team_info.get(
                "auction_budget_spent"
            ),
            "previous_season_team_rank": team_info.get(
                "previous_season_team_rank"
            ),
            "team_url": team_info.get("url"),
        })

    return teams
