import SwiftUI

// MARK: - 主頁面視圖
struct HomeView: View {
    @EnvironmentObject private var store: HomeStore
    @State private var selectedMatchForDetail: Match? = nil
    @State private var showFIFAWorldCup: Bool = false
    @State private var scrollToTopTrigger = false
    
    var body: some View {
        NavigationStack {
            ScrollViewReader { proxy in
                ScrollView {
                    Group {
                        if store.isLoading && store.filteredPredictions.isEmpty {
                            HomeSkeletonView()
                                .padding(.vertical)
                        } else {
                            VStack(alignment: .leading, spacing: 22) {
                                Color.clear.frame(height: 1).id("scrollTop")
                                
                                if let error = store.errorMessage {
                                    HStack(spacing: 10) {
                                        Image(systemName: "wifi.slash")
                                            .foregroundColor(.red)
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text("伺服器連線異常")
                                                .font(.caption).bold().foregroundColor(.red)
                                            Text(error)
                                                .font(.caption2).foregroundColor(.white.opacity(0.6))
                                        }
                                        Spacer()
                                        Button(action: {
                                            store.errorMessage = nil
                                            Task { await store.importAllSportsData() }
                                        }) {
                                            Text("重試")
                                                .font(.caption).bold()
                                                .foregroundColor(.white)
                                                .padding(.horizontal, 12)
                                                .padding(.vertical, 6)
                                                .background(Color.red)
                                                .cornerRadius(8)
                                        }
                                    }
                                    .padding()
                                    .background(Color.red.opacity(0.12))
                                    .cornerRadius(12)
                                    .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.red.opacity(0.25), lineWidth: 1))
                                    .padding(.horizontal)
                                }
                                
                                SportsSectionHeader(title: "AI 重點觀察賽事", icon: "flame.fill")
                                    .padding(.top, 4)
                                ScrollView(.horizontal, showsIndicators: false) {
                                    HStack(spacing: 16) {
                                        if store.focusMatches.isEmpty {
                                            FocusFallbackCardView()
                                        } else {
                                            ForEach(store.focusMatches) { match in
                                                FocusMatchCardView(
                                                    homeTeam: match.homeTeam,
                                                    awayTeam: match.awayTeam,
                                                    homeTeamCN: match.homeTeamCN,
                                                    awayTeamCN: match.awayTeamCN,
                                                    league: match.league.rawValue,
                                                    startTime: match.startTime,
                                                    confidence: match.aiConfidence ?? 0
                                                )
                                                .contentShape(Rectangle())
                                                .onTapGesture { selectedMatchForDetail = match }
                                            }
                                        }
                                    }
                                    .padding(.horizontal)
                                }
                                
                                SportsSectionHeader(title: "聯賽預測中心", icon: "sportscourt.fill")
                                    .padding(.top, 4)
                                ScrollView(.horizontal, showsIndicators: false) {
                                    HStack(spacing: 12) {
                                        ForEach(LeagueType.activeCases) { league in
                                            leagueFilterButton(for: league)
                                        }
                                    }
                                    .padding(.horizontal)
                                }
                                
                                SportsSectionHeader(title: "\(store.selectedLeague.rawValue) AI 數據預報", icon: "cpu.fill")
                                    .padding(.top, 4)
                                VStack(spacing: 14) {
                                    if store.selectedLeague == .fifa {
                                        FocusMatchCardView(
                                            homeTeam: "世界盃🏆",
                                            awayTeam: "冠軍預測",
                                            homeTeamCN: "2026 FIFA",
                                            awayTeamCN: "AI 分析",
                                            league: "FIFA",
                                            startTime: Date(),
                                            confidence: 8.4
                                        )
                                        .contentShape(Rectangle())
                                        .onTapGesture { showFIFAWorldCup = true }
                                    }
                                    
                                    if store.filteredPredictions.isEmpty {
                                        ContentUnavailableView(
                                            "暫無今日賽事",
                                            systemImage: "sportscourt",
                                            description: Text("該聯賽今日開源網路端尚無實時排程")
                                        )
                                        .padding(.top, 20)
                                    } else {
                                        ForEach(store.filteredPredictions) { match in
                                            PredictionRowView(match: match)
                                                .contentShape(Rectangle())
                                                .onTapGesture { self.selectedMatchForDetail = match }
                                        }
                                    }
                                }
                                .padding(.horizontal)
                            }
                            .padding(.vertical)
                        }
                    }
                    .onChange(of: scrollToTopTrigger) { _, _ in
                        withAnimation(.smooth) {
                            proxy.scrollTo("scrollTop", anchor: .top)
                        }
                    }
                }
            }
            .background(SportsDarkBackground())
            .navigationTitle("PredictX Sports")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Image("AppLogo")
                        .resizable()
                        .scaledToFit()
                        .frame(width: 38, height: 38)
                        .clipShape(Circle())
                        .overlay(Circle().stroke(Color.blue.opacity(0.3), lineWidth: 1))
                        .shadow(color: Color.blue.opacity(0.3), radius: 6)
                        .scaleEffect(scrollToTopTrigger ? 1.1 : 1.0)
                        .animation(.spring(response: 0.3, dampingFraction: 0.5), value: scrollToTopTrigger)
                        .onTapGesture {
                            scrollToTopTrigger.toggle()
                        }
                }
            }
            .refreshable {
                await store.importAllSportsData()
            }
            .sheet(item: $selectedMatchForDetail) { match in
                AIAnalysisDetailView(match: match)
            }
            .sheet(isPresented: $showFIFAWorldCup) {
                FIFAWorldCupPredictionView()
            }
        }
    }
    
    @ViewBuilder
    private func leagueFilterButton(for league: LeagueType) -> some View {
        let isSelected = store.selectedLeague == league
        let themeColor = LeagueTheme.color(for: league)
        
        Text(league.rawValue)
            .font(.subheadline)
            .fontWeight(.bold)
            .padding(.horizontal, 22)
            .padding(.vertical, 12)
            .background(
                Group {
                    if isSelected {
                        LeagueTheme.gradient(for: league)
                    } else {
                        LeagueTheme.unselectedBg(for: league)
                    }
                }
            )
            .foregroundColor(isSelected ? .white : themeColor)
            .cornerRadius(24)
            .shadow(color: isSelected ? LeagueTheme.shadowColor(for: league) : Color.clear, radius: 8, x: 0, y: 4)
            .onTapGesture {
                withAnimation(.spring(response: 0.4, dampingFraction: 0.7)) {
                    store.selectedLeague = league
                }
            }
    }
}

