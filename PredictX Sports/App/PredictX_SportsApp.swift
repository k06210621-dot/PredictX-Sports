import SwiftUI
import Combine
import AppTrackingTransparency

@main
struct PredictX_SportsApp: App {
    // 🆕 [2026-06-23] 註冊 AppDelegate 以初始化 Google Mobile Ads SDK
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    @StateObject private var homeStore = HomeStore()
    @StateObject private var favoritesStore = FavoritesStore()
    @StateObject private var subscriptionManager = SubscriptionManager()
    @StateObject private var themeManager = ThemeManager()

    @State private var showLaunchScreen: Bool = true
    @State private var showATTConsent: Bool = false

    var body: some Scene {
        WindowGroup {
            ZStack {
                if showLaunchScreen {
                    LaunchView {
                        // 起始動畫結束 → 先關閉 LaunchView，下一個 run loop 再判斷 ATT
                        showLaunchScreen = false
                        DispatchQueue.main.async {
                            checkAndShowATT()
                        }
                    }
                } else if showATTConsent {
                    ATTConsentView {
                        // 使用者完成 ATT 同意（同意或略過）後進入主畫面
                        showATTConsent = false
                    }
                } else {
                    MainTabView()
                        .environmentObject(homeStore)
                        .environmentObject(favoritesStore)
                        .environmentObject(subscriptionManager)
                        .environmentObject(themeManager)
                        .transition(.opacity)
                }
            }
            .preferredColorScheme(themeManager.isDarkMode ? .dark : .light)
        }
    }

    /// 檢查 ATT 狀態，只有未決定時才顯示同意卡片
    private func checkAndShowATT() {
        if #available(iOS 14, *) {
            let status = ATTrackingManager.trackingAuthorizationStatus
            print("🔍 [ATT] checkAndShowATT: status=\(status.rawValue)")
            if status == .notDetermined {
                print("🔍 [ATT] notDetermined → 顯示 ATTConsentView")
                showATTConsent = true
            } else {
                print("🔍 [ATT] 已決定 (status=\(status.rawValue)) → 跳過 ATTConsentView")
            }
        }
    }
}
