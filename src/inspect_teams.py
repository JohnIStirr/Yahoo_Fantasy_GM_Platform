
import json
from pathlib import Path


def extract_teams(file_path):
    """Extract team metadata and manager details from a Yahoo API response."""

    # Load the original Yahoo Fantasy JSON response.
    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    fantasy_content = data["fantasy_content"]
    league_sections = fantasy_content["league"]

    # The first item contains league metadata; the second contains teams.
    team_section = league_sections[1]["teams"]
    teams = []

    # Each numbered key represents one team; skip the count field.
    for key, team_entry in team_section.items():
        if key == "count":
            continue

        # The team data is a list containing dictionaries and empty lists.
        team_parts = team_entry["team"][0]
        team_info = {}

        # Combine the dictionaries so each field can be accessed by name.
        for part in team_parts:
            if isinstance(part, dict):
                team_info.update(part)

        # Extract manager details if Yahoo returned them.
        managers = team_info.get("managers", [])
        manager_info = managers[0].get("manager", {}) if managers else {}

        teams.append({
            "league_key": fantasy_content["league"][0]["league_key"],
            "team_key": team_info.get("team_key"),
            "team_id": team_info.get("team_id"),
            "team_name": team_info.get("name"),
            "manager_nickname": manager_info.get("nickname"),
            "waiver_priority": team_info.get("waiver_priority"),
            "number_of_moves": team_info.get("number_of_moves"),
            "number_of_trades": team_info.get("number_of_trades"),
            "auction_budget_total": team_info.get("auction_budget_total"),
            "auction_budget_spent": team_info.get("auction_budget_spent"),
            "previous_season_team_rank": team_info.get(
                "previous_season_team_rank"
            ),
            "team_url": team_info.get("url"),
        })

    return teams


if __name__ == "__main__":
    # Find saved team snapshots and inspect the latest one.
    files = sorted(
        Path("data/raw/nba/teams").glob("teams_*.json")
    )

    if not files:
        print("No team JSON files found. Fetch and save team data first.")
    else:
        teams = extract_teams(files[-1])
        print(f"Extracted {len(teams)} teams.")

        # Print a small sample to verify the parser.
        for team in teams[:3]:
            print(team)
