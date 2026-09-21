"""Regenerate every static data payload consumed by the React frontend."""
from pathlib import Path
import argparse

from build_homepage import build as build_homepage
from generate_historical_h2h import build as build_historical_h2h
from generate_record_book import build as build_record_book
from generate_team_stats import build as build_team_stats
from generate_player_metadata import build as build_player_metadata


ROOT = Path(__file__).resolve().parents[2]


def build_all(source: Path, output: Path) -> None:
    build_homepage(source, output)
    build_team_stats(source, output)
    build_historical_h2h(source, output)
    build_record_book(source, output)
    build_player_metadata(source, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "frontend/public/data")
    arguments = parser.parse_args()
    build_all(arguments.source_dir, arguments.output_dir)
