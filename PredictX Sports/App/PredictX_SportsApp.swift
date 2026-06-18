import SwiftUI
import Combine

@main
struct PredictX_SportsApp: App {
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
