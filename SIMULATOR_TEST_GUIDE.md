# PredictX Sports - Simulator 測試指南

**測試日期**: 2026-06-28  
**測試目標**: 確認訂閱頁面符合 Apple 審查要求

---

## 🚀 步驟 1：在 Xcode 中打開專案

```bash
open "/Users/jero/PredictX Sports/PredictX-Sports.xcworkspace"
```

**注意**: 一定要打開 `.xcworkspace` 而不是 `.xcodeproj`（因為有 CocoaPods 相依性）

---

## 🚀 步驟 2：選擇 Scheme 和設備

1. **選擇 Scheme**: 在 Xcode 頂部工具列，確認選擇 **PredictX Sports**
2. **選擇設備**: 點擊設備下拉選單，選擇：
   - **iPhone 17** (推薦)
   - 或任何可用的 iOS Simulator
3. **確認編譯成功**: 按 **Cmd+B** 編譯，確認沒有錯誤

---

## 🚀 步驟 3：運行 App

按 **Cmd+R** 或點擊 Xcode 頂部的 **▶️ Run** 按鈕

Simulator 會自動啟動並運行 PredictX Sports App。

---

## 🧪 步驟 4：測試訂閱頁面

### 4.1 導航到訂閱中心

1. 在 App 底部導航列，點擊 **個人資訊**（人形圖示）
2. 找到並點擊 **訂閱中心** 或 **升級 Premium** 按鈕

### 4.2 檢查事項

請確認看到以下內容：

#### ✅ 基本佈局
- [ ] 頁面標題：「AI 額度儲值中心」
- [ ] 頂部有金色皇冠圖示
- [ ] 標題文字：「解鎖完整 AI 分析引擎」
- [ ] 副標題：「四大運動聯盟 50+ 項特徵因子・即時推論・模型驗證率公開透明」

#### ✅ 法律保證列（膠囊狀）
- [ ] 左側：「新手登入贈禮：30 天・每天 60 點」（礼物圖示）
- [ ] 中間：「隨時升級」（星星圖示）
- [ ] 右側：「App Store 安全交易」（鎖頭圖示）

#### ✅ SubscriptionStoreView（重要！）
- [ ] 看到 Apple 官方的訂閱介面組件
- [ ] 顯示所有 6 個方案：
  - Basic 每月 (NT$ 100)
  - Basic 每年 (NT$ 990)
  - Standard 每月 (NT$ 290)
  - Standard 每年 (NT$ 2990)
  - Premium 每月 (NT$ 390)
  - Premium 每年 (NT$ 3850)
- [ ] 每個方案正確顯示：
  - 方案名稱
  - 訂閱長度（月/年）
  - 價格
  - 方案描述

#### ✅ 補充說明區塊
- [ ] 文字：「新手登入即享 30 天贈禮：每天補充 60 分析點數。30 天後如未訂閱，仍可透過觀看廣告獲得額外點數。」
- [ ] 文字：「• 訂閱會自動續訂・可在 iPhone「設定」>「Apple ID」>「訂閱項目」中隨時取消」
- [ ] 文字：「• PredictX Sports 為運動數據分析工具・所有 AI 推論結果僅供參考・不構成任何投注建議」

#### ✅ 隱私權政策連結（iOS 16 fallback）
- 如果您使用的是 iOS 16 Simulator：
  - [ ] 看到「隱私政策」可點擊連結
- 如果您使用的是 iOS 17+ Simulator：
  - [ ] 隱私權政策連結已自動包含在 SubscriptionStoreView 中

#### ✅ 恢復購買按鈕
- [ ] 底部有「恢復購買」按鈕（藍色，時鐘圖示）

---

## 📸 步驟 5：截圖記錄

建議截圖以下畫面（供審查參考）：

1. **訂閱中心主頁面**
   - 顯示完整的 SubscriptionStoreView
   - 可見所有方案和價格

2. **法律保證列特寫**
   - 顯示「新手登入贈禮：30 天・每天 60 點」

3. **補充說明區塊**
   - 顯示新手贈禮說明文字

4. **（可選）隱私權政策連結**
   - 點擊後在 Safari 中開啟的頁面

---

## ⚠️ 常見問題排查

### 問題 1：SubscriptionStoreView 顯示空白
**原因**: Product IDs 不匹配或 App Store Connect 未設定

**解決**:
- 確認 App Store Connect 中已建立所有 6 個產品
- 確認 Product IDs 完全一致（大小寫敏感）
- 使用 Sandbox 測試帳號

### 問題 2：看不到所有方案
**原因**: Product IDs 未正確載入

**解決**:
- 檢查 Xcode Console 是否有錯誤訊息
- 確認 `SubscriptionManager.allProductIDs` 包含所有 6 個 IDs

### 問題 3： Simulator 無法安裝 App
**原因**: Build 設定問題

**解決**:
- 清理組建產品：`Product` → `Clean Build Folder` (Shift+Cmd+K)
- 重新編譯：`Cmd+B`
- 確保打開的是 `.xcworkspace` 而不是 `.xcodeproj`

---

## ✅ 檢查清單總結

在關閉 Simulator 前，請確認：

- [ ] App 可以正常啟動
- [ ] 可以導航到訂閱中心
- [ ] SubscriptionStoreView 正常顯示
- [ ] 所有 6 個方案可見
- [ ] 「新手登入贈禮」文字正確
- [ ] 隱私權政策連結可點擊（或已自動包含）
- [ ] 無 UI 錯位或文字截斷

---

## 📝 測試結果記錄

### 測試日期：________________

### 測試人員：________________

### 測試設備：
- [ ] iPhone 17 Simulator (iOS 26.x)
- [ ] 其他：________________

### 測試結果：

| 檢查項目 | 通過 | 失敗 | 備註 |
|----------|:----:|:----:|------|
| App 正常啟動 | ☐ | ☐ | |
| 訂閱中心可達 | ☐ | ☐ | |
| SubscriptionStoreView 顯示 | ☐ | ☐ | |
| 所有 6 個方案正確 | ☐ | ☐ | |
| 新手贈禮文字正確 | ☐ | ☐ | |
| 隱私權政策連結 | ☐ | ☐ | |
| 無 UI 問題 | ☐ | ☐ | |

### 發現的問題：
_________________________________
_________________________________
_________________________________

### 是否可以提交審核：
- [ ] ✅ 是，所有測試通過
- [ ] ❌ 否，需先修正上述問題

---

## 🎯 下一步

如果所有測試通過：

1. **Commit 並 Push 程式碼**
   ```bash
   cd "/Users/jero/PredictX Sports"
   git add .
   git commit -m "feat(subscribe): 使用 SubscriptionStoreView 符合 Apple Guideline 3.1.2(c)"
   git push origin main
   ```

2. **在 Xcode 中建構 Archive**
   - `Product` → `Archive`
   - 等待 Archive 完成

3. **上傳到 App Store Connect**
   - 在 Organizer 中點擊 `Distribute App`
   - 選擇 `App Store Connect`
   - 選擇 `Upload`

4. **在 App Store Connect 提交審核**
   - 選擇新的 Build
   - 使用審查回應範本回覆 Apple

---

**文件位置**: `/Users/jero/PredictX Sports/SIMULATOR_TEST_GUIDE.md`  
**最後更新**: 2026-06-28