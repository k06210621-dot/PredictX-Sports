#!/usr/bin/env python3
"""
從 Railway 容器視角測試 CPBL 系列 endpoint 是否會被阻擋。
這隻在 Railway 上跑才有意義（測的是 Railway container IP 的可達性）。
"""
import os
import sys
import urllib3
import requests

# 抑制 SSL 警告（Railway Python 不支援 CPBL 憑證）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def test(url, method="GET", data=None, headers=None, timeout=10):
    """簡單 endpoint 探測"""
    h = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    if headers:
        h.update(headers)
    try:
        r = requests.request(method, url, data=data, headers=h, timeout=timeout, verify=False)
        return r.status_code, len(r.text)
    except Exception as e:
        return f"ERR: {type(e).__name__}", str(e)[:80]


def main():
    print("=" * 60)
    print(f"從 {os.environ.get('RAILWAY_SERVICE_NAME', 'local')} 測試 CPBL endpoint")
    print("=" * 60)

    # 1. stats.cpbl.com.tw — 取得比賽清單
    url1 = "https://stats.cpbl.com.tw/schedule/2026-08-06"
    s1, l1 = test(url1)
    print(f"\n[1] GET {url1}")
    print(f"    status={s1}, len={l1}")

    # 2. stats.cpbl.com.tw 單場頁面
    url2 = "https://stats.cpbl.com.tw/schedule/2026-A-246"
    s2, l2 = test(url2)
    print(f"\n[2] GET {url2}")
    print(f"    status={s2}, len={l2}")

    # 3. cpbl.com.tw 首頁 — 用於取得 token
    url3 = "https://www.cpbl.com.tw/"
    s3, l3 = test(url3)
    print(f"\n[3] GET {url3}")
    print(f"    status={s3}, len={l3}")

    # 4. cpbl.com.tw/home/gamedetail (POST) — 取得 SP
    print("\n[4] POST https://www.cpbl.com.tw/home/gamedetail")
    # 先取 token
    try:
        home = requests.get("https://www.cpbl.com.tw/", timeout=10, verify=False,
                            headers={"User-Agent": "Mozilla/5.0"})
        import re
        token_m = re.search(r'__RequestVerificationToken[^>]*value="([^"]+)"', home.text)
        token = token_m.group(1) if token_m else ""
        print(f"    Token: {len(token)} chars")
    except Exception as e:
        token = ""
        print(f"    Token fetch failed: {e}")

    s4, l4 = test(
        "https://www.cpbl.com.tw/home/gamedetail",
        method="POST",
        data={"Year": "2026", "GameSno": "246", "KindCode": "A", "__RequestVerificationToken": token},
        headers={"Referer": "https://www.cpbl.com.tw/", "X-Requested-With": "XMLHttpRequest"},
    )
    print(f"    status={s4}, len={l4}")

    # 5. cpbl.com.tw/box/index (GET) — 成績看板
    url5 = "https://www.cpbl.com.tw/box/index?year=2026&kindCode=A&gameSno=246"
    s5, l5 = test(url5)
    print(f"\n[5] GET {url5}")
    print(f"    status={s5}, len={l5}")

    # 6. TheSportsDB — 備援
    url6 = "https://www.thesportsdb.com/api/json/v1/eventsround.php?id=5111&r=20&s=2026-2027"
    s6, l6 = test(url6)
    print(f"\n[6] GET {url6}")
    print(f"    status={s6}, len={l6}")

    # 7. PTT — 備援
    url7 = "https://www.ptt.cc/bbs/Baseball/index.html"
    s7, l7 = test(url7)
    print(f"\n[7] GET {url7}")
    print(f"    status={s7}, len={l7}")

    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  stats.cpbl.com.tw  : {s1}")
    print(f"  stats game page    : {s2}")
    print(f"  cpbl.com.tw home   : {s3}")
    print(f"  cpbl gamedetail    : {s4}")
    print(f"  cpbl box score     : {s5}")
    print(f"  TheSportsDB        : {s6}")
    print(f"  PTT                : {s7}")


if __name__ == "__main__":
    main()
