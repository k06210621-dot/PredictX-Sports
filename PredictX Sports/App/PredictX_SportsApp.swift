import SwiftUI
import Combine

@main
struct PredictX_SportsApp: App {
    @StateObject private var homeStore = HomeStore()
    @StateObject private var favoritesStore = FavoritesStore()
    @StateObject private var subscriptionManager = SubscriptionManager()
    
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
                        .transition(.opacity)
                }
            }
            .preferredColorScheme(.dark)
        }
    }
}
