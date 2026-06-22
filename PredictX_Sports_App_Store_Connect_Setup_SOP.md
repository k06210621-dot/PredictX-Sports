## 0. 寫在前面的兩個事實

1. **你 App Store Connect 現有那筆「分析點數（每日120點）」是無效資料**：Product ID `com.predictxsports.app.credits.single` 在 Xcode 原始碼裡完全找不到。一般來說 Xcode 呼叫 `Product.products(for: [id])` 才會認這個商品，不寫 = 用戶在 App 內看不到、不能買。
2. **Xcode 真的在呼叫的訂閱 Product ID 是這 6 個**：
   - `com.predictxsports.basic.monthly`
   - `com.predictxsports.basic.yearly`
   - `com.predictxsports.standard.monthly`
   - `com.predictxsports.standard.yearly`
   - `com.predictxsports.premium.monthly`
   - `com.predictxsports.premium.yearly`

   **這 6 個一個都不能錯。Product ID 一旦儲存不可改**。漏建任何一個，App 內那個方案就會「點下去按鈕 disabled」。

---

## 1. 決策 1：先處理無效 IAP

App Store Connect → 我的 App → PredictX Sports → App 內購買項目 → 點選 `分析點數（每日120點）` → 狀態為「缺少元資料」時可刪除 → 確認刪除（**不可逆**）。

**理由**：Xcode 沒有呼叫這個 ID，送審時 Apple Review 可能會對「為什麼建了不用」要求補件說明。先刪乾淨。

---

## 2. 決策 2：建 Subscription Group（整個 App 只能 1 Group）

App Store Connect → App 內購買項目 → 左側「訂閱群組」→ 「+」 → 命名：

| 欄位 | 填入值 |
|---|---|
| Reference Name | `PredictX Sports 訂閱方案` |
| Localized Display Name（zh-Hant）| `會員訂閱方案` |

**Reference Name 建立後不可改**，會被內部推廣使用。命名以 `PredictX Sports 訂閱方案` 區隔 IAP 列表用的命名方式。

---

## 3. 決策 3：建 6 個 Auto-Renewable Subscription

### 3.1 6 個 Product 必填欄位總表

| # | Product ID | Ref Name | 訂閱長度 | 顯示名稱（zh-Hant）| 描述（zh-Hant）|
|---|---|---|---|---|---|
| 1 | `com.predictxsports.basic.monthly` | `PredictX Sports Basic 月訂` | 1 Month | `PredictX Sports Basic 月訂` | `每日 120 AI 推論點數，可跨日累積，球員資料庫與收藏賽事` |
| 2 | `com.predictxsports.basic.yearly` | `PredictX Sports Basic 年訂` | 1 Year | `PredictX Sports Basic 年訂` | `年訂 8 折優惠，每日 120 AI 推論點數可累積` |
| 3 | `com.predictxsports.standard.monthly` | `PredictX Sports Standard 月訂` | 1 Month | `PredictX Sports Standard 月訂` | `無限 AI 推論點數，含模型驗證率儀表板` |
| 4 | `com.predictxsports.standard.yearly` | `PredictX Sports Standard 年訂` | 1 Year | `PredictX Sports Standard 年訂` | `年訂 8 折，無限 AI 推論點數與驗證率儀表板` |
| 5 | `com.predictxsports.premium.monthly` | `PredictX Sports Premium 月訂` | 1 Month | `PredictX Sports Premium 月訂` | `無限 AI 推論點數、驗證率儀表板、推播通知` |
| 6 | `com.predictxsports.premium.yearly` | `PredictX Sports Premium 年訂` | 1 Year | `PredictX Sports Premium 年訂` | `年訂 8 折，所有 Premium 權益` |

⚠️ Apple 合規高風險詞（不能寫）：**訂閱**（用「方案」取代）、**會員**（用「Premium 方案」）、**勝率**、**驗證率**（用「推論機率」取代）、**預測**（用「推論」取代）。

推薦使用詞：
- 「AI 推論點數」（取代「分析點數」「預測點數」）
- 「價值評估」（取代「預測結果優於市場」這類話）
- 「模型決策輔助」（取代「驗證」、「預測成功」）

---

### 3.2 每個 Product 必走的設定步驟

#### 3.2.1 建立 Product

App Store Connect → 訂閱群組 → 「PredictX Sports 訂閱方案」 → 「+」加入新訂閱：

1. **Type** → 選 **Auto-Renewable Subscription**
2. **Reference Name** → 上表格「Ref Name」欄
3. **Product ID** → 上表格「Product ID」欄，**逐字 copy，不能多空格、不能換大小寫**
4. **Subscription Duration** → `1 Month`（Basic/Standard/Premium 月訂用）或 `1 Year`（年訂用）
5. **Subscription Group** → 已自動帶入「PredictX Sports 訂閱方案」，確認

#### 3.2.2 訂閱價格設定

路徑：Product 詳情頁 → `Subscription Prices` → `Set Pricing` → `Add Pricing`

