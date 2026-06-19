import Foundation

struct TeamNameMap {
    static let mapping: [String: String] = [
        // ===== NBA (30 隊完整) =====
        "Atlanta Hawks": "亞特蘭大老鷹",
        "Boston Celtics": "波士頓塞爾提克",
        "Brooklyn Nets": "布魯克林籃網",
        "Charlotte Hornets": "夏洛特黃蜂",
        "Chicago Bulls": "芝加哥公牛",
        "Cleveland Cavaliers": "克里夫蘭騎士",
        "Dallas Mavericks": "達拉斯獨行俠",
        "Denver Nuggets": "丹佛金塊",
        "Detroit Pistons": "底特律活塞",
        "Golden State Warriors": "金州勇士",
        "Houston Rockets": "休士頓火箭",
        "Indiana Pacers": "印第安納溜馬",
        "Los Angeles Clippers": "洛杉磯快艇",
        "Los Angeles Lakers": "洛杉磯湖人",
        "Memphis Grizzlies": "曼菲斯灰熊",
        "Miami Heat": "邁阿密熱火",
        "Milwaukee Bucks": "密爾瓦基公鹿",
        "Minnesota Timberwolves": "明尼蘇達灰狼",
        "New Orleans Pelicans": "紐奧良鵜鶘",
        "New York Knicks": "紐約尼克",
        "Oklahoma City Thunder": "奧克拉荷馬雷霆",
        "Orlando Magic": "奧蘭多魔術",
        "Philadelphia 76ers": "費城七六人",
        "Phoenix Suns": "鳳凰城太陽",
        "Portland Trail Blazers": "波特蘭拓荒者",
        "Sacramento Kings": "沙加緬度國王",
        "San Antonio Spurs": "聖安東尼奧馬刺",
        "Toronto Raptors": "多倫多暴龍",
        "Utah Jazz": "猶他爵士",
        "Washington Wizards": "華盛頓巫師",
        
        // ===== MLB =====
        "New York Yankees": "紐約洋基",
        "Boston Red Sox": "波士頓紅襪",
        "Los Angeles Dodgers": "洛杉磯道奇",
        "Chicago Cubs": "芝加哥小熊",
        "Houston Astros": "休士頓太空人",
        "Arizona Diamondbacks": "亞利桑那響尾蛇",
        "Milwaukee Brewers": "密爾瓦基釀酒人",
        "Colorado Rockies": "科羅拉多落磯",
        "Kansas City Royals": "堪薩斯皇家",
        "Minnesota Twins": "明尼蘇達雙城",
        "Cincinnati Reds": "辛辛那提紅人",
        "St. Louis Cardinals": "聖路易紅雀",
        "Washington Nationals": "華盛頓國民",
        "Athletics": "奧克蘭運動家",
        "Cleveland Guardians": "克里夫蘭守護者",
        "Texas Rangers": "德州遊騎兵",
        "Los Angeles Angels": "洛杉磯天使",
        "New York Mets": "紐約大都會",
        "San Diego Padres": "聖地牙哥教士",
        "Tampa Bay Rays": "坦帕灣光芒",
        "Miami Marlins": "邁阿密馬林魚",
        "Chicago White Sox": "芝加哥白襪",
        "Philadelphia Phillies": "費城費城人",
        "Seattle Mariners": "西雅圖水手",
        "Detroit Tigers": "底特律老虎",
        "Baltimore Orioles": "巴爾的摩金鶯",
        "Toronto Blue Jays": "多倫多藍鳥",
        "San Francisco Giants": "舊金山巨人",
        "Pittsburgh Pirates": "匹茲堡海盜",
        "Atlanta Braves": "亞特蘭大勇士",
        
        // ===== NPB (日本職棒) =====
        // 中央聯盟 (Central League)
        "Yomiuri Giants": "讀賣巨人",
        "Hanshin Tigers": "阪神虎",
        "Chunichi Dragons": "中日龍",
        "Yokohama DeNA BayStars": "橫濱DeNA海灣之星",
        "Hiroshima Toyo Carp": "廣島東洋鯉魚",
        "Tokyo Yakult Swallows": "東京養樂多燕子",
        // 太平洋聯盟 (Pacific League)
        "Fukuoka SoftBank Hawks": "福岡軟銀鷹",
        "Orix Buffaloes": "歐力士猛牛",
        "ORIX Buffaloes": "歐力士猛牛",
        "Chiba Lotte Marines": "千葉羅德海洋",
        "Saitama Seibu Lions": "埼玉西武獅",
        "Tohoku Rakuten Golden Eagles": "東北樂天金鷲",
        "Hokkaido Nippon-Ham Fighters": "北海道日本火腿鬥士",
        
        // ===== CPBL (中華職棒) =====
        "Uni-President 7-ELEVEn Lions": "統一7-ELEVEn獅",
        "CTBC Brothers": "中信兄弟",
        "Fubon Guardians": "富邦悍將",
        "Rakuten Monkeys": "樂天桃猿",
        "Wei Chuan Dragons": "味全龍",
        "TSG Hawks": "台鋼雄鷹"
    ]
    
    static func getChineseName(for englishName: String) -> String {
        return mapping[englishName] ?? englishName
    }
}