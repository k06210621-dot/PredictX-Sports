# PredictX Sports 後端 Runbook

> **緊急時的故障排除手冊**
> 最後更新：2026-06-20

---

## 🚨 緊急聯絡

| 服務 | 用途 | 連結 |
|:----|:----|:----|
| Railway Dashboard | 服務狀態 / 部署 | https://railway.com |
| Sentry | 錯誤監控 | https://sentry.io |
| TheSportsDB | CPBL/MLB/NBA/NPB API | https://www.thesportsdb.com |
| PredictX API | 線上 API | https://predictx-sports-production.up.railway.app |

---

## 📊 服務架構

```
┌─────────────────────────────────────────────────┐
│ Railway                                           │
│                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌────────┐│
│  │ predictx-api │  │predictx-ingest│ │settle  ││
│  │  (always-on) │  │ (cron 02:00) │ │(22:30) ││
│  │  Port: $PORT │  │              │ │        ││
│  └──────┬───────┘  └──────┬───────┘  └───┬────┘│
│         │                 │              │     │
│         └─────────────────┼──────────────┘     │
│                           ↓                     │
│                   ┌──────────────┐             │
│                   │   Postgres    │             │
│                   └──────────────┘             │
└─────────────────────────────────────────────────┘
```

---

## ✅ 日常檢查清單

### 每日

- [ ] 確認 Railway 服務狀態（綠色 = 正常）
- [ ] 檢查 `/health` 端點：`curl https://predictx-sports-production.up.railway.app/health`
- [ ] 確認昨日 settlement 有跑（`/analytics/overall` 顯示新資料）
- [ ] 確認 Ingest 有抓到當日賽事（`/api/games?days=1` 應有資料）

### 每週

- [ ] 查看 Railway 用量（`25 days or $X left`）
- [ ] Sentry dashboard 看錯誤趨勢
- [ ] 檢查 PostgreSQL 連線數

---

## 🆘 常見問題與處理

### Q1：`/health` 回 503

**症狀**：Railway health check 失敗，服務被重啟

**可能原因**：
| 原因 | 排查方法 |
|:----|:----|
| DB 連線失敗 | 看 `/health` 回應的 `checks.database` 欄位 |
| 環境變數缺失 | 看 `checks.env_vars` 欄位 |

**處理步驟**：
1. `curl https://predictx-sports-production.up.railway.app/health`
2. 看 `checks` 區塊哪項失敗
3. 若 DB 失敗 → Railway 重啟服務通常會恢復（connection pool 重置）
4. 若 env 缺失 → Railway Dashboard > Variables 補上

### Q2：Ingest 抓不到 CPBL 賽事

**症狀**：歷史賽事顯示 `SCHEDULED` 無分數

**可能原因**：
| 原因 | 症狀 |
|:----|:----|
| TheSportsDB API 失效 | `curl https://www.thesportsdb.com/api/v1/json/123/eventsday.php?d=2026-06-19&l=5111` |
| TheSportsDB rate limit (429) | log 中出現 "rate limit hit" |
| DB 寫入失敗 | log 中出現 `INSERT` 錯誤 |

**處理步驟**：
1. 直接 curl TheSportsDB 測試
2. 若 429 → 等 60 秒後重試
3. 若永久失效 → 看 Q6 切換資料來源

### Q3：AI 分析沒跑

**症狀**：`/api/run_analysis` 觸發後 `analyzed=0`

**可能原因**：
| 原因 | 排查 |
|:----|:----|
| 沒賽事可分析 | 查 `pending` 欄位 |
| NVIDIA_API_KEY 失效 | log 看 401/403 |
| Ollama service 不可用 | 若是本地模型，看 Railway logs |

**處理步驟**：
1. `curl -X POST https://predictx-sports-production.up.railway.app/api/run_analysis`
2. 看 `pending` 和 `analyzed` 數字
3. 若 pending > 0 但 analyzed = 0 → 看 log 找錯誤

### Q4：Settlement 沒跑

**症狀**：昨日賽事仍顯示「等待 AI 結算」

**可能原因**：
| 原因 | 排查 |
|:----|:----|
| Cron job 沒觸發 | Railway Dashboard > predictx-settlement > Logs |
| analysis_data 為空 | 用 `/api/game_analysis/{game_id}` 查 |
| POSTPONED 賽事未處理 | run `_settle_postponed_games()` 手動 |

