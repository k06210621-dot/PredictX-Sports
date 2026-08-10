def fetch_wnba_players_data():
    """
    使用 Hermes browser 工具抓取 stats.wnba.com 球員數據
    保存為 JSON 檔案供 wnba_data_fetcher.py 使用
    """
    
    # 步驟 1: 導航到 stats.wnba.com
    print("Navigate to stats.wnba.com...")
    # browser_navigate(url="https://stats.wnba.com/players/advanced/?sort=PIE&dir=-1")
    
    # 步驟 2: 等待頁面加載並抓取表格
    js_code = """
    (function() {
        const table = document.querySelector('table');
        if (!table) return {error: 'No table'};
        
        const rows = table.querySelectorAll('tbody tr');
        const players = [];
        
        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length >= 20) {
                players.push({
                    name: cells[0]?.textContent?.trim() || '',
                    team: cells[1]?.textContent?.trim() || '',
                    gp: parseFloat(cells[3]?.textContent?.trim()) || 0,
                    min: parseFloat(cells[6]?.textContent?.trim()) || 0,
                    offrtg: parseFloat(cells[7]?.textContent?.trim()) || 0,
                    defrtg: parseFloat(cells[8]?.textContent?.trim()) || 0,
                    netrtg: parseFloat(cells[9]?.textContent?.trim()) || 0,
                    ast_pct: parseFloat(cells[10]?.textContent?.trim()) || 0,
                    reb_pct: parseFloat(cells[14]?.textContent?.trim()) || 0,
                    efg_pct: parseFloat(cells[16]?.textContent?.trim()) || 0,
                    ts_pct: parseFloat(cells[17]?.textContent?.trim()) || 0,
                    pie: parseFloat(cells[19]?.textContent?.trim()) || 0,
                });
            }
        });
        
        return players;
    })()
    """
    
    # 步驟 3: 執行 JavaScript 抓取數據
    # result = browser_console(expression=js_code)
    
    # 步驟 4: 按球隊分組
    # from collections import defaultdict
    # teams = defaultdict(list)
    # for player in players:
    #     teams[player['team']].append(player)
    
    # 步驟 5: 排序並保存
    # for team in teams:
    #     teams[team].sort(key=lambda p: p['pie'], reverse=True)
    
    # with open('/Users/jero/PredictX-Sports-backend/data/wnba_players_2026.json', 'w') as f:
    #     json.dump(teams, f, indent=2)
    
    print("請執行以下命令來抓取數據：")
    print("  1. browser_navigate(url='https://stats.wnba.com/players/advanced/?sort=PIE&dir=-1')")
    print("  2. browser_console(expression=JS_CODE)")
    print("  3. 解析結果並保存到 JSON")
    print("\n或者，手動複製貼上數據到 wnba_players_2026.json")

if __name__ == '__main__':
    fetch_wnba_players_data()