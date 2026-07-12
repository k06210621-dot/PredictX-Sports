# PredictX Sports - Apple 審查回應指南

## 📋 本次修正內容（Guideline 3.1.2(c)）

### 已完成的 App 內修正：

1. **✅ 使用 Apple 官方 SubscriptionStoreView**
   - 位置：`PredictX Sports/Features/Profile/SubscribeView.swift`
   - 功能：自動包含所有 Guideline 3.1.2(c) 要求的必要資訊
     - 訂閱方案名稱（Basic / Standard / Premium）
     - 訂閱長度（月訂 / 年訂）
     - 價格顯示（NT$ 100/290/390 月訂，NT$ 990/2990/3850 年訂）
     - **功能性連結到隱私權政策**：https://k06210621-dot.github.io/privacy/
     - **功能性連結到服務條款**：使用 Apple 標準 EULA

2. **✅ 隱私權政策連結**
   - 使用現有網址：https://k06210621-dot.github.io/privacy/
   - 已在 SubscriptionStoreView 中自動整合

3. **✅ 服務條款（EULA）**
   - 使用 **Apple 標準 EULA**（不需自建頁面）
   - 在 App Store Connect 勾選即可

---

## 🔧 App Store Connect 設定步驟

### Step 1: 設定 Apple 標準 EULA

1. 登入 [App Store Connect](https://appstoreconnect.apple.com)
2. 進入 **PredictX Sports** → **App Store** 分頁
3. 滾動到頁面底部的 **App Description**（App 描述）區域
4. 在描述文字中加入以下內容（如果還沒有）：

```
服務條款：本 App 使用 Apple 標準服務條款（EULA）。
https://www.apple.com/legal/internet-services/itunes/dev/stdeula/
```

5. 或者在 **App Information** → **EULA** 欄位中，選擇使用 Apple 標準 EULA

### Step 2: 設定隱私權政策連結

1. 在 **App Store** 分頁
2. 找到 **Privacy Policy URL**（隱私權政策網址）欄位
3. 確認已填入：`https://k06210621-dot.github.io/privacy/`
4. 儲存

### Step 3: 上傳新版本

1. 在 Xcode 中建構新版本（建議 Build 12）
2. Archive 並上傳到 App Store Connect
3. 在 **1.0 提交項目** 中選擇新的 Build
4. 提交審核

---

## 📝 回覆 Apple 審查團隊的範本

```
尊敬的 Apple App Review 團隊，

感謝您的審查與寶貴意見。我們已針對 Guideline 3.1.2(c) 的問題完成了以下修正：

【App 內修正】
1. 已使用 Apple 官方的 SubscriptionStoreView 重構訂閱頁面
   - 自動包含所有必要資訊：方案名稱、訂閱長度、價格
   - 自動包含功能性連結到隱私權政策：https://k06210621-dot.github.io/privacy/
   - 自動包含功能性連結到服務條款（使用 Apple 標準 EULA）

【App Store Metadata 修正】
1. 隱私權政策網址已設定：https://k06210621-dot.github.io/privacy/
2. 服務條款：使用 Apple 標準 EULA
   https://www.apple.com/legal/internet-services/itunes/dev/stdeula/

【測試說明】
1. 請在 App 內前往「個人資訊」→「訂閱中心」查看所有訂閱方案
2. SubscriptionStoreView 會自動顯示所有必要資訊和連結
3. 隱私權政策連結可正常開啟外部瀏覽器

我們已確認 App 和 Metadata 都已包含所有 Guideline 3.1.2(c) 要求的資訊。
如有任何問題，請隨時告訴我們。

祝好，
PredictX Sports 開發團隊
```

---

## 🎯 關於 Guideline 2.3.2（促銷圖片）的說明

如果您的 In-App Purchase 有設定「促銷圖片」（Promotional Image），需要額外處理：

### 檢查步驟：
1. 進入 App Store Connect → PredictX Sports
2. 點選 **Monetization** → **Subscriptions**
3. 點選任一訂閱方案（如 Premium Monthly）
4. 檢查是否有上傳 **Promotional Image**

### 如果有上傳：
- **選項 A**：確保每個方案的促銷圖片都是**獨特的**（不使用相同圖片）
- **選項 B**：如果不需要促銷功能，可以**刪除所有促銷圖片**

### 促銷圖片規範：
- ❌ 不能使用 App 截圖
- ❌ 不能使用重複的圖片（不同方案要用不同圖）
- ❌ 文字不能太小或難以閱讀
- ✅ 建議使用專門設計的訂閱方案宣傳圖

### 建議處理：
由於這不是核心功能，**建議先刪除所有促銷圖片**，專注解決 Guideline 3.1.2(c) 的問題。後續可以再加回符合規範的促銷圖片。

---

## ✅ 檢查清單

在提交審核前，請確認：

- [ ] 新版本已上傳到 App Store Connect（Build 12 或更高）
- [ ] App Store Connect 的 Privacy Policy URL 已設定為正確網址
- [ ] App Description 或 App Information 中已包含 Apple 標準 EULA 連結
- [ ] 已測試 App 內的訂閱頁面可以正常顯示 SubscriptionStoreView
- [ ] 已測試隱私權政策連結可以正常開啟
- [ ] （如有）已處理所有 In-App Purchase 的促銷圖片問題

---

## 📞 需要協助？

如果有任何問題或需要進一步的技術支援，請隨時聯繫。

**最後更新**：2026-06-28