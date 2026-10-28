
import json
from pathlib import Path
from pprint import pprint

# Load one saved roster response.
files = sorted(
    Path("data/raw/nba").glob("roster_team_*/roster_team_*.json")
)

if not files:
    print("No roster files found.")
else:
    with files[0].open("r", encoding="utf-8") as file:
        data = json.load(file)

    fantasy_content = data["fantasy_content"]

    # Show the top-level structure without printing the entire response.
    print("Top-level fantasy_content keys:")
    print(list(fantasy_content.keys()))

    # Inspect how Yahoo stores the team and roster sections.
    print("\nTeam section structure:")
    pprint(fantasy_content.get("team"), depth=4)

    # Find and inspect the roster section.
    def find_roster(obj):
        if isinstance(obj, dict):
            if "roster" in obj:
                return obj["roster"]

            for value in obj.values():
                result = find_roster(value)
                if result is not None:
                    return result

        elif isinstance(obj, list):
            for value in obj:
                result = find_roster(value)
                if result is not None:
                    return result

        return None

    roster = find_roster(fantasy_content)

    print("\nRoster section keys:")
    print(list(roster.keys()) if isinstance(roster, dict) else type(roster))

    print("\nRoster structure:")
    pprint(roster, depth=5)
