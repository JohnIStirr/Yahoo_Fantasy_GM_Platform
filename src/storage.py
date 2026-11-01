"""Storage helpers for source-preserving Bronze ingestion."""

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from paths import (
    SPORT,
    SEASON,
    SOURCE,
    EXPERIMENTS_ROOT,
    bronze_resource_dir,
)


def _utc_timestamp():
    """Return an ISO-8601 UTC timestamp suitable for metadata."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _safe_name(value):
    """Keep resource names safe for use in file names."""
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return value.strip("._-") or "response"


def _atomic_json_write(path, value):
    """Write JSON to a temporary file before publishing the final file."""
    path = Path(path)
    temporary_path = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")

    try:
        with temporary_path.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(value, file, indent=2, ensure_ascii=False)
            file.write("\n")
        os.replace(str(temporary_path), str(path))
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def save_bronze_response(
    payload,
    *,
    resource,
    category,
    league_key=None,
    request_endpoint=None,
    ingestion_run_id=None,
    source=SOURCE,
    sport=SPORT,
    season=SEASON,
):
    """Save an original API payload and a sidecar ingestion manifest.

    Resource category is required so production paths are explicit rather than
    inferred from endpoint/resource-name strings. The raw JSON payload is kept
    separate from metadata so the source response remains easy to inspect.
    """
    if not resource or not str(resource).strip():
        raise ValueError("resource must be a non-empty name")
    if not category:
        raise ValueError("category is required for Bronze storage")

    output_dir = bronze_resource_dir(
        category,
        league_key=league_key,
        sport=sport,
        season=season,
        source=source,
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    ingested_at = _utc_timestamp()
    filename_timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S.%fZ"
    )
    safe_resource = _safe_name(str(resource))
    payload_path = output_dir / f"{safe_resource}_{filename_timestamp}.json"
    metadata_path = output_dir / f"{safe_resource}_{filename_timestamp}.metadata.json"

    _atomic_json_write(payload_path, payload)

    # Hash the stored representation so later integrity checks are possible.
    digest = hashlib.sha256(payload_path.read_bytes()).hexdigest()
    metadata = {
        "source": source,
        "sport": sport,
        "season": season,
        "category": category,
        "resource": str(resource),
        "league_key": league_key,
        "request_endpoint": request_endpoint,
        "ingested_at_utc": ingested_at,
        "ingestion_run_id": ingestion_run_id,
        "payload_file": payload_path.name,
        "payload_sha256": digest,
    }
    _atomic_json_write(metadata_path, metadata)

    print(f"Saved Bronze payload to: {payload_path}")
    print(f"Saved ingestion metadata to: {metadata_path}")
    return payload_path


def save_bronze_run_manifest(
    manifest,
    *,
    resource,
    category,
    league_key=None,
    source=SOURCE,
    sport=SPORT,
    season=SEASON,
):
    """Create or update the manifest for one ingestion run."""
    if not isinstance(manifest, dict):
        raise TypeError("manifest must be a dictionary")

    run_id = str(manifest.get("run_id", "")).strip()
    if not run_id:
        raise ValueError("manifest must contain a non-empty run_id")

    if not resource or not str(resource).strip():
        raise ValueError("resource must be a non-empty name")

    output_dir = bronze_resource_dir(
        category,
        league_key=league_key,
        source=source,
        sport=sport,
        season=season,
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    # Use a stable filename so repeated saves update the same run.
    safe_resource = _safe_name(str(resource))
    safe_run_id = _safe_name(run_id)
    manifest_path = output_dir / (
        f"{safe_resource}_{safe_run_id}.run.json"
    )

    document = {
        **manifest,
        "manifest_version": 1,
        "source": source,
        "sport": sport,
        "season": season,
        "category": category,
        "league_key": league_key,
        "recorded_at_utc": _utc_timestamp(),
    }

    _atomic_json_write(manifest_path, document)

    print(f"Saved Bronze run manifest to: {manifest_path}")
    return manifest_path

def save_experiment_response(
    payload,
    *,
    experiment,
    resource,
    request_endpoint=None,
    source=SOURCE,
    sport=SPORT,
    season=SEASON,
):
    """Save an exploratory API response outside the production layers."""
    experiment_name = _safe_name(str(experiment))
    resource_name = _safe_name(str(resource))

    output_dir = (
        EXPERIMENTS_ROOT
        / source
        / sport
        / f"season={season}"
        / experiment_name
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S.%fZ"
    )
    payload_path = output_dir / f"{resource_name}_{timestamp}.json"
    metadata_path = output_dir / f"{resource_name}_{timestamp}.metadata.json"

    _atomic_json_write(payload_path, payload)

    metadata = {
        "source": source,
        "sport": sport,
        "season": season,
        "experiment": experiment_name,
        "resource": resource,
        "request_endpoint": request_endpoint,
        "ingested_at_utc": _utc_timestamp(),
        "payload_file": payload_path.name,
        "payload_sha256": hashlib.sha256(
            payload_path.read_bytes()
        ).hexdigest(),
    }
    _atomic_json_write(metadata_path, metadata)

    print(f"Saved experiment payload to: {payload_path}")
    return payload_path
