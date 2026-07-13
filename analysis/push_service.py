"""
Push Notification Service for PredictX Sports
使用 Apple Push Notification service (APNs) HTTP/2 協議發送推播通知
🆕 [Phase 4] 雙平台支援：APNs（iOS）+ FCM（Android）

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
import sys
import json
import time
import base64
import asyncio
import logging
import httpx
import jwt
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger("push_service")
# 確保 push_service 的 log 在 Railway cron 環境中可見
if not logger.handlers:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter('[APNs] %(message)s'))
    logger.addHandler(h)
    logger.setLevel(logging.INFO)
    logger.propagate = False

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
# 🆕 FCM (Android) 配置
# ==========================================

FCM_SERVICE_ACCOUNT_JSON = os.environ.get("FCM_SERVICE_ACCOUNT_JSON", "")
_fcm_app = None

def _get_fcm_app():
    """懶載入 Firebase Admin SDK（只在需要發送 Android FCM 推播時才初始化）
    
    需要 Railway 環境變數 FCM_SERVICE_ACCOUNT_JSON（Firebase 私鑰的完整 JSON 字串）。
    如果未設定，Android 推播會被跳過。
    """
    global _fcm_app
    if _fcm_app is not None:
        return _fcm_app
    if not FCM_SERVICE_ACCOUNT_JSON:
        logger.warning("[FCM] FCM_SERVICE_ACCOUNT_JSON 環境變數未設定，Android 推播將跳過")
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials
        service_account = json.loads(FCM_SERVICE_ACCOUNT_JSON)
        cred = credentials.Certificate(service_account)
        _fcm_app = firebase_admin.initialize_app(cred, name="predictx-fcm")
        logger.info("[FCM] Firebase Admin SDK 初始化成功")
        return _fcm_app
    except Exception as e:
        logger.error(f"[FCM] Firebase Admin SDK 初始化失敗: {e}")
        return None


async def send_fcm_notification(
    device_token: str,
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> dict:
    """發送 FCM 推播通知到指定 Android 裝置
    
    Returns:
        dict: {"token": str, "ok": bool, "remove": bool}
              remove=True 表示 token 永久失效（NotRegistered），應從 DB 清除。
    """
    if not device_token:
        return {"token": device_token, "ok": False, "remove": False}
    
    app = await asyncio.to_thread(_get_fcm_app)
    if app is None:
        return {"token": device_token, "ok": False, "remove": False}
    
    try:
        from firebase_admin import messaging
        
        fcm_data = data or {}
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in fcm_data.items()},
            token=device_token,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    channel_id="predictx_analytics",
                    priority="HIGH",
                ),
            ),
        )
        
        # firebase_admin.messaging.send 是同步，需要 thread-offload
        response = await asyncio.to_thread(messaging.send, message)
        logger.info(f"[FCM] 推播成功 → {device_token[:16]}... (msg_id={response[:12]}...)")
        return {"token": device_token, "ok": True, "remove": False}
        
    except messaging.UnregisteredError:
        logger.warning(f"[FCM] token 永久失效: {device_token[:16]}...")
        return {"token": device_token, "ok": False, "remove": True}
    except Exception as e:
        error_str = str(e)
        is_invalid = (
            "NotRegistered" in error_str
            or "InvalidRegistration" in error_str
            or "MismatchSenderId" in error_str
        )
        logger.warning(f"[FCM] 推播失敗: {e} (token={device_token[:16]}...)")
        return {"token": device_token, "ok": False, "remove": is_invalid}


async def send_fcm_match_notification(
    device_tokens: List[str],
    match_info: dict,
    confidence: float,
) -> dict:
    """發送比賽推播通知給 Android 裝置（FCM）"""
    if confidence < CONFIDENCE_THRESHOLD:
        return {"success_count": 0, "failed_count": 0, "results": []}
    if not device_tokens:
        return {"success_count": 0, "failed_count": 0, "results": []}
    
    home_team = match_info.get("home_team", "主隊")
    away_team = match_info.get("away_team", "客隊")
    
    title = "⚾ PredictX 重點觀察賽事"
    body = f"{home_team} vs {away_team}\nAI 信心度 {confidence:.0f}/10"
    
    custom_data = {
        "type": "match_alert",
        "game_id": str(match_info.get("game_id", "")),
        "match_date": str(match_info.get("match_date", "")),
        "confidence": float(confidence),
        "home_team": home_team,
        "away_team": away_team,
    }
    
    tasks = [
        send_fcm_notification(device_token=token, title=title, body=body, data=custom_data)
        for token in device_tokens
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    success_count = 0
    invalid_tokens = []
    for r in results:
        if isinstance(r, dict):
            if r.get("ok"):
                success_count += 1
            elif r.get("remove"):
                invalid_tokens.append(r.get("token"))
    
    logger.info(
        f"[FCM] 推播完成：{home_team} vs {away_team} "
        f"(conf={confidence:.1f}) → {success_count}/{len(device_tokens)} 成功"
        + (f"，{len(invalid_tokens)} 個失效 token 待清除" if invalid_tokens else "")
    )
    
    return {
        "success_count": success_count,
        "failed_count": len(device_tokens) - success_count,
        "results": results,
        "invalid_tokens": invalid_tokens,
    }


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
) -> dict:
    """
    發送推播通知到指定裝置

    Returns:
        dict: {"token": str, "ok": bool, "remove": bool, "status": int}
              ok=True 表示 HTTP 200 送達；
              remove=True 表示 token 永久失效（410 Unregistered / 400 BadDeviceToken），應從 DB 清除。
    """
    if not device_token:
        logger.warning("[APNs] device_token 為空，跳過")
        return {"token": device_token, "ok": False, "remove": False, "status": 0}

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
        # httpx 原生支援 HTTP/2（APNs 強制要求 HTTP/2）
        async with httpx.AsyncClient(http2=True, timeout=10.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                logger.info(f"[APNs] 推播成功 → {device_token[:16]}...")
                return {"token": device_token, "ok": True, "remove": False, "status": 200}
            else:
                error_text = resp.text
                logger.warning(
                    f"[APNs] 推播失敗 HTTP {resp.status_code}: {error_text} "
                    f"(token={device_token[:16]}...)"
                )
                # 判斷是否為「永久失效」→ 需從 DB 清除
                # 410 Unregistered：token 已失效（App 移除/重裝）
                # 400 BadDeviceToken：token 格式錯或 sandbox/production 環境不符
                reason = ""
                try:
                    reason = (json.loads(error_text) or {}).get("reason", "")
                except Exception:
                    pass
                remove = (
                    resp.status_code == 410
                    or (resp.status_code == 400 and reason == "BadDeviceToken")
                )
                return {"token": device_token, "ok": False, "remove": remove, "status": resp.status_code}
    except httpx.TimeoutException:
        logger.error(f"[APNs] 推播逾時 (token={device_token[:16]}...)")
        return {"token": device_token, "ok": False, "remove": False, "status": 0}
    except Exception as e:
        logger.error(f"[APNs] 推播異常: {e} (token={device_token[:16]}...)")
        return {"token": device_token, "ok": False, "remove": False, "status": 0}


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

    success_count = 0
    invalid_tokens = []
    for r in results:
        if isinstance(r, dict):
            if r.get("ok"):
                success_count += 1
            elif r.get("remove"):
                invalid_tokens.append(r.get("token"))
        # 例外（Exception）或非預期回傳一律視為非永久失敗，不清除
    failed_count = len(results) - success_count

    logger.info(
        f"[APNs] 推播完成：{home_team} vs {away_team} "
        f"(conf={confidence:.1f}) → {success_count}/{len(device_tokens)} 成功"
        + (f"，{len(invalid_tokens)} 個失效 token 待清除" if invalid_tokens else "")
    )

    return {
        "success_count": success_count,
        "failed_count": failed_count,
        "results": results,
        "invalid_tokens": invalid_tokens,
    }


# ==========================================
# 從 DB 抓取符合資格的裝置並發送
# ==========================================

def _get_push_db_conn():
    """取得 DB 連線（背景 thread 用，不複用 Flask 連線池）
    
    push_service 在 daemon thread 中執行，無法存取 Flask app context 的連線池，
    因此需要獨立建立連線。呼叫端負責 close。
    """
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        return None
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    import psycopg2
    from psycopg2.extras import RealDictCursor
    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)


def _fetch_premium_devices_sync(min_tier: str = "premium", conn=None) -> List[dict]:
    """從 DB 查詢符合資格的裝置（🆕 回傳包含 platform 資訊）"""
    own_conn = conn is None
    if conn is None:
        conn = _get_push_db_conn()
        if conn is None:
            logger.error("[Push] DATABASE_URL 未設定，無法查詢 device_tokens")
            return []
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT device_token, platform
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
        return [{"token": r["device_token"], "platform": r.get("platform", "ios")} for r in rows if r]
    finally:
        if own_conn:
            conn.close()


# 🆕 [2026-06-27] 去重常數：同一 game_id 6 小時內不重複推播
PUSH_DEDUP_HOURS = 6


def _remove_invalid_tokens_sync(tokens: List[str], conn=None) -> int:
    """從 predictx.device_tokens 刪除永久失效的 device token（410/BadDeviceToken）。

    收到 410 Unregistered 或 400 BadDeviceToken 代表該 token 已永久失效
    （App 已移除/重裝/環境不符），留著只會每次推播都白打。裝置若仍在使用，
    下次啟動會重新註冊新 token，因此直接刪除安全。

    Returns:
        int: 實際刪除的筆數
    """
    if not tokens:
        return 0
    own_conn = conn is None
    if conn is None:
        conn = _get_push_db_conn()
        if conn is None:
            return 0
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM predictx.device_tokens WHERE device_token = ANY(%s)",
            (list(tokens),),
        )
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        logger.info(f"[APNs] 已清除 {deleted} 個失效 device token")
        return deleted
    except Exception as e:
        logger.error(f"[APNs] 清除失效 token 失敗（non-fatal）: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return 0
    finally:
        if own_conn:
            conn.close()


def _record_push_sync(game_id: str, devices_count: int, success_count: int, conn=None) -> None:
    """記錄推播事件到 push_log 表（可傳入共用連線）"""
    own_conn = conn is None
    if conn is None:
        conn = _get_push_db_conn()
        if conn is None:
            return
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
        if own_conn:
            conn.close()


def _was_recently_pushed_sync(game_id: str, hours: int = PUSH_DEDUP_HOURS, conn=None) -> bool:
    """檢查 game_id 最近 N 小時內是否已推播（可傳入共用連線）

    Returns:
        True = 已推過（跳過）, False = 未推過（可以推）
    """
    own_conn = conn is None
    if conn is None:
        conn = _get_push_db_conn()
        if conn is None:
            return False  # 無 DB 連線 → 預設不阻擋推播
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
            cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM predictx.ai_prediction_history
                WHERE game_id = %s::uuid
                  AND prediction_time >= NOW() - (%s || ' hours')::interval
            """, (game_id, hours))

        row = cur.fetchone()
        cur.close()
        cnt = int(row["cnt"]) if row else 0

        threshold = 1 if has_push_log else 2
        return cnt >= threshold
    except Exception as e:
        logger.error(f"[APNs] 去重檢查失敗（non-fatal）: {e}")
        return False
    finally:
        if own_conn:
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

    game_id = match_info.get("game_id")

    # 建立一條共用 DB 連線（去重檢查 → 查裝置 → 記錄推播 全程複用）
    conn = await asyncio.to_thread(_get_push_db_conn)
    if conn is None:
        logger.error("[APNs] 無法建立 DB 連線，跳過推播")
        return {"devices_found": 0, "success_count": 0, "failed_count": 0, "skipped": "no_db"}

    try:
        # 去重檢查：同一 game_id 6 小時內不重複推播
        if game_id:
            try:
                recently_pushed = await asyncio.to_thread(_was_recently_pushed_sync, str(game_id), PUSH_DEDUP_HOURS, conn)
                if recently_pushed:
                    logger.info(
                        f"[APNs] 跳過重複推播：game {str(game_id)[:8]}... "
                        f"在 {PUSH_DEDUP_HOURS} 小時內已推過"
                    )
                    return {"devices_found": 0, "success_count": 0, "failed_count": 0, "skipped": "recently_pushed"}
            except Exception as dedup_err:
                logger.error(f"[APNs] 去重檢查失敗（繼續推播）: {dedup_err}")

        # 查詢符合資格的裝置（現在回傳含 platform 的 dict）
        devices = await asyncio.to_thread(_fetch_premium_devices_sync, min_tier, conn)

        if not devices:
            logger.info(f"[Push] 無 {min_tier} 用戶啟用推播（match: {match_info.get('game_id')}）")
            return {"devices_found": 0, "success_count": 0, "failed_count": 0}

        # 🆕 分離 iOS 與 Android tokens
        ios_tokens = [d["token"] for d in devices if d.get("platform", "ios") == "ios"]
        android_tokens = [d["token"] for d in devices if d.get("platform") == "android"]

        total_success = 0
        total_failed = 0
        all_invalid = []

        # iOS → APNs
        if ios_tokens:
            ios_result = await send_match_notification(
                device_tokens=ios_tokens,
                match_info=match_info,
                confidence=confidence,
            )
            total_success += ios_result.get("success_count", 0)
            total_failed += ios_result.get("failed_count", 0)
            all_invalid.extend(ios_result.get("invalid_tokens", []))
        else:
            ios_result = {"success_count": 0, "failed_count": 0, "invalid_tokens": []}

        # Android → FCM
        if android_tokens:
            fcm_result = await send_fcm_match_notification(
                device_tokens=android_tokens,
                match_info=match_info,
                confidence=confidence,
            )
            total_success += fcm_result.get("success_count", 0)
            total_failed += fcm_result.get("failed_count", 0)
            all_invalid.extend(fcm_result.get("invalid_tokens", []))
        else:
            fcm_result = {"success_count": 0, "failed_count": 0, "invalid_tokens": []}

        # 推播完成 → 記錄到 push_log（供下次去重）
        if game_id and total_success > 0:
            try:
                await asyncio.to_thread(
                    _record_push_sync,
                    str(game_id),
                    len(devices),
                    total_success,
                    conn,
                )
            except Exception as rec_err:
                logger.error(f"[Push] push_log 記錄失敗（不影響本次推播）: {rec_err}")

        # 清除永久失效的 tokens（410 Unregistered / NotRegistered）
        removed_count = 0
        if all_invalid:
            try:
                removed_count = await asyncio.to_thread(
                    _remove_invalid_tokens_sync, all_invalid, conn
                )
            except Exception as rm_err:
                logger.error(f"[Push] 清除失效 token 失敗（不影響本次推播）: {rm_err}")

        return {
            "devices_found": len(devices),
            "ios_devices": len(ios_tokens),
            "android_devices": len(android_tokens),
            "success_count": total_success,
            "failed_count": total_failed,
            "removed_invalid": removed_count,
        }
    finally:
        conn.close()


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
