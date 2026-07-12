import Foundation
import SwiftUI
import Combine
import UserNotifications

/// 推播通知管理器：包裝 APNs device token 註冊與偏好設定
/// 與後端 /api/register_device + /api/update_push_preference 對接
@MainActor
final class PushServiceManager: ObservableObject {

    static let shared = PushServiceManager()

    @Published var deviceToken: String? = nil
    @Published var isPushEnabled: Bool = false  // 本地快取（使用者最後一次選擇）
    @Published var authorizationStatus: UNAuthorizationStatus = .notDetermined

    private let tokenKey = "apns_device_token"
    private let pushEnabledKey = "push_enabled_local"
    private let lastTierKey = "push_last_tier"

    private init() {
        self.deviceToken = UserDefaults.standard.string(forKey: tokenKey)
        self.isPushEnabled = UserDefaults.standard.bool(forKey: pushEnabledKey)
    }

    // MARK: - 註冊流程

    /// 由 AppDelegate 在拿到 APNs token 後呼叫
    func registerDeviceToken(_ token: String) async {
        self.deviceToken = token
        UserDefaults.standard.set(token, forKey: tokenKey)

        // 詢問使用者授權（第一次會彈 dialog）
        let granted = await requestAuthorization()
        self.authorizationStatus = granted ? .authorized : .denied

        #if DEBUG
        print("📱 [PushManager] token 已儲存，授權狀態: \(granted)")
        #endif

        // 送到後端（包含當前 tier 與推播開關）
        await syncWithBackend(tier: getCurrentTier(), pushEnabled: granted)
    }

    /// 請求推播授權
    private func requestAuthorization() async -> Bool {
        let center = UNUserNotificationCenter.current()
        do {
            let granted = try await center.requestAuthorization(options: [.alert, .sound, .badge])
            // 更新本地偏好
            self.isPushEnabled = granted
            UserDefaults.standard.set(granted, forKey: pushEnabledKey)
            return granted
        } catch {
            #if DEBUG
            print("❌ [PushManager] 授權請求失敗: \(error)")
            #endif
            return false
        }
    }

    // MARK: - 使用者切換開關

    /// 使用者在 ProfileView 切換推播開關時呼叫
    /// 🆕 [2026-06-29] 修正：使用者從 ProfileView 主動開啟推播時才觸發系統通知請求
    ///                避免啟動時連續彈出 ATT + 通知請求兩個彈窗
    func setPushEnabled(_ enabled: Bool) async {
        self.isPushEnabled = enabled
        UserDefaults.standard.set(enabled, forKey: pushEnabledKey)

        // 如果是從關→開，需要重新請求授權（若之前拒絕則無法再開啟）
        if enabled {
            // 🆕 先註冊 APNs（取得 device token）
            UIApplication.shared.registerForRemoteNotifications()

            // 再請求通知權限
            let granted = await requestAuthorization()
            if !granted {
                #if DEBUG
                print("⚠️ [PushManager] 使用者在系統設定關閉推播，需要引導至 Settings")
                #endif
                // 仍同步後端為 false（事實上無法推送）
                await syncWithBackend(tier: getCurrentTier(), pushEnabled: false)
                return
            }
        }

        await syncWithBackend(tier: getCurrentTier(), pushEnabled: enabled)
    }

    /// 訂閱狀態改變時通知後端（Premium 才發送推播）
    func onSubscriptionChanged(tier: String) async {
        UserDefaults.standard.set(tier, forKey: lastTierKey)
        await syncWithBackend(tier: tier, pushEnabled: isPushEnabled)
    }

    // MARK: - 後端同步

    private func getCurrentTier() -> String {
        // 從 SubscriptionManager 拿當前 tier
        // 為了避免循環 import，這裡用 UserDefaults 或簡單回傳字串
        if let tierStr = UserDefaults.standard.string(forKey: "membership_tier") {
            return tierStr.lowercased()
        }
        return "free"
    }

    private func syncWithBackend(tier: String, pushEnabled: Bool) async {
        guard let token = deviceToken else {
            #if DEBUG
            print("⚠️ [PushManager] 無 device token，跳過後端同步")
            #endif
            return
        }

        do {
            try await APIService.shared.registerDevice(
                token: token,
                tier: tier,
                pushEnabled: pushEnabled
            )
            #if DEBUG
            print("✅ [PushManager] 後端同步成功: tier=\(tier), push=\(pushEnabled)")
            #endif
        } catch {
            #if DEBUG
            print("❌ [PushManager] 後端同步失敗: \(error)")
            #endif
        }
    }
}

// 因為 SwiftUI EnvironmentObject 需要這裡 import UNUserNotificationCenter
// import UserNotifications  // 已移至檔案頂部
