"""Ingest Yahoo Fantasy free-agent and waiver responses into Bronze."""

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from yahoo_client import yahoo_get
from storage import save_bronze_response, save_bronze_run_manifest

AVAILABILITY_CATEGORY = "league/player_availability"
STATUSES = ("FA", "W")
DEFAULT_PAGE_SIZE = 25


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def numbered_player_entries(players):
    indexes = [key for key in players if str(key).isdigit()]
    return [players[key] for key in sorted(indexes, key=lambda key: int(key))]



def get_player_entries(response):
    """Extract player records from Yahoo's nested response."""
    content = response.get("fantasy_content", {})

    if not isinstance(content, dict):
        raise ValueError(
            "Yahoo response has no valid fantasy_content object."
        )

    players = content.get("players")

    # Yahoo can return an empty list when no players are available.
    if isinstance(players, list):
        if not players:
            return []

        raise ValueError(
            "Unexpected non-empty players list in Yahoo response."
        )

    # Some Yahoo responses put players directly under fantasy_content.
    if isinstance(players, dict):
        return numbered_player_entries(players)

    # League player searches place players inside a league section.
    league_sections = content.get("league", [])

    if isinstance(league_sections, list):
        for section in league_sections:
            if not isinstance(section, dict):
                continue

            if "players" not in section:
                continue

            players = section["players"]

            # An empty list means Yahoo returned no matching players.
            if isinstance(players, list):
                if not players:
                    return []

                raise ValueError(
                    "Unexpected non-empty players list."
                )

            if isinstance(players, dict):
                return numbered_player_entries(players)

            raise ValueError(
                f"Unexpected Yahoo players format: "
                f"{type(players).__name__}"
            )

    raise ValueError(
        "Could not locate the players section in Yahoo's response."
    )


def extract_player_key(entry):
    for part in entry.get("player", []):
        if isinstance(part, list):
            for item in part:
                if isinstance(item, dict) and item.get("player_key"):
                    return item["player_key"]
    return None


def fetch_status(league_key, status, run_id, page_size):
    start = 0
    pages = 0
    records = 0
    player_keys = set()
    missing_keys = 0

    while True:
        endpoint = (
            f"/league/{league_key}/players"
            f";status={status};start={start};count={page_size}"
        )
        print(f"Fetching {status}: start={start}, count={page_size}")
        response = yahoo_get(endpoint)
        resource = f"availability_{status.lower()}_{run_id}_start_{start}"

        save_bronze_response(
            response,
            resource=resource,
            category=AVAILABILITY_CATEGORY,
            league_key=league_key,
            request_endpoint=endpoint,
            ingestion_run_id=run_id,
        )

        entries = get_player_entries(response)
        pages += 1
        records += len(entries)

        for entry in entries:
            key = extract_player_key(entry)
            if key:
                player_keys.add(key)
            else:
                missing_keys += 1

        print(f"  Records returned: {len(entries)}")
        if len(entries) < page_size:
            break
        start += len(entries)

    return {
        "page_count": pages,
        "record_count": records,
        "unique_player_count": len(player_keys),
        "missing_player_key_count": missing_keys,
        "player_keys": player_keys,
    }


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Ingest free-agent and waiver players into Bronze."
    )
    parser.add_argument("--league-key", required=True)
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    args = parser.parse_args()
    if args.page_size < 1:
        parser.error("--page-size must be greater than zero")
    return args


def main():
    args = parse_arguments()
    run_id = uuid.uuid4().hex[:12]
    started_at = utc_now()
    manifest = {
        "run_id": run_id,
        "status": "running",
        "league_key": args.league_key,
        "requested_statuses": list(STATUSES),
        "page_size": args.page_size,
        "started_at_utc": started_at,
        "completed_at_utc": None,
        "status_results": {},
        "total_records_returned": 0,
        "unique_player_count": 0,
        "overlap_between_statuses": 0,
        "missing_player_key_count": 0,
        "error": None,
    }
    manifest_options = {
        "resource": f"availability_{run_id}",
        "category": AVAILABILITY_CATEGORY,
        "league_key": args.league_key,
    }
    save_bronze_run_manifest(manifest, **manifest_options)

    try:
        results = {
            status: fetch_status(
                args.league_key, status, run_id, args.page_size
            )
            for status in STATUSES
        }
        overlap = results["FA"]["player_keys"] & results["W"]["player_keys"]
        all_keys = set().union(*(item["player_keys"] for item in results.values()))

        manifest["status_results"] = {
            status: {
                key: value
                for key, value in result.items()
                if key != "player_keys"
            }
            for status, result in results.items()
        }
        manifest["total_records_returned"] = sum(
            item["record_count"] for item in results.values()
        )
        manifest["unique_player_count"] = len(all_keys)
        manifest["overlap_between_statuses"] = len(overlap)
        manifest["missing_player_key_count"] = sum(
            item["missing_player_key_count"] for item in results.values()
        )
        manifest["quality_warnings"] = []

        if overlap:
            manifest["quality_warnings"].append(
                f"{len(overlap)} players appeared in both FA and W results."
            )
        if manifest["missing_player_key_count"]:
            manifest["quality_warnings"].append(
                "Some returned records had no player_key."
            )

        # A successful HTTP collection can still have data-quality warnings.
        manifest["status"] = (
            "complete" if not manifest["missing_player_key_count"] else "incomplete"
        )
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        manifest["completed_at_utc"] = utc_now()
        save_bronze_run_manifest(manifest, **manifest_options)

    print("\nAvailability ingestion summary")
    print(f"Run ID: {run_id}")
    print(f"Status: {manifest['status']}")
    print(f"Records returned: {manifest['total_records_returned']}")
    print(f"Unique players: {manifest['unique_player_count']}")
    print(f"Duplicate players between FA/W: {manifest['overlap_between_statuses']}")
    print(f"Records missing player keys: {manifest['missing_player_key_count']}")

    if manifest["status"] != "complete":
        raise SystemExit("Availability run is incomplete; do not build Silver from it.")


if __name__ == "__main__":
    main()
