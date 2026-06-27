import SwiftUI
import GoogleMobileAds
import UIKit
import UserNotifications

/// AppDelegate — 在 App 啟動時初始化第三方 SDK
/// - Google Mobile Ads SDK（廣告）
/// - APNs 推播註冊（用於 Premium 推播通知功能）
///
/// SwiftUI App 必須用 UIApplicationDelegateAdaptor 才能呼叫傳統 AppDelegate 邏輯
final class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {

    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        // 1. Google Mobile Ads SDK 初始化
        // SDK 11.x：GADMobileAds 已重新命名為 MobileAds（Swift 命名空間現代化）
        let ads: MobileAds = MobileAds.shared
        ads.start(completionHandler: { _ in
            // 初始化完成
        })

        // 2. 設定 UNUserNotificationCenter delegate（讓前景也能收到推播）
        UNUserNotificationCenter.current().delegate = self

        // 3. 註冊 APNs 推播（背景模式）
        application.registerForRemoteNotifications()

        return true
    }

    // MARK: - APNs 註冊結果

    /// APNs 註冊成功 → 拿到 device token
    func application(_ application: UIApplication,
                     didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        let tokenString = deviceToken.map { String(format: "%02x", $0) }.joined()
        #if DEBUG
        print("📱 [APNs] device token: \(tokenString)")
        #endif
        // 傳送到後端 /api/register_device
        Task {
            await PushServiceManager.shared.registerDeviceToken(tokenString)
        }
    }

    /// APNs 註冊失敗
    func application(_ application: UIApplication,
                     didFailToRegisterForRemoteNotificationsWithError error: Error) {
        #if DEBUG
        print("❌ [APNs] 註冊失敗: \(error.localizedDescription)")
        #endif
    }

    /// 背景收到推播（silent push 或 content-available）
    func application(_ application: UIApplication,
                     didReceiveRemoteNotification userInfo: [AnyHashable: Any],
                     fetchCompletionHandler completionHandler: @escaping (UIBackgroundFetchResult) -> Void) {
        #if DEBUG
        print("📩 [APNs] 收到背景推播: \(userInfo)")
        #endif
        completionHandler(.newData)
    }

    // MARK: - UNUserNotificationCenterDelegate

    /// 前景時收到推播的顯示選項
    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        // 前景也顯示 banner + 播放聲音
        completionHandler([.banner, .sound, .badge])
    }

    /// 使用者點擊推播後的行為
    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                didReceive response: UNNotificationResponse,
                                withCompletionHandler completionHandler: @escaping () -> Void) {
        let userInfo = response.notification.request.content.userInfo
        #if DEBUG
        print("👆 [APNs] 使用者點擊推播: \(userInfo)")
        #endif
        // 處理 deep link（如果有 game_id 可跳轉到賽事詳情）
        if let gameId = userInfo["game_id"] as? String {
            NotificationCenter.default.post(
                name: .pushNotificationTapped,
                object: nil,
                userInfo: ["game_id": gameId]
            )
        }
        completionHandler()
    }
}

// MARK: - 推播點擊事件名稱

extension Notification.Name {
    static let pushNotificationTapped = Notification.Name("pushNotificationTapped")
}
