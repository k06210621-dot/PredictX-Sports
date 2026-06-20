import Foundation
import GoogleMobileAds

/// AdMob 設定檔 — 獎勵廣告整合
enum AdMobConfig {
    /// APP ID（在 AdMob 後台 > Apps 取得）
    static let appID = "ca-app-pub-6186518924141006~8915583551"
    
    /// 獎勵廣告單元 ID（在 AdMob 後台 > Ad units 取得）
    static let rewardedAdUnitID = "ca-app-pub-6186518924141006/5661662420"
    
    /// 測試模式：設為 true 時使用測試廣告（不會產生收益但可正常開發測試）
    static let isTestMode = true
}
