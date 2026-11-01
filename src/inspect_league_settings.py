
"""Inspect the scoring rules for our Yahoo fantasy league."""

import json
import sys
from pathlib import Path

# Reuse the existing Yahoo API client.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from yahoo_client import yahoo_get
from storage import save_bronze_response

LEAGUE_KEY = "478.l.105854"


def main():
    endpoint = f"/league/{LEAGUE_KEY}/settings"

    print(f"Request: {endpoint}")
    response = yahoo_get(endpoint)

    # Save the original response in the league's Bronze settings folder.
    save_bronze_response(
        response,
        resource="league_settings",
        category="league/settings",
        league_key=LEAGUE_KEY,
        request_endpoint=endpoint,
    )

    content = response.get("fantasy_content", {})
    league_sections = content.get("league", [])

    # Yahoo returns league metadata and settings in separate sections.
    for section in league_sections:
        if not isinstance(section, dict):
            continue

        settings = section.get("settings")
        if settings is None:
            continue

        print("\nSettings keys:")
        if isinstance(settings, dict):
            print(list(settings.keys()))

        print("\nScoring settings response:")
        print(json.dumps(settings, indent=2, ensure_ascii=False)[:12000])
        return

    # Show the response if the settings section wasn't where expected.
    print("\nCould not find the settings section.")
    print(json.dumps(response, indent=2, ensure_ascii=False)[:12000])


if __name__ == "__main__":
    main()
