
import json
from pathlib import Path


def extract_roster(file_path):
    """Extract player records from one Yahoo Fantasy team roster response."""

    # Load the raw JSON response saved from Yahoo's API.
    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    fantasy_content = data["fantasy_content"]
    team_section = fantasy_content["team"]

    # Find the Yahoo fantasy team key in the team metadata.
    team_key = None
    for item in team_section[0]:
        if isinstance(item, dict) and "team_key" in item:
            team_key = item["team_key"]
            break

    # Locate the roster's player list.
    roster = team_section[1]["roster"]
    players_section = roster["0"]["players"]

    players = []

    # Yahoo stores each player across nested lists and dictionaries.
    for key, player_entry in players_section.items():
        if key == "count":
            continue

        player_parts = player_entry["player"]
        player_info = {}

        # Combine the player's metadata into one dictionary.
        for part in player_parts:
            if isinstance(part, list):
                for item in part:
                    if isinstance(item, dict):
                        player_info.update(item)
            elif isinstance(part, dict):
                player_info.update(part)

        # Extract the player's full name.
        name_info = player_info.get("name", {})
        player_name = (
            name_info.get("full")
            if isinstance(name_info, dict)
            else None
        )

        # Collect all positions the player is eligible to play.
        eligible_positions = player_info.get("eligible_positions", [])
        positions = [
            item["position"]
            for item in eligible_positions
            if isinstance(item, dict) and item.get("position")
        ]

        # Find the player's currently selected fantasy roster slot.
        selected_position = player_info.get("selected_position", [])
        roster_position = None

        for item in selected_position:
            if isinstance(item, dict) and "position" in item:
                roster_position = item["position"]
                break

        # Temporary diagnostic for Tyrese Haliburton.
        if player_info.get("player_key") == "478.p.6404":
            print("Raw selected_position:", repr(selected_position))
            print("Parsed roster_position:", repr(roster_position))

        # Store the fields needed for roster analysis.
        players.append({
            "team_key": team_key,
            "player_key": player_info.get("player_key"),
            "player_id": player_info.get("player_id"),
            "player_name": player_name,
            "editorial_team_abbr": player_info.get("editorial_team_abbr"),
            "primary_position": player_info.get("primary_position"),
            "eligible_positions": ",".join(positions),
            "roster_position": roster_position,
        })

    return players


if __name__ == "__main__":
    # Find the saved roster responses for all 12 fantasy teams.
    roster_files = sorted(
        Path("data/raw/nba").glob("roster_team_*/roster_team_*.json")
    )

    all_players = []

    for file_path in roster_files:
        all_players.extend(extract_roster(file_path))

    print(f"\nRoster files found: {len(roster_files)}")
    print(f"Player records extracted: {len(all_players)}")

    # Display a few records to verify the parser.
    for player in all_players[:5]:
        print(player)
