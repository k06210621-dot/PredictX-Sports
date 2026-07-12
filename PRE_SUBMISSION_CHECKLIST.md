# PredictX Sports - Apple 審查前檢查清單

**檢查日期**: 2026-06-28  
**版本**: 1.0 (Build 11 → 12)  
**檢查目標**: 確保所有 Apple 審查問題已改善

---

## ✅ Guideline 3.1.2(c) - 訂閱資訊完整性檢查

### 問題描述
Apple 要求 App 內必須包含：
- 訂閱方案名稱
- 訂閱長度
- 價格
- **功能性連結**到隱私權政策
- **功能性連結**到服務條款（EULA）

### 修正檢查

| 項目 | 狀態 | 檢查方式 | 結果 |
|------|------|----------|------|
| **使用 SubscriptionStoreView** | ✅ | 檢查程式碼 | 已使用 Apple 官方組件 |
| **訂閱方案名稱** | ✅ | 自動顯示 | Basic / Standard / Premium |
| **訂閱長度** | ✅ | 自動顯示 | 月訂 / 年訂 |
| **價格顯示** | ✅ | 自動顯示 | 從 App Store Connect 同步 |
| **隱私權政策連結** | ✅ | 手動設定 | https://k06210621-dot.github.io/privacy/ |
| **服務條款連結** | ✅ | Apple 標準 EULA | 使用 Apple 預設條款 |

### 程式碼驗證

```swift
// ✅ 已正確集成
SubscriptionStoreView(productIDs: subscriptionManager.allProductIDs)
    .frame(height: 400)
    .cornerRadius(12)

// ✅ 隱私權政策網址正確
private let privacyPolicyURL = URL(string: "https://k06210621-dot.github.io/privacy/")!
```

### Product IDs 驗證

```swift
// ✅ 月訂方案
"com.predictxsports.basic.monthly"
"com.predictxsports.standard.monthly"
"com.predictxsports.premium.monthly"

// ✅ 年訂方案
"com.predictxsports.basic.yearly"
"com.predictxsports.standard.yearly"
"com.predictxsports.premium.yearly"
```

**注意**: 請確認這些 Product IDs 已在 App Store Connect 中**正確建立**且狀態為**「核准」**。

---

## ✅ Guideline 2.3.2 - 促銷圖片問題檢查

### 問題描述
Apple 指出：
- 提交了重複或相同的促銷圖片給不同方案
- 使用 App 截圖作為促銷圖片
- 圖片中的文字太小或難以閱讀

### 建議處理方案

#### 方案 A（推薦）：刪除所有促銷圖片
**優點**:
- 快速解決問題
- 不需要設計資源
- 不影響核心功能

**步驟**:
1. 登入 App Store Connect
2. 進入 **Monetization** → **Subscriptions**
3. 點選每個訂閱方案
4. 刪除 **Promotional Image** 欄位的圖片
5. 儲存

#### 方案 B：重新設計促銷圖片
**要求**:
- 每個方案使用**獨特**的圖片
- 不使用 App 截圖
- 文字清晰可讀（建議至少 72pt）
- 尺寸：1024x500 像素（Required）

**建議設計方向**:
- Basic: 綠色主題，強調「每日 120 點數」
- Standard: 藍色主題，強調「無限點數 + 驗證率」
- Premium: 紫色主題，強調「無限 + 推播通知」

### 檢查結果

| 處理方式 | 狀態 | 備註 |
|----------|------|------|
| 刪除所有促銷圖片 | ⏳ **待確認** | 需登入 App Store Connect 檢查 |
| 或重新設計圖片 | ⏳ **待決定** | 如選擇此方案，需提供設計稿 |

---

## 📋 App Store Connect 設定檢查清單

### 必要設定

| 項目 | 狀態 | 檢查步驟 | 結果 |
|------|------|----------|------|
| **Privacy Policy URL** | ⏳ 待確認 | App Store → Privacy Policy URL 欄位 | 應填寫：`https://k06210621-dot.github.io/privacy/` |
| **Apple 標準 EULA** | ⏳ 待確認 | App Information → EULA | 勾選使用 Apple 標準條款 |
| **或 App Description** | ⏳ 待確認 | App Store → Description | 加入 EULA 連結 |

### 如何設定 Apple 標準 EULA

**方法 1：使用 App Information 欄位**
1. App Store Connect → PredictX Sports
2. **App Information**（App 資訊）
3. 滾動到 **EULA** 欄位
4. 貼上：`https://www.apple.com/legal/internet-services/itunes/dev/stdeula/`
5. 儲存

**方法 2：在 App Description 中提及**
在 App 描述中加入：
```
服務條款：本 App 使用 Apple 標準服務條款（EULA）。
https://www.apple.com/legal/internet-services/itunes/dev/stdeula/
```

---

## 🧪 本地測試計畫

### 測試環境
- **測試設備**: iPhone 16 Plus (iOS 26.6) 或 Simulator
- **測試帳號**: 使用 Sandbox 測試帳號（不要用真實 Apple ID）

### 測試步驟

#### Step 1: 編譯與運行
```bash
cd "/Users/jero/PredictX Sports"
# 在 Xcode 中
# 1. 選擇 Scheme: PredictX Sports
# 2. 選擇目標設備：iPhone 16 Plus 或 Simulator
# 3. 執行：Product → Run (Cmd+R)
```