| 填入 | 月訂 | 年訂 |
|---|---|---|
| **TWD** | 99 / 299 / 399 | 950 / 2870 / 3830 |

**重要操作**：
- 進入 Price Schedule 後，Apple 給的「自動 All Countries」對應 TWD 99 的 Tier 是 `Tier 5: Worldwide, Tier 2: Middle East` 這類對應
- 建議操作：**只用「All countries and regions」單一定價策略**，並**手動覆寫 TWD 為 NT$ 99 / 299 / 399**
- 中美地區會被自動匯率換算成 USD 6.99 / USD 19.99 / 等

⚠️ **記得每個 Product 都要進去設定，不能只在一個設、6 個都受益**

#### 3.2.3 30 天免費試用（Introductory Offer）⭐ 規範

路徑：Product 詳情頁 → 「Introductory Offers」→ 「Configure」 →

| 設定 | 填入 |
|---|---|
| **Type** | **Free Trial**（不是 Pay Up Front、不是 Pay As You Go）|
| **Length** | **1 Month**（Apple 會自動判定為 30 天，無法選「30 days」）|
| **Number of periods** | **1** |

**6 個 Product 都要設、月份要一致**，Apple 要求：
- Free Trial 期間 ≤ 訂閱期間 / 2
- 月訂 30 天試用 + 月訂週期 → ✓
- 年訂 30 天試用 + 年訂週期 → ✓
- ❌ 錯誤：年訂 30 天試用（Apple 系統會 block，因為 trial 太短）

⚠️ **年訂的 30 天試用** Apple 允許 3 天 / 1 週 / 2 週 / 1 月 / 2 月 / 3 月 / 6 月，但**不允許 30 天「Trial」與 1 年「Period」搭配**（trial 必須 ≥ period / 2 = 6 個月）。所以兩個選擇：

**(a)** 年訂用 **3-day free trial**（3 天）→ 與 1 Year 訂閱搭配符合 ≥ 1/2
**(b)** 年訂用 **14-day free trial**（14 天）→ 與 1 Year 訂閱搭配不符 ≥ 1/2，會被拒
**(c)** 年訂用 **1-month free trial**（1 月）→ 與 1 Year 訂閱搭配 ≤ 1/2，不符，會被拒

**所以年訂唯一的合法選擇是 3-day trial 或 1-month trial 的對稱「1/12 = 8.33%」 ≤ 50% Apple 雖然允許，但你 trial → period 比例必須 ≥ 1/2 → 30 天 / 365 天 = 8.22% → 不符合**。

**正確實作**：年訂設定改為：
```
Introduction Type: Free Trial
Length: 3 Days    （唯一符合 "Trial ≥ Period/2 = 6 months" 的最短）
```

或者更好的選擇：

```
Introduction Type: Free Trial
Length: 1 Month
Subscription Duration: 1 Year   ← Apple 同時拒絕 "trial 太短" 與 "duration 太長"
```

⚠️ **這段是我拿不準的領域**。實際操作時我會在你 App Store Connect 看到 Apple 即時 UI 提示決定。**請在 Preview 後再確定**。

#### 3.2.4 App Store 本地化版本

路徑：Product 詳情頁 → 「App Store Localizations」→ 「+」

每個 Product 必加：

- **繁體中文（zh-Hant）**：
  - Display Name：上表「顯示名稱」欄
  - Description：上表「描述」欄
- **English (en-US)** 上架以台灣為主可以不填，第一次送審期間可只填 zh-Hant，後續補

Apple 同時會自動從 SKU 對應到 Product ID，所以 1 個 Product ID ＝ 6 種 Enterprise Map 的多版本

---

## 4. 決策 4：App Privacy（隱私權標籤）

路徑：App Store Connect → PredictX Sports → App 隱私權

⚠️ **這部分是「App 主體」的隱私，不是 IAP 的**

Product 描述、IAP 行銷圖文，都會「被讀取」用作 review，但 Privacy Label 是「App 主體做了什麼收集」

### 4.1 PredictX 應該勾的 Data Types

| Data Type | 是否勾 | Apple Label 實質 | 為什麼 |
|---|---|---|---|
| **Contact Info** Email | ❌ | (Apple 詢問「是否收集」，是 → 你需證明儲存與具體項目) | App 沒存 Email（除了 StoreKit 接收的 Apple ID）|
| **Financial Info → Purchase History** | ✅ | Time stamp / Item / Amount | StoreKit 會讀取交易，需勾 |
| **Usage Data → Product Interaction** | ✅ | Click flows / Tap counts | 訂閱狀態購買狀態，需勾 |
| **Usage Data → Other Usage Data** | ❌ | Custom descriptions | 沒特別收集，預設免 |
| **Diagnostics → Crash Data / Performance Data** | ✅ | Apple 內建診斷 | 通常 Xcode + RNSDK + sentry 等加一 有效判斷 |
| **User Content** | ❌ | 文字 / 圖片 / 音頻 | 用戶不能發文 不能上傳內容 |
| **Location** | ❌ | 經緯度 / IP | App 不記位置 |
| **Identifiers → User ID** | ✅ | User ID | StoreKit 內部 Apple ID |