**處理步驟**：
1. Railway Dashboard 看 cron job log
2. 若有失敗 → 重跑 cron
3. 若分析資料為空 → 手動 trigger：`curl -X POST .../api/run_analysis`

### Q5：API 回應慢

**症狀**：APP 載入超過 5 秒

**可能原因**：
| 原因 | 排查 |
|:----|:----|
| DB 查詢慢 | Railway Postgres Metrics |
| Gunicorn worker 全佔用 | `Procfile` 改 `--workers 4` |
| AI 分析卡住 | 看 settlement log |

**處理步驟**：
1. Railway Metrics 看 CPU / Memory
2. 若 worker 全佔用 → 重啟服務或加 worker

### Q6：CPBL 資料來源失效

**情境**：TheSportsDB 也壞了

**備用方案**（依優先級）：
1. **TheSportsDB 付費版**（$9/月）— 較穩定
2. **手動更新比分** — 用 `/api/update_score` 單場更新
3. **抓新聞網站** — `ltn.com.tw`、`udn.com` 賽事頁
4. **暫停 CPBL** — APP 隱藏 CPBL tab

---

## 🔧 維運指令

### 手動觸發 Ingest

```bash
curl -X POST https://predictx-sports-production.up.railway.app/api/insert_games \
  -H "Content-Type: application/json" \
  -d '{"games": [{"season": 2026, "match_date": "2026-06-20", "home_team": "Team A", "away_team": "Team B", "status": "FINAL", "home_team_score": 5, "away_team_score": 3}]}'
```

### 手動觸發 Settlement

```bash
curl -X POST https://predictx-sports-production.up.railway.app/analytics/settle
```

### 手動觸發 AI 分析

```bash
curl -X POST https://predictx-sports-production.up.railway.app/api/run_analysis
```

### 手動寫入 AI 分析（單場）

```bash
curl -X POST https://predictx-sports-production.up.railway.app/api/update_analysis \
  -H "Content-Type: application/json" \
  -d '{
    "game_id": "uuid-here",
    "analysis_data": {
      "home_team": "Team A",
      "away_team": "Team B",
      "home_win_probability": 0.6,
      "away_win_probability": 0.4,
      "confidence": 7.0,
      "summary": "...",
      "key_factors": [],
      "risk_factors": []
    }
  }'
```

---

## 📋 環境變數清單

| 變數 | 必要 | 說明 |
|:----|:---:|:----|
| `DATABASE_URL` | ✅ | Railway Postgres 自動注入 |
| `NVIDIA_API_KEY` | ✅ | NVIDIA NIM API（AI 分析）|
| `PREDICTX_MODEL` | ✅ | `cloud` 或 `local` |
| `THESPORTSDB_API_KEY` | ⚠️ | CPBL 抓取（預設 123 免費版）|
| `SENTRY_DSN` | ⚠️ | Sentry 錯誤監控 |
| `RAILWAY_ENVIRONMENT` | ⚠️ | 自動設為 `production` |
| `PORT` | ✅ | Railway 自動注入 |
| `CLOUD_API_URL` | ⚠️ | Ollama 服務（如用本地模型）|

---

## 🗓 排程時間表

| 時間 | Service | 動作 |
|:----:|:----|:----|
| 02:00 | predictx-ingest | 抓取當日 + 未來 2 天賽事 |
| 22:30 | predictx-settlement | 結算所有 FINAL 賽事 + 標記 POSTPONED |

---

## 📞 上架前必備

- [ ] Privacy Policy 公開 URL（必要）
- [ ] App Store 截圖 5 張（必要）
- [ ] Apple Developer 繳費 NT$3,300/年
- [ ] AppIcon 18 個尺寸完整（已確認）
- [ ] AdMob 整合測試（已設，須測試）

---

## 📝 變更歷史

| 日期 | 變更 | 影響 |
|:----|:----|:----|
| 2026-06-20 | CPBL 改用 TheSportsDB | 修好 6/19 比分問題 |
| 2026-06-20 | 多 service 拆分 | API/Ingest/Settlement 獨立 |
| 2026-06-20 | /health 完整檢查 | DB + env 驗證 |
| 2026-06-20 | Sentry 整合 | 錯誤自動回報 |
| 2026-06-17 | 移除 FIFA 預測 | 聚焦 MLB/NBA/NPB/CPBL |
| 2026-06-17 | 新增 NPB fetcher 月曆 | 修好樂天/羅德等配對 |