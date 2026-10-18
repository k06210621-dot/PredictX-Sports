#!/usr/bin/env python3
"""CPBL 2026 官方成績刷新（打擊 + 投球）
來源：cpbl.com.tw /stats/recordallaction（POST，Position=01 打者 / 02 投手）
更新：cpbl_player_pr（打者）、cpbl_pitcher_pr（投手），僅更新官方有提供的欄位
"""
import os, sys, re, json, time, requests
from bs4 import BeautifulSoup
import psycopg2
from psycopg2.extras import RealDictCursor

HDR = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36",
       "Accept-Language": "zh-TW", "X-Requested-With": "XMLHttpRequest",
       "Referer": "https://www.cpbl.com.tw/stats/recordall?season=2026"}
BASE_URL = "https://www.cpbl.com.tw/stats/recordall?season=2026"
ACTION = "https://www.cpbl.com.tw/stats/recordallaction"
DRY = os.environ.get("DRY_RUN", "1") == "1"
SEASON = 2026

def fetch_table(position: str):
    s = requests.Session()
    r = s.get(BASE_URL, headers=HDR, timeout=25)
    soup = BeautifulSoup(r.text, "lxml")
    tok = soup.find("input", attrs={"name": "__RequestVerificationToken"}).get("value")
    base = {"__RequestVerificationToken": tok, "ExecAction": "", "Sortby": "01",
            "KindCode": "A", "Year": str(SEASON), "Online": "01",
            "Position": position, "DefenceType": "99", "PageSize": "60"}
    header, rows = None, []
    for page in range(0, 12):
        d = dict(base); d["IndexOfPages"] = str(page)
        resp = s.post(ACTION, data=d, headers=HDR, timeout=30)
        sp = BeautifulSoup(resp.text, "lxml")
        t = sp.find("table")
        if not t:
            break
        trs = t.find_all("tr")
        if header is None:
            header = [c.get_text(strip=True) for c in trs[0].find_all(["th", "td"])]
        cnt = 0
        for tr in trs[1:]:
            cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
            if cells and len(cells) >= 10:
                rows.append(cells); cnt += 1
        if cnt == 0:
            break
    return header, rows

def f(v):
    try:
        s = str(v).replace(' ', '')
        return float(s) if s not in ('', '-', 'N/A') else None
    except Exception:
        return None

def i(v):
    try:
        return int(float(str(v).replace(' ', '')))
    except Exception:
        return None

print("=== 抓取官方打者成績（Position=01）===")
hb, bat = fetch_table("01")
print(f"  欄位 {len(hb)}，筆數 {len(bat)}")
print("=== 抓取官方投手成績（Position=02）===")
hp, pit = fetch_table("02")
print(f"  欄位 {len(hp)}，筆數 {len(pit)}")

# DB 連線
url = os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL") or ""
if not url:
    raise RuntimeError("DATABASE_PUBLIC_URL / DATABASE_URL 未設定")
conn = psycopg2.connect(url, cursor_factory=RealDictCursor)
cur = conn.cursor()
cur.execute("SELECT team_id::text tid, chinese_name, english_name FROM predictx.teams WHERE league='CPBL' AND english_name NOT LIKE '%%Deprecated%%'")
teams = cur.fetchall()
# CPBL 官網中文隊名 → DB english_name（DB 無中文隊名，需靜態對照）
CN2EN = {
    "中信兄弟": "CTBC Brothers",
    "樂天桃猿": "Rakuten Monkeys",
    "味全龍": "Wei Chuan Dragons",
    "富邦悍將": "Fubon Guardians",
    "台鋼雄鷹": "TSG Hawks",
    "統一7-ELEVEn獅": "Uni-President 7-ELEVEn Lions",
}
en2id = {t['english_name']: t['tid'] for t in teams}
# 長到短排序，避免「統一7-ELEVEn獅」被短前綴誤配
team_list = sorted([(cn, en2id.get(en), en) for cn, en in CN2EN.items() if en2id.get(en)],
                   key=lambda x: -len(x[0]))
print(f"\nDB CPBL 實隊 {len(teams)} 支：{sorted(en2id)}")

def parse_name(cell):
    m = re.match(r'^\d+(.*)$', cell)
    body = m.group(1) if m else cell
    for cn, tid, en in team_list:
        if body.startswith(cn):
            return tid, body[len(cn):].strip()
    return None, body

# 更新打者
def update_batters():
    idx = {h: n for n, h in enumerate(hb)}
    sql = """
        UPDATE predictx.cpbl_player_pr SET
            avg=%s, obp=%s, slg=%s, ops=%s, ops_plus=%s, pa=%s, games=%s,
            k_pct=%s, bb_pct=%s, babip=%s, iso=%s, sb_pct=%s, bip=%s,
            imported_at=NOW()
        WHERE team_id=%s::uuid AND season=%s AND player_name=%s
    """
    ok = miss = 0
    for row in bat:
        tid, name = parse_name(row[0])
        if not tid or not name:
            miss += 1; continue
        avg = f(row[idx['打擊率']]); obp = f(row[idx['上壘率']]); slg = f(row[idx['長打率']])
        iso = round(slg - avg, 3) if (slg is not None and avg is not None) else None
        vals = (avg, obp, slg, f(row[idx['整體攻擊指數']]), f(row[idx['OPS+']]),
                i(row[idx['打席']]), i(row[idx['出賽數']]),
                f(row[idx['K%']]), f(row[idx['BB%']]), f(row[idx['BABIP']]), iso,
                None, f(row[idx['BIP%']]),
                tid, SEASON, name)
        if DRY:
            ok += 1; continue
        cur.execute(sql, vals)
        if cur.rowcount:
            ok += cur.rowcount
        else:
            miss += 1
    return ok, miss

# 更新投手
def update_pitchers():
    idx = {h: n for n, h in enumerate(hp)}
    sql = """
        UPDATE predictx.cpbl_pitcher_pr SET
            era=%s, games=%s, ip=%s, whip=%s, b_avg=%s,
            k_pct=%s, bb_pct=%s, babip=%s, fip=%s, era_plus=%s,
            h9=%s, hr9=%s, imported_at=NOW()
        WHERE team_id=%s::uuid AND season=%s AND player_name=%s
    """
    ok = miss = 0
    for row in pit:
        tid, name = parse_name(row[0])
        if not tid or not name:
            miss += 1; continue
        vals = (f(row[idx['防禦率']]), i(row[idx['出賽數']]), f(row[idx['投球局數']]),
                f(row[idx['每局被上壘率']]), f(row[idx['被打擊率']]),
                f(row[idx['K%']]), f(row[idx['BB%']]), f(row[idx['BABIP']]),
                f(row[idx['FIP']]), f(row[idx['ERA+']]),
                f(row[idx['H9值']]), None,   # HR9 不在官方表，保留原值
                tid, SEASON, name)
        if DRY:
            ok += 1; continue
        cur.execute(sql, vals)
        if cur.rowcount:
            ok += cur.rowcount
        else:
            miss += 1
    return ok, miss

print("\n=== 更新打者 ===")
bo, bm = update_batters()
print(f"  匹配更新 {bo} / 未匹配 {bm}")
print("=== 更新投手 ===")
po, pm = update_pitchers()
print(f"  匹配更新 {po} / 未匹配 {pm}")

if DRY:
    print("\n【DRY-RUN】未寫入")
    conn.rollback()
else:
    conn.commit()
    print("\n✅ 已提交")
conn.close()
