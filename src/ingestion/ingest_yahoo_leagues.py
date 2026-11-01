"""Ingest the authenticated user's Yahoo NBA leagues into Bronze."""

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Allow this script to run directly from the src/ingestion directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from yahoo_client import get_leagues_by_sport
from storage import save_bronze_response, save_bronze_run_manifest


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def walk_for_key(value, target_key):
    """Find a field in Yahoo's nested JSON response."""
    if isinstance(value, dict):
        if target_key in value:
            yield value[target_key]
        for child in value.values():
            yield from walk_for_key(child, target_key)
    elif isinstance(value, list):
        for child in value:
            yield from walk_for_key(child, target_key)


def main():
    parser = argparse.ArgumentParser(
        description="Ingest the authenticated user's Yahoo fantasy leagues."
    )
    parser.add_argument(
        "--sport", choices=["nba"], default="nba",
        help="Yahoo sport code to collect (currently NBA).",
    )
    args = parser.parse_args()

    run_id = uuid.uuid4().hex[:12]
    category = "user/leagues"
    endpoint = f"/users;use_login=1/games;game_codes={args.sport}/leagues"
    manifest = {
        "run_id": run_id,
        "status": "running",
        "sport": args.sport,
        "started_at_utc": utc_now(),
        "completed_at_utc": None,
        "request_count": 1,
        "league_keys_found": [],
        "error": None,
    }
    manifest_options = {
        "resource": f"yahoo_leagues_{run_id}",
        "category": category,
        "sport": args.sport,
    }
    save_bronze_run_manifest(manifest, **manifest_options)

    try:
        response = get_leagues_by_sport(args.sport)
        content = response.get("fantasy_content")
        if not isinstance(content, dict):
            raise ValueError("Yahoo response has no valid fantasy_content object")

        save_bronze_response(
            response,
            resource=f"yahoo_leagues_{run_id}",
            category=category,
            request_endpoint=endpoint,
            ingestion_run_id=run_id,
            sport=args.sport,
        )

        league_keys = sorted({
            value for value in walk_for_key(response, "league_key")
            if isinstance(value, str) and ".l." in value
        })
        manifest["league_keys_found"] = league_keys
        manifest["league_count"] = len(league_keys)
        manifest["status"] = "complete"
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        manifest["completed_at_utc"] = utc_now()
        save_bronze_run_manifest(manifest, **manifest_options)

    print("\nYahoo league ingestion summary")
    print(f"Run ID: {run_id}")
    print(f"Sport: {args.sport}")
    print(f"Leagues found: {manifest.get('league_count', 0)}")
    for key in manifest.get("league_keys_found", []):
        print(f"  {key}")
    print(f"Status: {manifest['status']}")


if __name__ == "__main__":
    main()
