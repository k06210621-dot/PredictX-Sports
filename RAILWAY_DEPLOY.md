# PredictX Sports Railway 一鍵部署指南（5 分鐘圖文版）

> 適用 macOS / iPhone 瀏覽器皆可，全程點滑鼠即可完成

---

## 步驟 1：建立 Railway 專案（30 秒）

1. 瀏覽器打開：https://railway.app/new
2. 點左側「Deploy from GitHub repo」
3. 找到 `k06210621-dot/PredictX-Sports`，點右側「Deploy Now」
4. 看到「Deploying…」就放著等 1-2 分鐘，會自動完成

---

## 步驟 2：加入 PostgreSQL 資料庫（20 秒）

1. 進入專案頁面後，點右上角「+ Add Resource」（或 + New 圖示）
2. 選「Database」→「PostgreSQL」
3. 自動建立，**不需要填任何東西**

---

## 步驟 3：讓 Web Service 連到 PostgreSQL（10 秒）

1. 點左側的 Web Service（會顯示「PredictX-Sports」）
2. 點「Variables」標籤
3. 點「+ New Variable」→「Add Reference」
4. 選 `DATABASE_URL`（從 PostgreSQL 拉過來）
5. 點確認

這樣 Web Service 就能連到資料庫了。

---

## 步驟 4：加 Ollama 環境變數（20 秒）

繼續在同一個 Variables 頁面，點「+ New Variable」→「Raw Variable」：

| Name | Value |
|------|-------|
| `OLLAMA_HOST` | 你的 Ollama Cloud 端點 URL |
| `FLASK_ENV` | `production` |

---

## 步驟 5：取得公開網域（20 秒）

1. 點 Web Service →「Settings」標籤
2. 找到「Domains」區塊
3. 點「Generate Domain」
4. 複製產生的網域（格式：`https://xxx.up.railway.app`）

---

## 步驟 6：驗證成功（10 秒）

瀏覽器打開：
```
https://你的網域.up.railway.app/health
```

看到這段 JSON 就代表成功：
```json
{"status":"healthy","service":"PredictX Analysis API"}
```

---

## 步驟 7：把網域貼給我

把步驟 5 拿到的網域貼在這裡，我會幫你：
1. 更新 iOS App 的 `baseURL`
2. 設定 Cron Job（每日自動分析）
3. 部署完成測試

---

## 遇到問題時的截圖位置

| 卡在哪 | 看哪裡 | 怎麼解決 |
|--------|--------|----------|
| 找不到 repo | 步驟 1.2 | 點右側「Configure GitHub access」授權 |
| Generate Domain 失敗 | 步驟 5 | 重新部署一次（點右上「Redeploy」） |
| /health 回 500 | 步驟 4 | 檢查 `OLLAMA_HOST` 有沒有填 |
| /health 回 404 | 步驟 1 | 確認是從 `analysis/` 目錄部署而非根目錄 |

---

## 之後每天自動跑的 Cron Job（我會幫你做）

`python run_analysis.py` 每日 08:30 / 17:30 台北時間，自動跑：
- 今日 + 明日賽事 AI 分析
- 結算（settlement）昨天的賽事
- 結果寫回資料庫，iOS App 自動看到新資料

---

開始吧！最簡單的做法是：
1. 點 https://railway.app/new
2. 截圖第一個畫面給我，我一步步帶你走
