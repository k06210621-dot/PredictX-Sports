import SwiftUI
import Combine

@main
struct PredictX_SportsApp: App {
    // 🆕 [2026-06-23] 註冊 AppDelegate 以初始化 Google Mobile Ads SDK
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    @StateObject private var homeStore = HomeStore()
    @StateObject private var favoritesStore = FavoritesStore()
    @StateObject private var subscriptionManager = SubscriptionManager()
    @StateObject private var themeManager = ThemeManager()
    
    @State private var showLaunchScreen: Bool = true
    
    var body: some Scene {
        WindowGroup {
            ZStack {
                if showLaunchScreen {
                    LaunchView {
                        showLaunchScreen = false
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
}
