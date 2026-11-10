"""Offline season-by-season FP/Start coverage audit; no ESPN requests or writes to CSVs."""
import argparse
import json
from pathlib import Path

import pandas as pd

from generate_team_stats import ROOT
from playerDailyAggregation import load_season_metadata
from teamPerformance import team_performance, performance_audit


def audit(source):
    metadata_path = source / 'seasonMetadata.json'
    metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else load_season_metadata()
    performance = team_performance(pd.read_csv(source / 'playerDailyData.csv'),
        pd.read_csv(source / 'scoringPeriodMatchupMap.csv'), metadata,
        pd.read_csv(source / 'basketballBrawlLeagueData.csv'), pd.read_csv(source / 'playerMatchupData.csv'))
    return performance_audit(performance)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=ROOT / 'data')
    args = parser.parse_args()
    print(json.dumps(audit(args.source_dir), indent=2))