#### Step 2: 檢查訂閱頁面
1. 開啟 App
2. 導航到 **個人資訊** 分頁
3. 點選 **訂閱中心** 或 **升級 Premium**
4. 確認看到以下內容：

**iOS 17+ 設備應看到**:
- ✅ Apple SubscriptionStoreView 組件
- ✅ 所有 6 個方案（3 種方案 × 2 種週期）
- ✅ 方案名稱（Basic / Standard / Premium）
- ✅ 訂閱長度（月訂 / 年訂）
- ✅ 價格顯示
- ✅ 隱私權政策連結（可點擊）
- ✅ 服務條款連結（可點擊）

**iOS 16 設備應看到**:
- ✅ Fallback 訊息
- ✅ 隱私權政策連結

#### Step 3: 測試隱私權政策連結
1. 在訂閱頁面找到「隱私權政策」連結
2. 點擊連結
3. 確認 Safari 開啟並導向：`https://k06210621-dot.github.io/privacy/`
4. 確認頁面內容正確顯示

#### Step 4: 檢查視覺效果
- [ ] 所有文字清晰可讀
- [ ] 按鈕大小適合點擊（最小 44x44pt）
- [ ] 顏色對比度足夠
- [ ] 無 UI 錯位或截斷

#### Step 5: 截圖記錄
建議截圖以下畫面供審查參考：
1. 訂閱中心主頁面（顯示 SubscriptionStoreView）
2. 隱私權政策頁面（Safari）
3. 方案詳情（點擊任一方案後的細節）

---

## 📸 審查回应準備

### 截圖清單（建議準備）

1. **訂閱頁面主視圖**
   - 顯示完整的 SubscriptionStoreView
   - 可見所有方案和價格

2. **隱私權政策連結**
   - 特寫連結位置
   - 顯示連結可點擊

3. **Safari 開啟隱私權政策**
   - 顯示網址列：`https://k06210621-dot.github.io/privacy/`
   - 顯示頁面內容

4. **（可選）服務條款連結**
   - 如果 SubscriptionStoreView 有自動顯示

### 回覆 Apple 的範本

請參考 `/Users/jero/PredictX Sports/APPLE_REVIEW_RESPONSE_GUIDE.md` 中的範本。

---

## ⚠️ 潛在風險與注意事項

### 1. Product IDs 不匹配
**風險**: 如果 App 中的 Product IDs 與 App Store Connect 中設定的不一致
**症狀**: SubscriptionStoreView 顯示空白或錯誤
**解決**: 確認兩邊的 IDs 完全一致（大小寫敏感）

### 2. App Store Connect 設定未完成
**風險**: Privacy Policy URL 未設定或錯誤
**症狀**: Apple 可能再次退件
**解決**: 在提交前再次確認所有設定

### 3. 促銷圖片問題未處理
**風險**: 如果促銷圖片仍存在且不符合規範
**症狀**: Guideline 2.3.2 再次被退件
**解決**: 建議先刪除所有促銷圖片

---

## ✅ 最終檢查清單（提交前）

在點擊「提交審核」前，請確認：

### 程式碼與建構
- [ ] SubscribeView.swift 已更新為 SubscriptionStoreView 版本
- [ ] 程式碼已 Commit 並 Push 到 Git
- [ ] Xcode 編譯無錯誤（Cmd+B）
- [ ] 已在 Simulator 或實機上測試過
- [ ] 隱私權政策連結可正常開啟

### App Store Connect 設定
- [ ] Privacy Policy URL 已設定為正確網址
- [ ] Apple 標準 EULA 已設定（在 App Information 或 Description）
- [ ] 所有 In-App Purchase 產品狀態為「核准」或「準備提交」
- [ ] 促銷圖片已刪除或更新為符合規範的版本

### 提交資料
- [ ] 已準備好審查回應範本
- [ ] 已準備好截圖（可選但建議）
- [ ] 新版本已上傳（Build 12 或更高）
- [ ] 已選擇正確的 Build 進行提交

---

## 📝 測試結果記錄

### 測試日期：________________

#### 測試人員：________________

#### 測試設備：
- [ ] iPhone 16 Plus (iOS 26.6)
- [ ] Simulator (iOS ___)
- [ ] 其他：__________

#### 測試結果：
| 測試項目 | 通過 | 失敗 | 備註 |
|----------|:----:|:----:|------|
| SubscriptionStoreView 顯示 | ☐ | ☐ | |
| 所有方案正確顯示 | ☐ | ☐ | |
| 隱私權政策連結可點擊 | ☐ | ☐ | |
| 隱私權政策頁面開啟成功 | ☐ | ☐ | |
| UI 無錯位或截斷 | ☐ | ☐ | |
| 按鈕大小合適 | ☐ | ☐ | |

#### 發現的問題：
_________________________________
_________________________________
_________________________________

#### 修正措施：
_________________________________
_________________________________
_________________________________

#### 是否可以提交：
- [ ] ✅ 是，所有測試通過
- [ ] ❌ 否，需先修正上述問題

---

**最後更新**: 2026-06-28  
**文件位置**: `/Users/jero/PredictX Sports/PRE_SUBMISSION_CHECKLIST.md`