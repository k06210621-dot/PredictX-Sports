"""
Push Notification Service for PredictX Sports
使用 Apple Push Notification service (APNs) HTTP/2 協議發送推播通知

設計目標：當 run_analysis 完成新分析時，立即觸發推播給所有
啟用推播的 Premium 用戶（信心度 >= 8 的賽事）。

環境變數：
- APNS_KEY_ID: Apple APNs Key ID (e.g. V2YYWUGNMW)
- APNS_TEAM_ID: Apple Developer Team ID (e.g. 9KNQAT34D5)
- APNS_P8_BASE64: .p8 私密金鑰的 base64 編碼內容（避免 git 暴露原始 key）
- APNS_TOPIC: iOS Bundle ID（預設 com.predictxsports.app）
- APNS_USE_SANDBOX: 設 "true" 走 sandbox.push.apple.com（測試用），預設 false（生產）
"""

import os
import json
import time
import base64
import asyncio
import logging
import aiohttp
import jwt
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger("push_service")

# ==========================================
# 環境配置
# ==========================================

APNS_KEY_ID = os.environ.get("APNS_KEY_ID", "V2YYWUGNMW")
APNS_TEAM_ID = os.environ.get("APNS_TEAM_ID", "9KNQAT34D5")
APNS_TOPIC = os.environ.get("APNS_TOPIC", "com.predictxsports.app")
APNS_USE_SANDBOX = os.environ.get("APNS_USE_SANDBOX", "false").lower() == "true"
APNS_P8_BASE64 = os.environ.get("APNS_P8_BASE64", "")

APNS_HOST = (
    "https://api.sandbox.push.apple.com"
    if APNS_USE_SANDBOX
    else "https://api.push.apple.com"
)

# 信心度門檻：>= 8 才推播
CONFIDENCE_THRESHOLD = 8


# ==========================================
# JWT 簽章（APNs 要求 ES256，每小時重簽一次）
# ==========================================

_apns_jwt: Optional[str] = None
_jwt_expiry: float = 0.0
_p8_private_key: Optional[bytes] = None


def _load_p8_key() -> bytes:
    """載入 .p8 私密金鑰（從 base64 環境變數解碼）"""
    global _p8_private_key
    if _p8_private_key is not None:
        return _p8_private_key

    if not APNS_P8_BASE64:
        raise RuntimeError(
            "APNS_P8_BASE64 環境變數未設定。請在 Railway 設定後重啟。"
        )

    try:
        _p8_private_key = base64.b64decode(APNS_P8_BASE64)
    except Exception as e:
        raise RuntimeError(f"APNS_P8_BASE64 解碼失敗: {e}")

    return _p8_private_key


def _generate_apns_jwt() -> str:
    """生成 APNs JWT Token（ES256，每小時重簽一次）"""
    global _apns_jwt, _jwt_expiry

    now = time.time()
    # 還有 5 分鐘以上有效期就重用
    if _apns_jwt and now < _jwt_expiry - 300:
        return _apns_jwt

    p8_key = _load_p8_key()

    now_int = int(now)
    payload = {
        "iss": APNS_TEAM_ID,
        "iat": now_int,
    }

    _apns_jwt = jwt.encode(
        payload,
        p8_key,
        algorithm="ES256",
        headers={"kid": APNS_KEY_ID},
    )

    # APNs JWT 最長 1 小時有效
    _jwt_expiry = now + 3600
    logger.info(f"[APNs] JWT 重簽完成，過期時間 {datetime.fromtimestamp(_jwt_expiry).isoformat()}")
    return _apns_jwt


# ==========================================
# 單裝置推播（真實 HTTP/2）
# ==========================================

