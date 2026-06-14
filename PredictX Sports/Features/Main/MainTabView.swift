import SwiftUI

struct MainTabView: View {
    @State private var selectedTab: Int = 0
    
    var body: some View {
        TabView(selection: $selectedTab) {
            
            // ① 智能分析
            HomeView()
                .tabItem {
                    Label("智能分析", systemImage: "cpu.fill")
                }
                .tag(0)
            
            // ② 分析結果
            AnalyticsView()
                .tabItem {
                    Label("分析結果", systemImage: "chart.bar.doc.horizontal.fill")
                }
                .tag(1)
            
            // ③ 歷史賽事
            HistoryView()
                .tabItem {
                    Label("歷史賽事", systemImage: "clock.arrow.circlepath")
                }
                .tag(2)
            
            // ④ 個人資訊
            ProfileView()
                .tabItem {
                    Label("個人資訊", systemImage: "person.crop.circle.fill")
                }
                .tag(3)
        }
        .accentColor(.blue)
    }
}
