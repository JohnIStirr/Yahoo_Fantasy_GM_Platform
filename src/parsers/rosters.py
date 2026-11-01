
"""Extract player and roster information from Yahoo responses."""

import json
from pathlib import Path


def extract_roster(file_path):
    """Extract player records from one Yahoo fantasy roster response."""
    with Path(file_path).open("r", encoding="utf-8") as file:
        data = json.load(file)

    fantasy_content = data["fantasy_content"]
    team_section = fantasy_content["team"]

    # Find the fantasy team key.
    team_key = None

    for item in team_section[0]:
        if isinstance(item, dict) and "team_key" in item:
            team_key = item["team_key"]
            break

    # Locate the roster player collection.
    roster = team_section[1]["roster"]
    players_section = roster["0"]["players"]

    players = []

    for key, player_entry in players_section.items():
        if key == "count":
            continue

        player_parts = player_entry["player"]
        player_info = {}

        # Combine nested player dictionaries into one record.
        for part in player_parts:
            if isinstance(part, list):
                for item in part:
                    if isinstance(item, dict):
                        player_info.update(item)

            elif isinstance(part, dict):
                player_info.update(part)

        name_info = player_info.get("name", {})
        player_name = (
            name_info.get("full")
            if isinstance(name_info, dict)
            else None
        )

        eligible_positions = player_info.get(
            "eligible_positions", []
        )

        positions = [
            item["position"]
            for item in eligible_positions
            if isinstance(item, dict) and item.get("position")
        ]

        selected_position = player_info.get(
            "selected_position", []
        )

        roster_position = None

        for item in selected_position:
            if isinstance(item, dict) and "position" in item:
                roster_position = item["position"]
                break

        players.append({
            "team_key": team_key,
            "player_key": player_info.get("player_key"),
            "player_id": player_info.get("player_id"),
            "player_name": player_name,
            "editorial_team_abbr": player_info.get(
                "editorial_team_abbr"
            ),
            "primary_position": player_info.get(
                "primary_position"
            ),
            "eligible_positions": ",".join(positions),
            "roster_position": roster_position,
        })

    return players
