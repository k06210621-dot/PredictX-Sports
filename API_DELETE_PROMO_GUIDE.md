# App Store Connect API 刪除促銷圖片指南

## ⚠️ 重要提醒
此方法需要額外的 API 金鑰設定，且操作較為複雜。**建議使用方法一（手動操作）**。

如果您仍希望使用 API，請遵循以下步驟：

## 前置條件

1. **生成 App Store Connect API 金鑰**
   - 登入 App Store Connect
   - 點選 **Users and Access** → **Keys**
   - 點擊 **Generate API Key**
   - 選擇 **App Manager** 角色
   - 下載 `.p8` 檔案（只能下載一次！）
   - 記錄 **Key ID** 和 **Issuer ID**

2. **安裝必要工具**
```bash
# 安裝 App Store Connect CLI（需 Ruby）
gem install appstore-connect
```

3. **設定環境變數**
```bash
export APPSTORE_CONNECT_API_KEY="/path/to/your/AuthKey_XXXXXXXXXX.p8"
export APPSTORE_CONNECT_KEY_ID="YOUR_KEY_ID"
export APPSTORE_CONNECT_ISSUER_ID="YOUR_ISSUER_ID"
```

## 使用 API 刪除促銷圖片

### 步驟 1: 取得 App ID
```bash
appstore-connect api get \
  "/v1/apps" \
  --query filter[bundleId]=com.predictxsports.app.dev
```

記錄回傳的 `id` 欄位（這是 App 的內部 ID）。

### 步驟 2: 取得所有 In-App Purchase 產品
```bash
appstore-connect api get \
  "/v1/apps/{APP_ID}/inAppPurchases"
```

### 步驟 3: 對每個產品刪除促銷圖片

對於每個有 `promotionalImage` 的產品：

```bash
appstore-connect api delete \
  "/v1/inAppPurchases/{IAP_ID}/relationships/promotionalImage"
```

## ⚠️ 注意事項

- API 操作不可逆，刪除後需重新上傳圖片
- 某些 API 端點可能需要額外權限
- 建議先在 Sandbox 環境測試

## 建議

**由於您的 Authentic Key (`AuthKey_GJBB8U3YDA.p8`) 是用於 APNs 推播通知，不是 App Store Connect API 金鑰**，兩者不同。

強烈建議您使用**方法一（手動操作）**，大約只需 5-10 分鐘即可完成所有設定。