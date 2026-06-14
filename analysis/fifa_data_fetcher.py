"""
FIFA 世界盃資料收集器
從 ESPN API 取得 FIFA 隊伍排名與戰績資料
"""
import requests
import json

class FIFADataFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "PredictX-Sports/1.0"})
        self.ESPN_TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/teams"
        self.ESPN_TEAM_DETAIL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/teams/{}"
    
    def get_all_team_rankings(self):
        """取得所有 FIFA 隊伍的排名與戰績"""
        # 先取得隊伍列表
        resp = self.session.get(self.ESPN_TEAMS_URL, timeout=15)
        if resp.status_code != 200:
            print(f"  ⚠ ESPN teams API: {resp.status_code}")
            return {}
        
        data = resp.json()
        teams = data['sports'][0]['leagues'][0]['teams']
        
        rankings = {}
        for t in teams:
            tid = t['team']['id']
            name = t['team']['displayName']
            
            # 查詢詳細資料
            try:
                resp2 = self.session.get(self.ESPN_TEAM_DETAIL.format(tid), timeout=10)
                if resp2.status_code == 200:
                    d2 = resp2.json()
                    team = d2.get('team', {})
                    standing = team.get('standingSummary', 'N/A')
                    record = team.get('record', {}).get('items', [{}])[0].get('summary', 'N/A')
                    rankings[name] = {
                        'standing': standing,
                        'record': record,
                    }
            except Exception as e:
                print(f"  ⚠ Error fetching {name}: {e}")
        
        return rankings
    
    def get_team_ranking(self, team_name):
        """取得單一隊伍的排名"""
        rankings = self.get_all_team_rankings()
        # 嘗試完全比對
        if team_name in rankings:
            return rankings[team_name]
        # 嘗試部分比對
        for name, data in rankings.items():
            if team_name.lower() in name.lower() or name.lower() in team_name.lower():
                return data
        return None

if __name__ == "__main__":
    f = FIFADataFetcher()
    rankings = f.get_all_team_rankings()
    print(f"Fetched {len(rankings)} team rankings")
    for name, data in list(rankings.items())[:10]:
        print(f"  {name:30s} | {data['standing']:30s} | {data['record']}")
