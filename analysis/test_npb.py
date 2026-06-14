import sys
sys.path.insert(0, '/Users/jero/PredictX Sports/analysis')
from npb_data_fetcher import NPBDataFetcher

f = NPBDataFetcher()

# Test full fetch
result = f.fetch_and_store_game_data('test', 'Yomiuri Giants', 'Hanshin Tigers')
if result:
    print('Standings:')
    print(f'  Home: {result["standings"]["home"]}')
    print(f'  Away: {result["standings"]["away"]}')
    print(f'\nBatting:')
    print(f'  Home: {result["batting"]["home"]}')
    print(f'  Away: {result["batting"]["away"]}')
    print(f'\nPitching:')
    print(f'  Home: {result["pitching"]["home"]}')
    print(f'  Away: {result["pitching"]["away"]}')
    print(f'\nSources: {result["sources"]}')
else:
    print('Failed')

f.close()