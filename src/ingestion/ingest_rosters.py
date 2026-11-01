"""Ingest fantasy-team metadata and roster snapshots into Bronze."""

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from yahoo_client import get_teams_by_league, get_roster_by_team
from storage import save_bronze_response, save_bronze_run_manifest


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def walk_for_key(value, target_key):
    """Find a field in Yahoo's nested response."""
    if isinstance(value, dict):
        if target_key in value:
            yield value[target_key]
        for child in value.values():
            yield from walk_for_key(child, target_key)
    elif isinstance(value, list):
        for child in value:
            yield from walk_for_key(child, target_key)


def extract_team_keys(response, league_key):
    prefix = f"{league_key}.t."
    keys = {
        value for value in walk_for_key(response, "team_key")
        if isinstance(value, str) and value.startswith(prefix)
    }
    return sorted(keys, key=lambda key: int(key.rsplit(".t.", 1)[-1]))


def main():
    parser = argparse.ArgumentParser(
        description="Ingest all fantasy-team rosters for one Yahoo league."
    )
    parser.add_argument("--league-key", required=True)
    args = parser.parse_args()

    league_key = args.league_key
    run_id = uuid.uuid4().hex[:12]
    category = "league/rosters"
    manifest = {
        "run_id": run_id,
        "status": "running",
        "league_key": league_key,
        "started_at_utc": utc_now(),
        "completed_at_utc": None,
        "team_count_discovered": 0,
        "roster_count_saved": 0,
        "roster_player_count_by_team": {},
        "error": None,
    }
    manifest_options = {
        "resource": f"roster_snapshot_{run_id}",
        "category": category,
        "league_key": league_key,
    }
    save_bronze_run_manifest(manifest, **manifest_options)

    try:
        teams_endpoint = f"/league/{league_key}/teams"
        teams_response = get_teams_by_league(league_key)
        team_keys = extract_team_keys(teams_response, league_key)
        if not team_keys:
            raise ValueError("No fantasy team keys found in Yahoo response")

        save_bronze_response(
            teams_response,
            resource=f"fantasy_teams_{run_id}",
            category="league/fantasy_teams",
            league_key=league_key,
            request_endpoint=teams_endpoint,
            ingestion_run_id=run_id,
        )
        manifest["team_count_discovered"] = len(team_keys)

        for team_key in team_keys:
            team_id = team_key.rsplit(".t.", 1)[-1]
            endpoint = f"/team/{team_key}/roster"
            print(f"Fetching roster for fantasy team {team_id}...")
            response = get_roster_by_team(team_key)

            # Count player keys as an initial completeness diagnostic.
            player_keys = {
                value for value in walk_for_key(response, "player_key")
                if isinstance(value, str) and ".p." in value
            }
            if not player_keys:
                raise ValueError(
                    f"Roster response for team {team_id} has no player keys"
                )

            save_bronze_response(
                response,
                resource=f"roster_team_{team_id}_{run_id}",
                category=category,
                league_key=league_key,
                request_endpoint=endpoint,
                ingestion_run_id=run_id,
            )
            manifest["roster_count_saved"] += 1
            manifest["roster_player_count_by_team"][team_id] = len(player_keys)

        if manifest["roster_count_saved"] != len(team_keys):
            raise RuntimeError("Not all discovered team rosters were saved")

        manifest["status"] = "complete"
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        manifest["completed_at_utc"] = utc_now()
        save_bronze_run_manifest(manifest, **manifest_options)

    print("\nRoster ingestion summary")
    print(f"Run ID: {run_id}")
    print(f"League: {league_key}")
    print(f"Teams discovered: {manifest['team_count_discovered']}")
    print(f"Rosters saved: {manifest['roster_count_saved']}")
    print(f"Rostered player records: {sum(manifest['roster_player_count_by_team'].values())}")
    print(f"Status: {manifest['status']}")


if __name__ == "__main__":
    main()
