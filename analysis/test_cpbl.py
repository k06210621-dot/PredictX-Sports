import sys
sys.path.insert(0, '/Users/jero/PredictX Sports/analysis')
from cpbl_data_fetcher import CPBLDataFetcher

f = CPBLDataFetcher()
hitters = f.get_hitting_leaderboard()
if hitters:
    print(f'Hitters: {len(hitters)}')
    for h in hitters[:10]:
        print(f'  #{h["rank"]} {h["name"]} ({h["team_en"]}) AVG={h["avg"]} HR={h["hr"]}')
    
    from collections import Counter
    team_counts = Counter(h['team_en'] for h in hitters)
    print('\nBy team:')
    for team, cnt in team_counts.most_common():
        print(f'  {team}: {cnt}')
f.close()