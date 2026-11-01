
"""Safely migrate legacy data files into the new folder structure.

By default, this script only previews the migration.
Pass --apply to actually move files.
"""

import argparse
import re
import shutil
from pathlib import Path

from paths import (
    PROJECT_ROOT,
    RAW_LEAGUE_SETTINGS_DIR,
    RAW_TEAMS_DIR,
    RAW_ROSTERS_DIR,
    RAW_FREE_AGENTS_DIR,
    RAW_WAIVERS_DIR,
    RAW_DAILY_STATS_DIR,
    RAW_EXPERIMENTS_DIR,
    ROSTERS_FILE,
    ROSTER_SUMMARY_FILE,
    PLAYER_POOL_FILE,
    PROCESSED_DAILY_STATS_DIR,
    DAILY_LEADERBOARDS_DIR,
    PROCESSED_NBA_ROOT,
)


# Legacy locations used before paths.py was introduced.
LEGACY_RAW_ROOT = PROJECT_ROOT / "data" / "raw" / "nba"
LEGACY_PROCESSED_ROOT = PROJECT_ROOT / "data" / "processed"


def raw_destination(source):
    """Map one legacy raw file to its new location."""
    relative = source.relative_to(LEGACY_RAW_ROOT)
    parts = relative.parts
    folder = parts[0]
    remaining = Path(*parts[1:]) if len(parts) > 1 else Path()

    # Preserve existing roster team subfolders.
    if folder == "league_settings":
        return RAW_LEAGUE_SETTINGS_DIR / remaining

    if folder == "teams":
        return RAW_TEAMS_DIR / remaining

    if re.fullmatch(r"roster_team_\d+", folder):
        return RAW_ROSTERS_DIR / folder / remaining

    if folder == "available_players_fa":
        return RAW_FREE_AGENTS_DIR / remaining

    if folder == "available_players_w":
        return RAW_WAIVERS_DIR / remaining

    # Group historical daily-stat responses by date and original batch.
    if folder.startswith("daily_stats_"):
        match = re.search(r"\d{4}-\d{2}-\d{2}", folder)

        if match:
            return (
                RAW_DAILY_STATS_DIR
                / match.group(0)
                / folder
                / remaining
            )

    # Keep experimental requests separate from durable raw datasets.
    if folder.startswith(("yesterday_", "lastweek_", "lastmonth_")):
        return RAW_EXPERIMENTS_DIR / "leaderboards" / folder / remaining

    if folder.startswith("batch_date_stats"):
        return RAW_EXPERIMENTS_DIR / "batch_stats" / folder / remaining

    if folder.startswith("player_date_stats"):
        return (
            RAW_EXPERIMENTS_DIR
            / "player_date_stats"
            / folder
            / remaining
        )

    # Unknown legacy resources are preserved instead of discarded.
    return RAW_EXPERIMENTS_DIR / folder / remaining


def processed_destination(source):
    """Map a legacy processed CSV to its new location."""
    name = source.name

    known_files = {
        "nba_rosters.csv": ROSTERS_FILE,
        "nba_roster_summary.csv": ROSTER_SUMMARY_FILE,
        "nba_player_pool.csv": PLAYER_POOL_FILE,
    }

    if name in known_files:
        return known_files[name]

    if name.startswith("nba_daily_player_stats_"):
        return PROCESSED_DAILY_STATS_DIR / name

    if name.startswith("nba_daily_leaderboard_"):
        return DAILY_LEADERBOARDS_DIR / name

    # Keep any unrecognized top-level processed file for later review.
    return PROCESSED_NBA_ROOT / "legacy" / name


def reserve_destination(candidate, reserved):
    """Avoid overwriting existing files or another planned destination."""
    original = candidate
    number = 1

    while (
        candidate.exists()
        or str(candidate).casefold() in reserved
    ):
        candidate = original.with_name(
            f"{original.stem}__migrated_{number}{original.suffix}"
        )
        number += 1

    reserved.add(str(candidate).casefold())
    return candidate


def build_plan():
    """Build a complete list of moves without changing any files."""
    plan = []
    reserved = set()

    # Migrate all files under the old raw NBA directory.
    if LEGACY_RAW_ROOT.exists():
        for source in sorted(LEGACY_RAW_ROOT.rglob("*")):
            if source.is_file():
                destination = reserve_destination(
                    raw_destination(source), reserved
                )
                plan.append((source, destination))

    # Existing processed outputs are currently stored directly in this folder.
    if LEGACY_PROCESSED_ROOT.exists():
        for source in sorted(LEGACY_PROCESSED_ROOT.iterdir()):
            if source.is_file():
                destination = reserve_destination(
                    processed_destination(source), reserved
                )
                plan.append((source, destination))

    return plan


def remove_empty_directories(root):
    """Remove empty legacy folders after a successful migration."""
    if not root.exists():
        return

    for directory in sorted(
        (item for item in root.rglob("*") if item.is_dir()),
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        try:
            directory.rmdir()
        except OSError:
            # Keep folders that still contain files.
            pass

    try:
        root.rmdir()
    except OSError:
        pass


def main():
    parser = argparse.ArgumentParser(
        description="Preview or apply the legacy data migration."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually move files. Without this flag, only preview.",
    )
    args = parser.parse_args()

    plan = build_plan()

    if not plan:
        print("No legacy files found to migrate.")
        return

    print(f"Files in migration plan: {len(plan)}")

    for source, destination in plan:
        print(f"{source}")
        print(f"  -> {destination}")

    if not args.apply:
        print("\nDRY RUN ONLY: no files were moved.")
        print("Review the destinations above.")
        print("To apply the migration, run:")
        print("  python src/migrate_storage.py --apply")
        return

    moved = 0

    try:
        for source, destination in plan:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            moved += 1
    except Exception:
        print(
            f"\nMigration stopped after {moved} files moved. "
            "Review the error and the remaining files before retrying."
        )
        raise

    # Clean up only empty legacy folders.
    remove_empty_directories(LEGACY_RAW_ROOT)

    print(f"\nMigration complete. Files moved: {moved}")
    print(f"Processed NBA data: {PROCESSED_NBA_ROOT}")


if __name__ == "__main__":
    main()
