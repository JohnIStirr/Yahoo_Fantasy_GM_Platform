"""Ingest date-specific player stats into Bronze without transforming them."""

import argparse
import json
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from yahoo_client import yahoo_get
from storage import save_bronze_response, save_bronze_run_manifest
from paths import bronze_resource_dir

ROSTER_CATEGORY = "league/rosters"
AVAILABILITY_CATEGORY = "league/player_availability"
STATS_CATEGORY = "players/stats"
DEFAULT_BATCH_SIZE = 25


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def numbered_entries(container):
    indexes = [key for key in container if str(key).isdigit()]
    return [container[key] for key in sorted(indexes, key=lambda key: int(key))]


def walk_for_key(value, key_name):
    """Find values for a field throughout nested Yahoo JSON."""
    if isinstance(value, dict):
        if key_name in value:
            yield value[key_name]
        for child in value.values():
            yield from walk_for_key(child, key_name)
    elif isinstance(value, list):
        for child in value:
            yield from walk_for_key(child, key_name)


def latest_complete_manifest(category, league_key):
    """Find the newest successfully completed run for one category."""
    directory = bronze_resource_dir(category, league_key=league_key)
    if not directory.exists():
        raise FileNotFoundError(
            f"No Bronze data directory exists for {category}: {directory}"
        )

    candidates = []
    for path in directory.glob("*.run.json"):
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        if (
            manifest.get("league_key") == league_key
            and manifest.get("status") == "complete"
            and manifest.get("run_id")
        ):
            candidates.append((
                manifest.get("completed_at_utc")
                or manifest.get("recorded_at_utc", ""),
                manifest,
                path,
            ))

    if not candidates:
        raise RuntimeError(
            f"No complete run manifest found for {category}. "
            "Run its Bronze ingestion first."
        )

    _, manifest, path = max(candidates, key=lambda item: item[0])
    print(f"Using {category} snapshot: {path.name}")
    return manifest


def payload_files_for_run(directory, run_id):
    """Find raw payload files associated with a particular ingestion run."""
    found = set()

    # Sidecar metadata is the preferred link between a run and its payloads.
    for metadata_path in directory.glob("*.metadata.json"):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        resource = str(metadata.get("resource", ""))
        if (
            metadata.get("ingestion_run_id") != run_id
            and run_id not in resource
        ):
            continue

        payload_name = metadata.get("payload_file")
        payload_path = directory / payload_name if payload_name else Path(
            str(metadata_path).replace(".metadata.json", ".json")
        )
        if payload_path.is_file():
            found.add(payload_path)

    # Compatibility fallback for early runs whose metadata lacked run IDs.
    if not found:
        for payload_path in directory.glob(f"*{run_id}*.json"):
            if payload_path.name.endswith((".metadata.json", ".run.json")):
                continue
            if payload_path.is_file():
                found.add(payload_path)

    return sorted(found)


def player_keys_from_run(category, league_key, manifest):
    """Collect player keys from the payloads of a completed snapshot."""
    directory = bronze_resource_dir(category, league_key=league_key)
    run_id = manifest["run_id"]
    payloads = payload_files_for_run(directory, run_id)

    if not payloads:
        raise RuntimeError(
            f"No raw payloads were linked to run {run_id} in {directory}"
        )

    keys = set()
    for payload_path in payloads:
        try:
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Could not read {payload_path}: {exc}") from exc

        for value in walk_for_key(payload, "player_key"):
            if isinstance(value, str) and ".p." in value:
                keys.add(value)

    return keys, len(payloads)


def get_player_entries(response):
    """Extract numbered player records from a batch response."""
    content = response.get("fantasy_content", {})
    players = content.get("players") if isinstance(content, dict) else None
    if not isinstance(players, dict):
        raise ValueError("Yahoo response did not contain a players dictionary")
    return numbered_entries(players)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Fetch daily Yahoo player stats for the player universe in the "
            "latest complete availability and roster snapshots."
        )
    )
    parser.add_argument(
        "--league-key", action="append", required=True,
        help=("Yahoo league key to include in player discovery. Repeat this "
              "argument to union players across multiple leagues."),
    )
    parser.add_argument(
        "--date", required=True,
        help="Statistical date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
        help=f"Player keys per request (default: {DEFAULT_BATCH_SIZE}; max: 100).",
    )
    args = parser.parse_args()

    try:
        date.fromisoformat(args.date)
    except ValueError:
        parser.error("--date must be a valid YYYY-MM-DD date")

    if not 1 <= args.batch_size <= 100:
        parser.error("--batch-size must be between 1 and 100")

    return args


