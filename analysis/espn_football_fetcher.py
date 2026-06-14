"""
PredictX Sports — ESPN 足球資料收集器（完全免費，無需 API Key）
"""
import requests
import json

class ESPNFootballFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "PredictX-Sports/1.0"})
        self.fetched_sources = []
        self.ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

    def get_fifa_world_cup_schedule(self):
        """取得 FIFA 世界盃賽程"""
        url = f"{self.ESPN_BASE}/fifa.world/scoreboard"
        resp = self.session.get(url, timeout=15)
        if resp.status_code != 200:
            return None
        data = resp.json()
        self.fetched_sources.append("espn.com")
        events = []
        for event in data.get('events', []):
            comps = event.get('competitions', [{}])[0]
            competitors = comps.get('competitors', [])
            home = competitors[0].get('team', {}).get('displayName', '?') if competitors else '?'
            away = competitors[1].get('team', {}).get('displayName', '?') if len(competitors) > 1 else '?'
            home_score = competitors[0].get('score', '') if competitors else ''
            away_score = competitors[1].get('score', '') if len(competitors) > 1 else ''
            status = comps.get('status', {}).get('type', {}).get('name', '?')
            events.append({
                'home': home, 'away': away,
                'home_score': home_score, 'away_score': away_score,
                'status': status,
                'date': comps.get('date', ''),
            })
        return events

    def get_league_schedule(self, league_id="ENG.1"):
        """取得特定聯賽賽程（英超: ENG.1, 西甲: ESP.1, 德甲: GER.1）"""
        url = f"{self.ESPN_BASE}/eng.1/scoreboard"  # 英超
        if 'GER' in league_id:
            url = f"{self.ESPN_BASE}/ger.1/scoreboard"
        elif 'ESP' in league_id:
            url = f"{self.ESPN_BASE}/esp.1/scoreboard"
        elif 'ITA' in league_id:
            url = f"{self.ESPN_BASE}/ita.1/scoreboard"
        
        resp = self.session.get(url, timeout=15)
        if resp.status_code != 200:
            return None
        data = resp.json()
        self.fetched_sources.append("espn.com")
        events = []
        for event in data.get('events', []):
            comps = event.get('competitions', [{}])[0]
            competitors = comps.get('competitors', [])
            home = competitors[0].get('team', {}).get('displayName', '?') if competitors else '?'
            away = competitors[1].get('team', {}).get('displayName', '?') if len(competitors) > 1 else '?'
            events.append({'home': home, 'away': away, 'status': comps.get('status', {}).get('type', {}).get('name', '?')})
        return events

    def get_soccer_leagues(self):
        """列出所有可用足球聯賽"""
        url = "https://site.api.espn.com/apis/site/v2/sports/soccer"
        resp = self.session.get(url, timeout=15)
        if resp.status_code != 200:
            return None
        data = resp.json()
        leagues = data.get('leagues', [])
        return [(l.get('name', '?'), l.get('abbreviation', '?'), l.get('id', '?')) for l in leagues]


if __name__ == "__main__":
    f = ESPNFootballFetcher()
    print("=== FIFA World Cup ===")
    events = f.get_fifa_world_cup_schedule()
    if events:
        for e in events:
            print(f"  {e['home']} vs {e['away']} [{e['status']}]")
    else:
        print("  No data")
    
    print("\n=== League list ===")
    leagues = f.get_soccer_leagues()
    if leagues:
        for name, abbr, lid in leagues[:10]:
            print(f"  {name} ({abbr}) id={lid}")