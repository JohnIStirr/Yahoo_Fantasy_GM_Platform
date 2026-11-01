
"""Print a compact table of our league's fantasy scoring rules."""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_DIR = PROJECT_ROOT / "data" / "raw" / "nba" / "league_settings"


def main():
    # Read the latest saved Yahoo league-settings response.
    files = sorted(SETTINGS_DIR.glob("league_settings_*.json"))

    if not files:
        raise FileNotFoundError(
            f"No saved league settings found in {SETTINGS_DIR}"
        )

    with files[-1].open("r", encoding="utf-8") as file:
        response = json.load(file)

    # Find the settings object inside Yahoo's nested response.
    sections = response["fantasy_content"]["league"]
    settings_list = next(
        section["settings"]
        for section in sections
        if isinstance(section, dict) and "settings" in section
    )
    settings = settings_list[0]

    # Map every stat ID to its display name and abbreviation.
    stat_names = {}

    categories = settings.get("stat_categories", {}).get("stats", [])
    for item in categories:
        stat = item.get("stat", {})
        stat_id = str(stat.get("stat_id", ""))

        stat_names[stat_id] = {
            "name": stat.get("name", ""),
            "abbr": stat.get("abbr", stat.get("display_name", "")),
        }

    # Print each scoring modifier with its corresponding stat.
    modifiers = settings.get("stat_modifiers", {}).get("stats", [])

    print(f"Scoring type: {settings.get('scoring_label')}")
    print("\nStat ID | Abbreviation | Statistic | Fantasy points per stat")
    print("-" * 76)

    for item in modifiers:
        stat = item.get("stat", {})
        stat_id = str(stat.get("stat_id", ""))
        info = stat_names.get(stat_id, {})

        print(
            f"{stat_id:>7} | "
            f"{info.get('abbr', 'Unknown'):<12} | "
            f"{info.get('name', 'Unknown'):<25} | "
            f"{float(stat.get('value', 0)):>8.2f}"
        )


if __name__ == "__main__":
    main()