// MARK: - 🛠️ 模組化 UI 子組件

struct SportsSectionHeader: View {
    var title: String
    var icon: String
    
    var body: some View {
        HStack(spacing: 10) {
            Rectangle()
                .fill(
                    LinearGradient(
                        colors: [Color.blue, Color.blue.opacity(0.3)],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )
                .frame(width: 4, height: 24)
                .cornerRadius(2)
            
            Image(systemName: icon)
                .foregroundColor(.blue)
                .font(.subheadline)
            Text(title)
                .font(.title3)
                .fontWeight(.heavy)
                .foregroundColor(.white)
            Spacer()
        }
        .padding(.horizontal)
    }
}

struct FocusMatchCardView: View {
    var homeTeam: String
    var awayTeam: String
    var homeTeamCN: String
    var awayTeamCN: String
    var league: String
    var startTime: Date
    var confidence: Double = 0
    
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(league)
                    .font(.caption)
                    .fontWeight(.bold)
                    .foregroundColor(.white.opacity(0.6))
                Spacer()
                HStack(spacing: 2) {
                    Image(systemName: "bolt.fill")
                        .font(.system(size: 8))
                        .foregroundColor(.yellow)
                    Text("\(Int(confidence))")
                        .font(.system(size: 11, design: .monospaced))
                        .bold()
                }
                .foregroundColor(.orange)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(Color.orange.opacity(0.15))
                .cornerRadius(6)
            }
            HStack {
                Text(homeTeam).bold()
                Text("vs").foregroundColor(.white.opacity(0.35)).font(.caption)
                Text(awayTeam).bold()
            }
            .font(.headline)
            .foregroundColor(.white)
            
            HStack(spacing: 4) {
                Image(systemName: "calendar")
                    .font(.caption2)
                Text(formattedDate)
                    .font(.caption2)
            }
            .foregroundColor(.white.opacity(0.5))
        }
        .padding()
        .frame(width: 240)
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(Color(red: 0.14, green: 0.16, blue: 0.26))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(Color.orange.opacity(0.4), lineWidth: 1.5)
                )
        )
        .shadow(color: Color.orange.opacity(0.2), radius: 10, x: 0, y: 4)
    }
    
    private var formattedDate: String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "zh_TW")
        formatter.dateFormat = "MM/dd"
        return formatter.string(from: startTime)
    }
}

struct FocusFallbackCardView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("AI 即時推薦").font(.caption).fontWeight(.bold).foregroundColor(.blue)
            Text("真實雲端數據已成功鏈結")
                .font(.subheadline).bold()
                .foregroundColor(.white.opacity(0.8))
            Text("下拉或切換分類即可刷新預報")
                .font(.caption2)
                .foregroundColor(.white.opacity(0.4))
        }
        .padding()
        .frame(width: 240)
        .background(Color(red: 0.14, green: 0.16, blue: 0.26))
        .cornerRadius(16)
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.blue.opacity(0.2), lineWidth: 1))
    }
}

// MARK: - Preview
#Preview {
    HomeView()
        .environmentObject(HomeStore())
}
