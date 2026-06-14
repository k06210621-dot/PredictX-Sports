from bs4 import BeautifulSoup

with open('/tmp/cpbl_standings.html') as f:
    soup = BeautifulSoup(f.read(), 'lxml')

tables = soup.find_all('table')
for i, table in enumerate(tables):
    rows = table.find_all('tr')
    print(f'\n=== Table {i}: {len(rows)} rows ===')
    for row in rows[:8]:
        cells = row.find_all(['th', 'td'])
        row_data = [c.get_text(strip=True)[:18] for c in cells]
        print(f'  {row_data[:12]}')
    
    if i == 3:
        for row in rows:
            cells = row.find_all(['th', 'td'])
            row_data = [c.get_text(strip=True)[:18] for c in cells]
            print(f'  {row_data[:12]}')