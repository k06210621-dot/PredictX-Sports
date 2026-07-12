"""
Push Notification Cron Job for PredictX Sports
每日固定時間發送推播通知
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any

# 導入共用模組
from push_service import send_match_notification
from api_server import get_db


async def daily_push_notification():
    """每日固定時間發送推播通知
    
    1. 查詢今天/明天的高信心度賽事
    2. 查詢所有 Premium 用戶的 device token
    3. 發送推播通知
    """
    print(f"[{datetime.now()}] 開始每日推播任務")
    
    try:
        # 1. 取得資料庫連線
        from api_server import get_db
        conn = get_db()
        
        # 2. 查詢今天/明天的高信心度賽事
        today_str = datetime.now().strftime('%Y-%m-%d')
        tomorrow_str = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

        # ⚠️ [2026-06-29] 統一門檻為 >= 8（與 iOS App ProfileView.swift:575 顯示文字
        # 及 push_service.CONFIDENCE_THRESHOLD 一致）。之前用 > 8 會漏推 confidence = 8
        # 的賽事，造成 App 顯示「高信心度」但收不到通知的混淆。
        cur.execute("""
            SELECT g.game_id, g.home_team, g.away_team, g.match_date,
                   ga.analysis_data->>'confidence' as confidence
            FROM predictx.games g
            JOIN predictx.game_analysis ga ON g.game_id = ga.game_id
            WHERE g.match_date IN (%s, %s)
            AND g.status = 'SCHEDULED'
            AND (ga.analysis_data->>'confidence')::numeric >= 8
            ORDER BY g.match_date
        """, (today_str, tomorrow_str))
        
        games = cur.fetchall()
        
        if not games:
            print("今日/明日無高信心度賽事，跳過推播")
            return
        
        # 2. 取得所有 Premium 用戶的 device token
        cur.execute("""
            SELECT device_token 
            FROM predictx.device_tokens 
            WHERE tier = 'premium' AND push_enabled = true
        """)
        device_tokens = [row[0] for row in cur.fetchall()]
        
        if not device_tokens:
            print("無 Premium 用戶啟用推播，跳過發送")
            return
        
        # 3. 發送推播
        total_sent = 0
        for game in games:
            match_info = {
                'game_id': game[0],
                'home_team': game[1],
                'away_team': game[2],
                'match_date': game[3]
            }
            confidence = float(game[3])
            
            # 使用 push_service 的發送功能
            from push_service import send_match_notification
            sent = await send_match_notification(device_tokens, match_info, confidence)
            total_sent += 1
            
            print(f"  已發送: {match_info['home_team']} vs {match_info['away_team']} (信心度: {confidence:.1f}%) -> {sent} 台裝置")
        
        print(f"推播完成: 共發送 {total_sent} 場賽事到 {len(device_tokens)} 台裝置")
        
    except Exception as e:
        print(f"推播任務失敗: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主程式入口"""
    print(f"[{datetime.now()}] 開始每日推播任務")
    await daily_push_notification()
    print(f"[{datetime.now()}] 推播任務完成")


if __name__ == "__main__":
    asyncio.run(main())