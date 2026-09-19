"""Generate the canonical ESPN scoring-period to matchup-week reference CSV."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dataUpdateSafety import atomic_write_csv
from playerDailyAggregation import (
    SCORING_PERIOD_MAP_PATH,
    build_scoring_period_map,
    load_season_metadata,
)


def generate(output: Path = SCORING_PERIOD_MAP_PATH):
    mapping = build_scoring_period_map(load_season_metadata())
    atomic_write_csv(mapping, output)
    return mapping


if __name__ == "__main__":
    mapping = generate()
    print(f"Wrote {len(mapping)} scoring-period mappings to {SCORING_PERIOD_MAP_PATH}")
