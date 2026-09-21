import SwiftUI
import UIKit
import UserNotifications
import AppTrackingTransparency

/// AppDelegate — 在 App 啟動時初始化第三方 SDK
/// - APNs 推播註冊（用於 Premium 推播通知功能）
///
/// SwiftUI App 必須用 UIApplicationDelegateAdaptor 才能呼叫傳統 AppDelegate 邏輯
final class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {

    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        
        // 1. 設定 UNUserNotificationCenter delegate（讓前景也能收到推播）
        UNUserNotificationCenter.current().delegate = self

        // 2. App 啟動時清除 App 圖示 badge 數字
        if #available(iOS 17.0, *) {
            UNUserNotificationCenter.current().setBadgeCount(0) { _ in }
        } else {
            application.applicationIconBadgeNumber = 0
        }

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
        // 🆕 前景收到時也清 badge（避免 badge 一直累積）
        if #available(iOS 17.0, *) {
            UNUserNotificationCenter.current().setBadgeCount(0) { _ in }
        } else {
            UIApplication.shared.applicationIconBadgeNumber = 0
        }
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
        // 🆕 點擊推播進入 App 時清除 badge（從鎖屏/通知中心點通知 → badge 應該立刻歸零）
        if #available(iOS 17.0, *) {
            UNUserNotificationCenter.current().setBadgeCount(0) { _ in }
        } else {
            UIApplication.shared.applicationIconBadgeNumber = 0
        }
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
