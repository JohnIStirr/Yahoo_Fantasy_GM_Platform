"""Ingest one Yahoo fantasy league's settings into Bronze."""

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from yahoo_client import yahoo_get
from storage import save_bronze_response, save_bronze_run_manifest


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def has_settings(response):
    """Confirm the response contains the league settings resource."""
    content = response.get("fantasy_content", {})
    for section in content.get("league", []):
        if isinstance(section, dict) and "settings" in section:
            return True
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Ingest Yahoo Fantasy league settings into Bronze."
    )
    parser.add_argument("--league-key", required=True)
    args = parser.parse_args()

    run_id = uuid.uuid4().hex[:12]
    endpoint = f"/league/{args.league_key}/settings"
    category = "league/settings"
    manifest = {
        "run_id": run_id,
        "status": "running",
        "league_key": args.league_key,
        "started_at_utc": utc_now(),
        "completed_at_utc": None,
        "settings_found": False,
        "error": None,
    }
    manifest_options = {
        "resource": f"league_settings_{run_id}",
        "category": category,
        "league_key": args.league_key,
    }
    save_bronze_run_manifest(manifest, **manifest_options)

    try:
        response = yahoo_get(endpoint)
        if not has_settings(response):
            raise ValueError("Yahoo response did not contain a settings section")

        save_bronze_response(
            response,
            resource=f"league_settings_{run_id}",
            category=category,
            league_key=args.league_key,
            request_endpoint=endpoint,
            ingestion_run_id=run_id,
        )
        manifest["settings_found"] = True
        manifest["status"] = "complete"
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        manifest["completed_at_utc"] = utc_now()
        save_bronze_run_manifest(manifest, **manifest_options)

    print("\nLeague settings ingestion summary")
    print(f"League: {args.league_key}")
    print(f"Run ID: {run_id}")
    print(f"Status: {manifest['status']}")


if __name__ == "__main__":
    main()