async def send_push_notification(
    device_token: str,
    title: str,
    body: str,
    data: Optional[dict] = None,
    badge: int = 1,
    sound: str = "default",
    category: str = "MATCH_NOTIFICATION",
) -> bool:
    """
    發送推播通知到指定裝置

    Returns:
        bool: 是否成功送達 APNs（HTTP 200）
    """
    if not device_token:
        logger.warning("[APNs] device_token 為空，跳過")
        return False

    url = f"{APNS_HOST}/3/device/{device_token}"
    headers = {
        "authorization": f"bearer {_generate_apns_jwt()}",
        "apns-topic": APNS_TOPIC,
        "apns-push-type": "alert",
        "apns-priority": "10",
        "apns-expiration": str(int(time.time()) + 86400),  # 24 小時後過期
        "content-type": "application/json",
    }

    payload = {
        "aps": {
            "alert": {"title": title, "body": body},
            "badge": badge,
            "sound": sound,
            "category": category,
            "mutable-content": 1,
        }
    }

    if data:
        # 自訂 payload 不能與 aps 同層保留 (Apple 限制)
        for key, value in data.items():
            if key != "aps":
                payload[key] = value

    try:
        # aiohttp 預設支援 HTTP/2（需要[h2]）→ 改用 ClientSession 顯式指定
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    logger.info(f"[APNs] 推播成功 → {device_token[:16]}...")
                    return True
                else:
                    error_text = await resp.text()
                    # APNs 410 = token 失效（用戶移除 App 或關閉推播）→ 標記為無效
                    # APNs 400 BadDeviceToken → 同上
                    logger.warning(
                        f"[APNs] 推播失敗 HTTP {resp.status}: {error_text} "
                        f"(token={device_token[:16]}...)"
                    )
                    return False
    except asyncio.TimeoutError:
        logger.error(f"[APNs] 推播逾時 (token={device_token[:16]}...)")
        return False
    except Exception as e:
        logger.error(f"[APNs] 推播異常: {e} (token={device_token[:16]}...)")
        return False


# ==========================================
# 單場比賽推播給多個裝置
# ==========================================

