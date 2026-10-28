
import pandas as pd
from pathlib import Path

# Read the consolidated roster exported from Yahoo.
INPUT_FILE = Path("data/processed/nba_rosters.csv")
OUTPUT_FILE = Path("data/processed/nba_roster_summary.csv")


def main():
    # Stop early if the roster export hasn't been created.
    if not INPUT_FILE.exists():
        print(f"Roster file not found: {INPUT_FILE}")
        print("Run python src\\export_rosters.py first.")
        return

    # Load the roster data into a DataFrame.
    df = pd.read_csv(INPUT_FILE)

    # Report basic data quality checks.
    print(f"Total player-team records: {len(df)}")
    print(f"Unique fantasy teams: {df['team_key'].nunique()}")
    print(f"Unique players: {df['player_key'].nunique()}")

    missing_names = df["player_name"].isna().sum()
    missing_ids = df["player_key"].isna().sum()

    print(f"Records missing player names: {missing_names}")
    print(f"Records missing player keys: {missing_ids}")

    # Summarize roster size for each fantasy team.
    team_summary = (
        df.groupby("team_key")
        .agg(
            player_count=("player_key", "count"),
            unique_players=("player_key", "nunique"),
        )
        .reset_index()
    )

    # Count how many players occupy each roster position per team.
    position_counts = (
        df.pivot_table(
            index="team_key",
            columns="roster_position",
            values="player_key",
            aggfunc="count",
            fill_value=0,
        )
        .reset_index()
    )

    # Combine roster sizes and position counts.
    team_summary = team_summary.merge(
        position_counts,
        on="team_key",
        how="left",
    )

    # Identify players listed on more than one fantasy team.
    duplicate_players = (
        df.groupby("player_key")["team_key"]
        .nunique()
        .reset_index(name="fantasy_team_count")
    )
    duplicate_players = duplicate_players[
        duplicate_players["fantasy_team_count"] > 1
    ]

    print("\nRoster size by team:")
    print(team_summary.to_string(index=False))

    print("\nPlayers found on multiple teams:")
    if duplicate_players.empty:
        print("None found.")
    else:
        print(duplicate_players.to_string(index=False))

    # Save the team-level summary for later use.
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    team_summary.to_csv(OUTPUT_FILE, index=False)

    print(f"\nSummary saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
