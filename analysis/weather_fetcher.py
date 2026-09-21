"""
PredictX Sports — 天氣資料收集器
使用 wttr.in（完全免費，無需 API Key）
"""
import requests
import json
import psycopg2
from psycopg2.extras import RealDictCursor
import os

DB_CONFIG = {
    "dbname": "sports_db", "user": "jero",
    "password": "", "host": "localhost", "port": 5432
}

# MLB 球隊對應主場城市（用於天氣查詢）
MLB_VENUE_CITIES = {
    "Arizona Diamondbacks": "Phoenix",
    "Atlanta Braves": "Atlanta",
    "Baltimore Orioles": "Baltimore",
    "Boston Red Sox": "Boston",
    "Chicago Cubs": "Chicago",
    "Chicago White Sox": "Chicago",
    "Cincinnati Reds": "Cincinnati",
    "Cleveland Guardians": "Cleveland",
    "Colorado Rockies": "Denver",
    "Detroit Tigers": "Detroit",
    "Houston Astros": "Houston",
    "Kansas City Royals": "Kansas City",
    "Los Angeles Angels": "Anaheim",
    "Los Angeles Dodgers": "Los Angeles",
    "Miami Marlins": "Miami",
    "Milwaukee Brewers": "Milwaukee",
    "Minnesota Twins": "Minneapolis",
    "New York Mets": "New York",
    "New York Yankees": "New York",
    "Oakland Athletics": "Oakland",
    "Philadelphia Phillies": "Philadelphia",
    "Pittsburgh Pirates": "Pittsburgh",
    "San Diego Padres": "San Diego",
    "San Francisco Giants": "San Francisco",
    "Seattle Mariners": "Seattle",
    "St. Louis Cardinals": "St. Louis",
    "Tampa Bay Rays": "Tampa",
    "Texas Rangers": "Arlington",
    "Toronto Blue Jays": "Toronto",
    "Washington Nationals": "Washington",
}

# NBA 球隊對應主場城市
NBA_VENUE_CITIES = {
    "Atlanta Hawks": "Atlanta",
    "Boston Celtics": "Boston",
    "Brooklyn Nets": "New York",
    "Charlotte Hornets": "Charlotte",
    "Chicago Bulls": "Chicago",
    "Cleveland Cavaliers": "Cleveland",
    "Dallas Mavericks": "Dallas",
    "Denver Nuggets": "Denver",
    "Detroit Pistons": "Detroit",
    "Golden State Warriors": "San Francisco",
    "Houston Rockets": "Houston",
    "Indiana Pacers": "Indianapolis",
    "Los Angeles Clippers": "Los Angeles",
    "Los Angeles Lakers": "Los Angeles",
    "Memphis Grizzlies": "Memphis",
    "Miami Heat": "Miami",
    "Milwaukee Bucks": "Milwaukee",
    "Minnesota Timberwolves": "Minneapolis",
    "New Orleans Pelicans": "New Orleans",
    "New York Knicks": "New York",
    "Oklahoma City Thunder": "Oklahoma City",
    "Orlando Magic": "Orlando",
    "Philadelphia 76ers": "Philadelphia",
    "Phoenix Suns": "Phoenix",
    "Portland Trail Blazers": "Portland",
    "Sacramento Kings": "Sacramento",
    "San Antonio Spurs": "San Antonio",
    "Toronto Raptors": "Toronto",
    "Utah Jazz": "Salt Lake City",
    "Washington Wizards": "Washington",
}

class WeatherFetcher:
    def __init__(self):
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
            self.conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        else:
            self.conn = psycopg2.connect(**DB_CONFIG)
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "curl/8.0"})
        self.fetched_sources = []

    def get_weather(self, city):
        """從 wttr.in 取得某城市的天氣資料（完全免費）"""
        url = f"https://wttr.in/{city}?format=j1"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return None
            data = resp.json()
            current = data.get('current_condition', [{}])[0]
            self.fetched_sources.append("wttr.in")
            
            weather_code = int(current.get('weatherCode', 0))
            # 天氣狀況描述
            conditions = {
                113: "晴朗", 116: "多雲間晴", 119: "多雲", 122: "陰天",
                143: "有霧", 176: "小雨", 179: "小雪", 182: "雨夾雪",
                185: "凍雨", 200: "雷陣雨", 227: "小雪", 230: "中雪",
                248: "薄霧", 260: "霧", 263: "毛毛雨", 266: "毛毛雨",
                281: "凍毛毛雨", 284: "凍毛毛雨", 293: "小雨", 296: "小雨",
                299: "中雨", 302: "中雨", 305: "大雨", 308: "大雨",
                311: "凍雨", 314: "凍雨", 320: "雨夾雪", 323: "小雪",
                326: "小雪", 329: "中雪", 332: "中雪", 335: "大雪",
                338: "大雪", 350: "冰雹", 353: "小雨", 356: "中雨",
                359: "大雨", 362: "雨夾雪", 365: "雨夾雪", 368: "小雪",
                371: "大雪", 374: "冰雹", 377: "冰雹", 386: "雷雨",
                389: "雷雨", 392: "雷陣雪", 395: "雷陣雪"
            }
            
            return {
                "temperature_c": float(current.get('temp_C', 0)),
                "feels_like_c": float(current.get('FeelsLikeC', 0)),
                "humidity_pct": float(current.get('humidity', 0)),
                "wind_speed_kmh": float(current.get('windspeedKmph', 0)),
                "wind_direction": current.get('winddir16Point', ''),
                "precip_mm": float(current.get('precipMM', 0)),
                "pressure_hpa": float(current.get('pressure', 0)),
                "cloud_cover_pct": float(current.get('cloudcover', 0)),
                "visibility_km": float(current.get('visibility', 0)),
                "condition": conditions.get(weather_code, f"代碼{weather_code}"),
                "city": city
            }
        except Exception as e:
            print(f"  ⚠ Weather fetch error for {city}: {e}")
            return None

    def fetch_and_store_weather(self, game_id, home_team_name, league):
        """為一場比賽取得天氣資料並存入資料庫"""
        city_map = MLB_VENUE_CITIES if league.upper() == 'MLB' else NBA_VENUE_CITIES
        city = city_map.get(home_team_name)
        
        if not city:
            # 嘗試用隊名最後一個詞找城市
            parts = home_team_name.split()[-1]
            for key, val in city_map.items():
                if parts.lower() in key.lower():
                    city = val
                    break
        
        if not city:
            print(f"  ⚠ Unknown venue for {home_team_name}")
            return None
        
        weather = self.get_weather(city)
        if not weather:
            return None
        
        # 存入資料庫
        self.cur.execute("""
            INSERT INTO predictx_advanced.game_weather 
                (game_id, venue_name, temperature, wind_speed, wind_direction, 
                 humidity, precipitation_pct, data_source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'wttr.in')
            ON CONFLICT (game_id) DO UPDATE SET
                temperature = EXCLUDED.temperature,
                wind_speed = EXCLUDED.wind_speed,
                wind_direction = EXCLUDED.wind_direction,
                humidity = EXCLUDED.humidity,
                precipitation_pct = EXCLUDED.precipitation_pct,
                fetched_at = CURRENT_TIMESTAMP
        """, (game_id, weather['city'], weather['temperature_c'],
              weather['wind_speed_kmh'], weather['wind_direction'],
              weather['humidity_pct'], weather['precip_mm']))
        self.conn.commit()
        
        return weather

    def close(self):
        self.cur.close()
        self.conn.close()