async def send_match_notification(
    device_tokens: List[str],
    match_info: dict,
    confidence: float,
) -> dict:
    """
    發送比賽推播通知給多個裝置

    Args:
        device_tokens: 接收者的 APNs device token 列表
        match_info: 比賽資訊，應包含 home_team/away_team/game_id/match_date
        confidence: AI 信心度（0-10）

    Returns:
        dict: {"success_count": int, "failed_count": int, "results": list}
    """
    # 信心度門檻檢查（防呆：即使外部呼叫也擋）
    if confidence < CONFIDENCE_THRESHOLD:
        logger.info(
            f"[APNs] 信心度 {confidence:.1f} < {CONFIDENCE_THRESHOLD}，跳過推播"
        )
        return {"success_count": 0, "failed_count": 0, "results": []}

    if not device_tokens:
        return {"success_count": 0, "failed_count": 0, "results": []}

    home_team = match_info.get("home_team", "主隊")
    away_team = match_info.get("away_team", "客隊")
    match_date = match_info.get("match_date", "")

    # 標題與內容設計（簡潔明瞭，避免過長）
    title = "⚾ PredictX 重點觀察賽事"
    body = f"{home_team} vs {away_team}\nAI 信心度 {confidence:.0f}/10"

    # 客製化 payload（iOS 端可從 userInfo 讀取）
    custom_data = {
        "type": "match_alert",
        "game_id": str(match_info.get("game_id", "")),
        "match_date": str(match_date),
        "confidence": float(confidence),
        "home_team": home_team,
        "away_team": away_team,
    }

    # 並行發送給所有裝置（每個獨立 timeout 10s）
    tasks = [
        send_push_notification(
            device_token=token,
            title=title,
            body=body,
            data=custom_data,
        )
        for token in device_tokens
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    success_count = sum(1 for r in results if r is True)
    failed_count = len(results) - success_count

    logger.info(
        f"[APNs] 推播完成：{home_team} vs {away_team} "
        f"(conf={confidence:.1f}) → {success_count}/{len(device_tokens)} 成功"
    )

    return {
        "success_count": success_count,
        "failed_count": failed_count,
        "results": results,
    }


# ==========================================
# 從 DB 抓取符合資格的裝置並發送
# ==========================================

def _fetch_premium_devices_sync(min_tier: str = "premium") -> List[str]:
    """
    從 DATABASE_URL 直接建立連線（背景 thread 使用，避免 Flask app context leak）
    用 psycopg2 + RealDictCursor 同步查詢
    """
    import os
    import psycopg2
    from psycopg2.extras import RealDictCursor

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        logger.error("[APNs] DATABASE_URL 未設定，無法查詢 device_tokens")
        return []
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT device_token
            FROM predictx.device_tokens
            WHERE tier = %s
              AND push_enabled = TRUE
              AND device_token IS NOT NULL
              AND device_token != ''
            """,
            (min_tier,),
        )
        rows = cur.fetchall()
        cur.close()
        return [r["device_token"] for r in rows if r]
    finally:
        conn.close()


# 🆕 [2026-06-27] 去重常數：同一 game_id 6 小時內不重複推播
PUSH_DEDUP_HOURS = 6


def _record_push_sync(game_id: str, devices_count: int, success_count: int) -> None:
    """
    記錄推播事件到 push_log 表（如果存在），供下次去重檢查使用
    用 predictx.push_log 表 + auto-create（無表就 skip，不影響功能）
    """
    import os
    import psycopg2
    from psycopg2.extras import RealDictCursor

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        return
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    try:
        cur = conn.cursor()
        # 檢查表是否存在
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'predictx'
                AND table_name = 'push_log'
            )
        """)
        has_table = cur.fetchone()["exists"]
        if not has_table:
            # 表不存在時自動建立（方便新環境快速啟用）
            cur.execute("""
                CREATE TABLE IF NOT EXISTS predictx.push_log (
                    id SERIAL PRIMARY KEY,
                    game_id UUID NOT NULL,
                    pushed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    devices_count INT NOT NULL DEFAULT 0,
                    success_count INT NOT NULL DEFAULT 0
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_push_log_game_time
                ON predictx.push_log(game_id, pushed_at DESC)
            """)
            conn.commit()

        cur.execute("""
            INSERT INTO predictx.push_log (game_id, devices_count, success_count)
            VALUES (%s::uuid, %s, %s)
        """, (game_id, devices_count, success_count))
        conn.commit()
        cur.close()
        logger.info(f"[APNs] push_log 記錄成功: game={game_id[:8]}... devices={devices_count} success={success_count}")
    except Exception as e:
        logger.error(f"[APNs] push_log 寫入失敗（non-fatal）: {e}")
        conn.rollback()
    finally:
        conn.close()


