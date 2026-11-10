"""Opt-in static ranking/game-log export; not enabled in generate_all yet.

Preparing these assets does not migrate any current React calculations. Future
Pages integration can call this same entry point with an approved public output.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from playerSeasonStats import export

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-dir',type=Path,default=Path('data'))
    p.add_argument('--summary',default='data/playerSeasonStats.csv')
    p.add_argument('--output-dir',default='data/player-static')
    args=p.parse_args()
    print(json.dumps(export(args.source_dir/'playerGameLogs.csv',args.summary,args.output_dir)))