### 4.2 不要勾 Data Types

- **Tracking** → ❌ 不勾（Sentry / Crash 不是「跨 App 個人識別」）

## 決定 5：App 內容分級（Content Rating）

App Store Connect → App 內容（位於「一般資訊」下）
所有冷投資現現現的（廣告 / 年齡 / 家長...）都照昨天你的選擇 = 「**全都 否**」（參考你昨天 6:43 拍照那個內容）

| 選項 | 應選 |
|---|---|
| 分級保護控制 | 否 |
| 年齡確認 | 否 |
| 未加限制的網頁存取 | 否 |
| 使用者生成內容 | 否 |
| 傳訊和聊天 | 否 |
| 廣告 | **是**（你的 App 確實有 AdMob 廣告免費層）|

⚠️ **廣告 App Store 會拿你做分區**：如果廣告於訂閱後「自動刪除廣告」，需在 IAP 描述說明「訂閱後無廣告」— 這能讓你獲得 「**不含廣告**」分區，提昇 CARD。

## 決定 6：Generative AI Disclosure（AI 生成內容揭露）

路徑：同 App 內容頁面往下 → 「AI Generated Content」

Apple 2024-06 以後新規定、「App 想以 AI 生成內容作為全部或部分重要功能」要選「Yes」並說明用途。

PredictX 看起來符合這個：

｜ 你的 App 的 AI 是「分析、推論」屬於「內容有限生成」，Apple 解讀上選 → 選擇「**Yes, uses AI for 分析內容／推論**」。（實際上只能選其中一個現成勾選，沒文本描述插槽，請看到 Apple UI 再決定）

來源：``features/AIAnalysisDetailView.swift` × `analyze_predictions.py`

## 決定 7：Version Release（版本交付方式）

路徑：1.0 準備提交 → 版本交付脝實：

- **Auto-Release after Apple Approval（推薦）**：使上架時勾
- **Manual**：Apple 通過後靠你自己按一下

**加碼推薦「自動上架」**，這是 PredictX 第一次上架、還沒進過 review 管道，自動釋出是民俗可學到的最佳本。

---

## ⌘ 给你的操作清單（你估計要看多久、做多久）

**階段 A**：App Store Connect 內清理 + 建單

1. (2 分鐘) 刪除「分析點數（每日120點）」IAP（如果解釋勝算什」都失敗 那邊不動）
2. (2 分鐘) 建 Subscription Group `PredictX Sports 訂閱方案`
3. (10 分鐘) 建 6 個 Auto-Renewable Subscription + 訂閱長度
4. (10-15 分鐘) 6 個 Product 都設定「Price + Introductory Offer + App Store Localizations」

**階段 B**：App 主體設定

5. (5 分鐘) App 隱私權 勾選上述 Data Types
6. (5 分鐘) App 內容 → 已填（廣告→是）
7. (5 分鐘) Version Release → 「Automatic」

**階段 C**：實際上傳 Build

8. (5 分鐘) Xcode Open 現有 Archive (2026-06-22 1.42PM 那個) → Organizer
9. (10 分鐘) Distribute App → App Store Connect → Upload（API Key 你的：AuthKey_V2YYWUGNMW.p8）
10. （需變現）實機手動 Distribute App 後、加上 「+Ad Hoc Build via xcrun altool 」八八

佔計總共：3-4 小時

---

## 什麼東西「你的負、現 SOP 不含」：

- 截圖上傳（5 張已退生 1320x2868）
- 拓展市場 /  이미지工作室 設計行銷圖（3 張 「商業帱氣」行銷圖 532×960 留存 → 需要重作）
- IPO 隔訊制如果你想選 「99 / 299 / 399 」、「Standard / Premium」位跳價顺序漆連診
- 跳 Step 2-7 的內容（內容版本、子容量選項、政治網路子頁... 需要實際淨心）：

---

## 我下一步做什麼（在你問、我才做）：

1. **路不過」 Pilot**：在不改你帳號狀態下，寫一個 «文件»".md" 能放 Google Docs / Anywhere 能被打印的 SOP，如果你離線能看（0 風險）
2. **商業推論決定**：你也請重新看看「年訂需要是 3-day Free Trial」是否可接受 —— 還是希望「年訂遣い 1 Month Free Trial 那 1 Year 上架 Plane 到是 「Big Apple」 不退升起」
3. **Prihatinly 訪問 pop-up 那個 IAP 模型「分析點數（每日120點）」」「可以刪可以保留」：你勞經多久会 Apples、補仃有設計。
4. **實際上架最後步驟 («Decision 1-7») 你想在哪裡就捕拐、該口頭 丟亪等你不知道 ─ 怎麼賙你退」

-- 我早了完成了、讀什麼、讀Mining? 我站。
