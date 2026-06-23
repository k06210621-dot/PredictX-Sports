import SwiftUI
import GoogleMobileAds
import UIKit

/// AppDelegate — 在 App 啟動時初始化 Google Mobile Ads SDK
/// SwiftUI App 必須用 UIApplicationDelegateAdaptor 才能呼叫傳統 AppDelegate 邏輯
final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        // 🆕 [2026-06-23] 初始化 Google Mobile Ads SDK
        // 必須在 App 啟動時呼叫，否則 RewardedAd.load() 會失敗
        // SDK 11.x：GADMobileAds 已重新命名為 MobileAds（Swift 命名空間現代化）
        let ads: MobileAds = MobileAds.shared
        ads.start(completionHandler: { _ in
            // 初始化完成（正式版不需 print）
        })
        return true
    }
}