def main():
    args = parse_arguments()
    league_keys = sorted(set(args.league_key))
    stat_date = args.date
    run_id = uuid.uuid4().hex[:12]

    # Build a shared player universe from every selected league's latest
    # complete roster and availability snapshots.
    player_keys_union = set()
    source_snapshots = {}
    source_payload_counts = {}

    for league_key in league_keys:
        availability_manifest = latest_complete_manifest(
            AVAILABILITY_CATEGORY, league_key
        )
        roster_manifest = latest_complete_manifest(ROSTER_CATEGORY, league_key)

        available_keys, availability_payload_count = player_keys_from_run(
            AVAILABILITY_CATEGORY, league_key, availability_manifest
        )
        roster_keys, roster_payload_count = player_keys_from_run(
            ROSTER_CATEGORY, league_key, roster_manifest
        )

        player_keys_union.update(available_keys)
        player_keys_union.update(roster_keys)
        source_snapshots[league_key] = {
            "availability_run_id": availability_manifest["run_id"],
            "roster_run_id": roster_manifest["run_id"],
        }
        source_payload_counts[league_key] = {
            "availability_payload_count": availability_payload_count,
            "roster_payload_count": roster_payload_count,
        }

    # A player may occur in several league pools; request that player once.
    player_keys = sorted(player_keys_union)
    if not player_keys:
        raise RuntimeError("No player keys were found in Bronze snapshots")

    batches = [
        player_keys[index:index + args.batch_size]
        for index in range(0, len(player_keys), args.batch_size)
    ]

    manifest = {
        "run_id": run_id,
        "status": "running",
        "league_keys": league_keys,
        "stat_date": stat_date,
        "started_at_utc": utc_now(),
        "completed_at_utc": None,
        "player_key_count": len(player_keys),
        "source_snapshots_by_league": source_snapshots,
        "source_payload_counts_by_league": source_payload_counts,
        "batch_size": args.batch_size,
        "batch_count_expected": len(batches),
        "batch_count_saved": 0,
        "record_count_returned": 0,
        "returned_player_key_count": 0,
        "missing_player_key_count": 0,
        "missing_player_keys_sample": [],
        "error": None,
    }
    manifest_options = {
        "resource": f"player_daily_stats_{stat_date}_{run_id}",
        "category": STATS_CATEGORY,
        # This is a shared NBA statistics collection across the selected leagues.
    }
    save_bronze_run_manifest(manifest, **manifest_options)

    returned_keys = set()
    record_count = 0

    try:
        for batch_number, batch in enumerate(batches, start=1):
            endpoint = (
                f"/players;player_keys={','.join(batch)}"
                f"/stats;type=date;date={stat_date}"
            )
            print(
                f"Batch {batch_number}/{len(batches)}: "
                f"requesting {len(batch)} player stats"
            )
            response = yahoo_get(endpoint)
            resource = (
                f"player_stats_{stat_date}_{run_id}_batch_{batch_number:04d}"
            )

            save_bronze_response(
                response,
                resource=resource,
                category=STATS_CATEGORY,
                request_endpoint=endpoint,
                ingestion_run_id=run_id,
            )

            entries = get_player_entries(response)
            if not entries:
                raise ValueError(f"Batch {batch_number} returned no player entries")

            batch_keys = set()
            for entry in entries:
                for value in walk_for_key(entry, "player_key"):
                    if isinstance(value, str) and ".p." in value:
                        batch_keys.add(value)

            returned_keys.update(batch_keys)
            record_count += len(entries)
            manifest["batch_count_saved"] += 1
            print(f"  Records returned: {len(entries)}")

        missing_keys = set(player_keys) - returned_keys
        manifest["record_count_returned"] = record_count
        manifest["returned_player_key_count"] = len(returned_keys)
        manifest["missing_player_key_count"] = len(missing_keys)
        manifest["missing_player_keys_sample"] = sorted(missing_keys)[:25]

        # A missing response for a requested player makes this run incomplete.
        manifest["status"] = "complete" if not missing_keys else "incomplete"
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        manifest["completed_at_utc"] = utc_now()
        save_bronze_run_manifest(manifest, **manifest_options)

    print("\nDaily player stats ingestion summary")
    print(f"Run ID: {run_id}")
    print(f"Leagues used for player discovery: {', '.join(league_keys)}")
    print(f"Stat date: {stat_date}")
    print(f"Source player keys: {len(player_keys)}")
    print(f"Batches saved: {manifest['batch_count_saved']}/{len(batches)}")
    print(f"Records returned: {record_count}")
    print(f"Players missing responses: {manifest['missing_player_key_count']}")
    print(f"Status: {manifest['status']}")

    if manifest["status"] != "complete":
        raise SystemExit("Stats ingestion is incomplete; do not use it in Silver yet.")


if __name__ == "__main__":
    main()
