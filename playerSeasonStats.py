"""Deterministic season summaries and small static per-player game-log shards.

This exporter has no frontend imports and writes only a dedicated output tree.
"""
import argparse,csv,hashlib,io,json,math,os,tempfile
from collections import defaultdict
from pathlib import Path
from playerGameLogs import STATS,CollectionError,write_json

TOTALS=['FPTS',*STATS.keys()]
FIELDS=['Year','Player ID','Player Name','Latest Observed NBA Team ID','NBA Team IDs','Eligible Slot IDs','Games Played','Total FPTS','FPTS/Game',*['Total '+s for s in STATS if s!='GP']]

def summaries(rows):
    groups=defaultdict(list);seen=set()
    for row in rows:
        key=tuple(int(row[k])for k in ('Year','Player ID','Game ID'))
        if key in seen:raise CollectionError('Duplicate season/player/game identity')
        seen.add(key)
        if float(row['GP'])!=1:raise CollectionError('An archive row must be one appearance')
        for name in TOTALS:
            if not math.isfinite(float(row[name])):raise CollectionError('Missing/nonfinite game statistic')
        if not row['Date'] or not row['Player Name']:raise CollectionError('Missing game identity metadata')
        groups[key[:2]].append(row)
    result=[]
    for (year,pid),games in sorted(groups.items()):
        games=sorted(games,key=lambda r:(r['Date'],int(r['Game ID'])))
        latest=games[-1];totals={s:math.fsum(float(r[s])for r in games)for s in TOTALS}
        result.append({'Year':year,'Player ID':pid,'Player Name':latest['Player Name'],'Latest Observed NBA Team ID':int(latest['NBA Team ID']),
          'NBA Team IDs':json.dumps(sorted({int(r['NBA Team ID'])for r in games}),separators=(',',':')),
          'Eligible Slot IDs':latest['Eligible Slot IDs'],'Games Played':len(games),'Total FPTS':totals['FPTS'],'FPTS/Game':totals['FPTS']/len(games),
          **{'Total '+s:totals[s]for s in STATS if s!='GP'}})
    return result

def json_value(column,value):
    if column in ('Eligible Slot IDs','NBA Team IDs'):return json.loads(value)
    if column in ('Year','Game ID','Player ID','NBA Team ID','Opponent ID','Scoring Period','Latest Observed NBA Team ID','Games Played'):return int(value) if value not in ('',None) else None
    if column in TOTALS or column.startswith('Total ') or column=='FPTS/Game':return float(value)
    return value

def stable_bytes(path,content):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.read_bytes()==content:return
    fd,tmp=tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd,'wb')as f:f.write(content);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def export(source='data/playerGameLogs.csv',summary='data/playerSeasonStats.csv',output='data/player-static'):
    source=Path(source);rows=list(csv.DictReader(source.open()));stats=summaries(rows)
    if not stats:raise CollectionError('Empty archive')
    # Verify the collector's publication marker before consuming a generation.
    report=source.with_suffix('.report.json')
    if report.exists() and json.loads(report.read_text())['csvSHA256']!=hashlib.sha256(source.read_bytes()).hexdigest():raise CollectionError('Archive/report digest mismatch')
    text=io.StringIO();w=csv.DictWriter(text,fieldnames=FIELDS,lineterminator='\n');w.writeheader();w.writerows(stats)
    root=Path(output);columns=list(rows[0]);years=sorted({r['Year']for r in stats})
    for year in years:
        selected=[r for r in stats if r['Year']==year]
        write_json(root/f'seasons/{year}.json',{'schemaVersion':1,'columns':FIELDS,'rows':[[json_value(k,r[k])for k in FIELDS]for r in selected]})
        shards=defaultdict(list)
        for row in rows:
            if int(row['Year'])==year:shards[int(row['Player ID'])%32].append(row)
        for shard,games in sorted(shards.items()):
            games.sort(key=lambda r:(int(r['Player ID']),r['Date'],int(r['Game ID'])))
            write_json(root/f'games/{year}/{shard:02d}.json',{'schemaVersion':1,'columns':columns,'rows':[[json_value(k,r[k])for k in columns]for r in games]})
    stable_bytes(summary,text.getvalue().encode())
    # Manifest is published last; timestamp changes only when archive contents change.
    digest=hashlib.sha256(source.read_bytes()).hexdigest();manifest=root/'index.json';old=json.loads(manifest.read_text())if manifest.exists()else {}
    from datetime import datetime,timezone
    stamp=old.get('updatedAt')if old.get('archiveSHA256')==digest else datetime.now(timezone.utc).isoformat()
    write_json(manifest,{'schemaVersion':1,'archiveSHA256':digest,'updatedAt':stamp,'seasons':years,'players':len(stats),'appearances':len(rows),
        'shards':32,'shardRule':'ESPN player ID modulo 32; zero-padded two digits','seasonPath':'seasons/{year}.json','gamePath':'games/{year}/{shard}.json'})
    return {'seasonPlayers':len(stats),'appearances':len(rows),'summaryBytes':Path(summary).stat().st_size,'staticBytes':sum(p.stat().st_size for p in root.rglob('*.json'))}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',default='data/playerGameLogs.csv');p.add_argument('--summary',default='data/playerSeasonStats.csv');p.add_argument('--output',default='data/player-static');a=p.parse_args()
    print(json.dumps(export(a.source,a.summary,a.output)))
