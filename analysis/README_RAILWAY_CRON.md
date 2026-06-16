# Railway Cron Service 設定指南 — 五大賽事自動更新

> 對應 PredictX 五大賽事 ingestion 的雲端排程設定
> 適用於：gentle-spirit project / 6/16 起的新建 cron service

---

## 為什麼要這個？

預設的 `PredictX-分析服務`（現有 cron）只跑 `run_analysis.py` 做 AI 分析。
**賽事資料本身需要另一個 cron 定時從來源網站抓回雲端**，APP 才能有資料顯示。

---

## 設定步驟（5 分鐘可完成）

### 1. 新建 Empty Service

在 gentle-spirit project 內（您 6/16 已建立的 `distinguished-renewal` service 那個畫面）：

- 點 **Settings** 標籤
- **Source** → 點 **Connect Repo** → 選 `k06210621-dot/PredictX-Sports`
- **Root Directory** 輸入 `analysis`（不是 `/`）
- **Deploy** 旁邊的 settings icon → 設 Start Command

### 2. Start Command（兩種策略二選一）

#### 策略 A：5 大賽事一鍋煮（推薦簡單）

```
python run_all_ingest.py
```

Cron Schedule 設 `0 1,9 * * *`（UTC 台北 09:00 / 17:00 各跑一次）
涵蓋 MLB / NPB / CPBL / NBA / FIFA 全部，**省錢**（5 個 service → 1 個），犧牲一點精準度。

#### 策略 B：各聯盟精準排程

建 **5 個** cron service（成本高但精準）：

| Service 名稱 | Start Command | Cron Schedule (UTC) | 台北時間 |
|---|---|---|---|
| PredictX-MLB-Ingest | `python run_all_ingest.py --leagues MLB` | `0 1 * * *` | 09:00 |
| PredictX-NPB-Ingest | `python run_all_ingest.py --leagues NPB` | `0 9 * * *` | 17:00 |
| PredictX-CPBL-Ingest | `python run_all_ingest.py --leagues CPBL` | `0 2 * * *` | 10:00 |
| PredictX-NBA-Ingest | `python run_all_ingest.py --leagues NBA` | `0 6 * * *` | 14:00 |
| PredictX-FIFA-Ingest | `python run_all_ingest.py --leagues FIFA` | `0 3 * * *` | 11:00 |

每個 service 都要：
1. Empty Service
2. Connect Repo
3. Root Directory = `analysis`
4. Start Command = 上表
5. Cron Schedule = 上表

### 3. 環境變數

- **不需要** `CLOUD_API_URL`：程式內已預設 `https://predictx-sports-production.up.railway.app`
- **不需要** `DATABASE_URL`：這支程式不打 DB，純粹 POST API
- **不需要** `NVIDIA_API_KEY`：只有 AI 分析（另一個 service）才需要

### 4. 驗證

跑完後（5-10 分鐘），到您 Xcode 模擬器按 **Cmd+R** 重啟 APP，5 個聯賽分頁都應該有賽事資料。

若想立即驗證 Railway cron 跑成功：
- 點 service → **Deployments** 標籤 → 看「Last run」狀態
- 或 Logs 標籤 → 看本次跑 log

---

## 故障排除

### Log 出現 `❌ CPBL API HTTP 403`
CPBL 偶爾擋自動請求，內建重試 3 次會自動救回。
若連 3 次都失敗，可調 `ingest/cpbl.py` 第 22 行的 `delay = 2` 為 `delay = 5`。

### Log 出現 `❌ 上傳失敗`
檢查 CLOUD_API_URL 環境變數是否正確指向 `https://predictx-sports-production.up.railway.app`。

### 5 個 service 太多怎麼辦
直接用策略 A（一鍋煮），犧牲一點精準度但簡單很多。

---

## 最後一動：刪除測試 token

您 6/16 在 https://railway.app/account/tokens 生成的 `hermes-cli` token 已經用不到，**請到 Railway Dashboard → Account → Tokens → 刪除**。

（之前 CLI 報「Not Authorized」是 token 還沒生效，重新建立即可。Dashboard 點選法更直觀。）