def _was_recently_pushed_sync(game_id: str, hours: int = PUSH_DEDUP_HOURS) -> bool:
    """
    檢查指定 game_id 是否在最近 N 小時內已推播過（用 ai_prediction_history 表的 prediction_time）
    用 predictx.push_log 表（如果存在），沒有就 fallback 到 ai_prediction_history.prediction_time + game_id 唯一性

    Returns:
        bool: True = 已推過（要跳過）, False = 未推過（可以推）
    """
    import os
    import psycopg2
    from psycopg2.extras import RealDictCursor

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        return False  # 無 DB 連線 → 預設不阻擋推播（避免配錯環境就完全沒推播）
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    try:
        cur = conn.cursor()
        # 先檢查 push_log 表是否存在（migration 安全設計）
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'predictx'
                AND table_name = 'push_log'
            )
        """)
        has_push_log = cur.fetchone()["exists"]

        if has_push_log:
            cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM predictx.push_log
                WHERE game_id = %s::uuid
                  AND pushed_at >= NOW() - (%s || ' hours')::interval
            """, (game_id, hours))
        else:
            # Fallback: 用 ai_prediction_history 最近 N 小時內的多筆快照當作去重依據
            # 同 game_id 在 N 小時內出現 >= 2 次 = 重複（首次分析 + N 小時後重分析）
            cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM predictx.ai_prediction_history
                WHERE game_id = %s::uuid
                  AND prediction_time >= NOW() - (%s || ' hours')::interval
            """, (game_id, hours))

        row = cur.fetchone()
        cur.close()
        cnt = int(row["cnt"]) if row else 0

        # 有 push_log 表時，>= 1 表示已推過
        # 用 ai_prediction_history fallback 時，>= 2 表示有重複（首次不算）
        threshold = 1 if has_push_log else 2
        return cnt >= threshold
    except Exception as e:
        logger.error(f"[APNs] 去重檢查失敗（non-fatal）: {e}")
        return False  # 檢查失敗時預設允許推播（避免誤擋）
    finally:
        conn.close()


async def trigger_match_push(
    match_info: dict,
    confidence: float,
    min_tier: str = "premium",
) -> dict:
    """
    從資料庫抓取符合資格（Premium + push_enabled）的裝置 token，並發送推播

    Args:
        match_info: 比賽資訊字典
        confidence: AI 信心度
        min_tier: 最低訂閱層級（premium/standard/basic/free），預設 premium

    Returns:
        dict: {"devices_found": int, "success_count": int, "failed_count": int, "skipped": str (optional)}
    """
    # 信心度門檻
    if confidence < CONFIDENCE_THRESHOLD:
        return {"devices_found": 0, "success_count": 0, "failed_count": 0, "skipped": "low_confidence"}

    # 🆕 去重檢查：同一 game_id 6 小時內不重複推播（防止 cron + iOS 強制重跑重複推送）
    game_id = match_info.get("game_id")
    if game_id:
        try:
            recently_pushed = await asyncio.to_thread(_was_recently_pushed_sync, str(game_id), PUSH_DEDUP_HOURS)
            if recently_pushed:
                logger.info(
                    f"[APNs] 跳過重複推播：game {str(game_id)[:8]}... "
                    f"在 {PUSH_DEDUP_HOURS} 小時內已推過"
                )
                return {"devices_found": 0, "success_count": 0, "failed_count": 0, "skipped": "recently_pushed"}
        except Exception as dedup_err:
            logger.error(f"[APNs] 去重檢查失敗（繼續推播）: {dedup_err}")

    # 用 to_thread 把同步 DB 查詢丟到 thread pool（不阻塞 event loop）
    device_tokens = await asyncio.to_thread(_fetch_premium_devices_sync, min_tier)

    if not device_tokens:
        logger.info(f"[APNs] 無 {min_tier} 用戶啟用推播（match: {match_info.get('game_id')}）")
        return {"devices_found": 0, "success_count": 0, "failed_count": 0}

    result = await send_match_notification(
        device_tokens=device_tokens,
        match_info=match_info,
        confidence=confidence,
    )

    # 🆕 推播完成 → 記錄到 push_log（供下次去重）
    if game_id and result.get("success_count", 0) > 0:
        try:
            await asyncio.to_thread(
                _record_push_sync,
                str(game_id),
                len(device_tokens),
                result["success_count"],
            )
        except Exception as rec_err:
            logger.error(f"[APNs] push_log 記錄失敗（不影響本次推播）: {rec_err}")

    return {
        "devices_found": len(device_tokens),
        "success_count": result["success_count"],
        "failed_count": result["failed_count"],
    }


# ==========================================
# 本地測試
# ==========================================

if __name__ == "__main__":
    # 測試 JWT 簽章（不實際發送）
    print(f"APNS_KEY_ID: {APNS_KEY_ID}")
    print(f"APNS_TEAM_ID: {APNS_TEAM_ID}")
    print(f"APNS_TOPIC: {APNS_TOPIC}")
    print(f"APNS_HOST: {APNS_HOST}")
    print(f"APNS_P8_BASE64 設定: {'✅' if APNS_P8_BASE64 else '❌'}")
    if APNS_P8_BASE64:
        token = _generate_apns_jwt()
        print(f"JWT 簽章成功（前 32 字元）: {token[:32]}...")
