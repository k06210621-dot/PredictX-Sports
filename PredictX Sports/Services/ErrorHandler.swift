import Foundation

/// 將 API 錯誤轉換為使用者友善的中文錯誤訊息
/// 避免直接顯示 iOS 內部的技術錯誤碼（如 NSURLErrorDomain）
func userFriendlyError(_ error: Error) -> String {
    let nsError = error as NSError
    switch nsError.code {
    case NSURLErrorNotConnectedToInternet:
        return "網路連線中斷，請檢查您的 Wi-Fi 或行動數據"
    case NSURLErrorTimedOut:
        return "連線逾時，可能是網路環境不穩定，請稍後再試"
    case NSURLErrorCannotConnectToHost, NSURLErrorCannotFindHost:
        return "無法連線至分析伺服器，請稍後再試"
    case NSURLErrorNetworkConnectionLost:
        return "網路連線不穩定，請檢查網路狀態後重試"
    case NSURLErrorDNSLookupFailed:
        return "DNS 解析失敗，請檢查網路連線設定"
    case NSURLErrorSecureConnectionFailed, NSURLErrorServerCertificateUntrusted:
        return "安全連線驗證失敗，請確認網路環境安全"
    case 400...499:
        return "請求資料異常，請嘗試重新整理頁面"
    case 500...599:
        return "分析系統暫時忙碌中，我們已記錄此問題並將盡快修復"
    default:
        // 檢查錯誤描述是否包含常見關鍵字
        let desc = nsError.localizedDescription.lowercased()
        if desc.contains("json") || desc.contains("parse") || desc.contains("decode") || desc.contains("serializ") {
            return "賽事資料格式異常，請嘗試下拉重新整理"
        }
        if desc.contains("timeout") {
            return "連線逾時，可能是網路環境不穩定，請稍後再試"
        }
        if desc.contains("cancelled") || desc.contains("cancel") {
            return "請求已取消"
        }
        if desc.contains("404") || desc.contains("not found") {
            return "查無此賽事分析資料"
        }
        return "暫時無法取得資料，請稍後再試"
    }
}

/// 根據錯誤類型回傳對應的圖示名稱
func errorIcon(_ error: Error) -> String {
    let nsError = error as NSError
    switch nsError.code {
    case NSURLErrorNotConnectedToInternet:
        return "wifi.slash"
    case NSURLErrorTimedOut:
        return "clock.badge.exclamationmark"
    case NSURLErrorCannotConnectToHost:
        return "antenna.radiowaves.left.and.right.slash"
    case 500...599:
        return "exclamationmark.icloud"
    default:
        return "exclamationmark.triangle.fill"
    }
}