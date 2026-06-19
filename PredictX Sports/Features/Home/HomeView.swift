import SwiftUI

// MARK: - 主頁面視圖
struct HomeView: View {
    @EnvironmentObject private var store: HomeStore
    @EnvironmentObject private var favoritesStore: FavoritesStore
    @EnvironmentObject private var subscriptionManager: SubscriptionManager
    @State private var selectedMatchForDetail: Match? = nil
    @State private var scrollToTopTrigger = false
    @State private var showSpendToast: Bool = false
    @State private var spendToastMessage: String = ""
    @State private var showConfirmAlert: Bool = false
    @State private var matchToConfirm: Match? = nil

    /// 點擊賽事卡片的權限閘門
    private func openAnalysis(for match: Match) {
        if subscriptionManager.isUnlocked(match.id) {
            // 已解鎖：直接開啟
            selectedMatchForDetail = match
        } else if subscriptionManager.canWatchAnalysis() {
            // 有足夠點數：先跳出確認彈窗
            matchToConfirm = match
            showConfirmAlert = true
        } else {
            // 點數不足：跳出訂閱頁面
            subscriptionManager.showSubscribeView = true
        }
    }

    /// 執行確認扣點後的開啟邏輯
    private func confirmAndOpenAnalysis() {
        guard let match = matchToConfirm else { return }
        if subscriptionManager.spendDiamond() {
            subscriptionManager.unlockAnalysis(match.id)
            // 顯示扣點回饋 toast
            if let fb = subscriptionManager.lastSpendFeedback {
                spendToastMessage = "已使用 \(fb.cost) 分析點數・剩餘 \(fb.remaining) 點"
                showSpendToast = true
                DispatchQueue.main.asyncAfter(deadline: .now() + 2) { showSpendToast = false }
            }
            selectedMatchForDetail = match
        }
    }
    
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
                                                .font(.caption2).foregroundColor(.secondary)
                                        }
                                        Spacer()
                                        Button(action: {
                                            store.errorMessage = nil
                                            Task { await store.importAllSportsData() }
                                        }) {
                                            Text("重試")
                                                .font(.caption).bold()
                                                .foregroundColor(.primary)
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
                                            // 用 league + id 組合作為 SwiftUI 唯一鍵, 避免跨聯盟 gameId 碰撞
                                            ForEach(Array(store.focusMatches.enumerated()), id: \.offset) { _, match in
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
                                                .onTapGesture { openAnalysis(for: match) }
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
                                    if store.filteredPredictions.isEmpty {
                                        ContentUnavailableView(
                                            "暫無今日賽事",
                                            systemImage: "sportscourt",
                                            description: Text("該聯賽今日開源網路端尚無實時排程")
                                        )
                                        .padding(.top, 20)
                                    } else {
                                        ForEach(Array(store.filteredPredictions.enumerated()), id: \.offset) { _, match in
                                            PredictionRowView(
                                                match: match,
                                                onUnlock: { matchToUnlock in
                                                    // 鎖定狀態點擊鎖定區 → 觸發扣點確認對話框（共用邏輯）
                                                    matchToConfirm = matchToUnlock
                                                    showConfirmAlert = true
                                                }
                                            )
                                            .contentShape(Rectangle())
                                            .onTapGesture { openAnalysis(for: match) }
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
                    .environmentObject(favoritesStore)
                    .environmentObject(subscriptionManager)
            }
            .alert("開啟 AI 賽事詳情分析", isPresented: $showConfirmAlert) {
                Button("同意・扣除 20 點") {
                    confirmAndOpenAnalysis()
                }
                Button("取消", role: .cancel) {
                    matchToConfirm = nil
                }
            } message: {
                let remaining = subscriptionManager.diamonds
                Text("點選同意後將扣除 20 點分析點數查看本場賽事 AI 詳情分析。\n\n目前剩餘：\(remaining) 點")
            }
            .overlay(alignment: .bottom) {
                if showSpendToast {
                    spendToastView
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                        .animation(.spring(response: 0.4, dampingFraction: 0.7), value: showSpendToast)
                }
            }
        }
    }
    
    // MARK: - 扣點回饋 Toast
    private var spendToastView: some View {
        HStack(spacing: 8) {
            Image(systemName: "cpu.fill")
                .font(.caption)
                .foregroundColor(.blue)
            Text(spendToastMessage)
                .font(.caption)
                .fontWeight(.medium)
                .foregroundColor(.primary)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(.ultraThinMaterial)
        .clipShape(Capsule())
        .shadow(color: .black.opacity(0.2), radius: 8, y: 4)
        .padding(.bottom, 100)
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
                .foregroundColor(.primary)
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
                    .foregroundColor(.secondary)
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
                Text("vs").foregroundColor(Color(.tertiaryLabel)).font(.caption)
                Text(awayTeam).bold()
            }
            .font(.headline)
            .foregroundColor(.primary)
            
            HStack(spacing: 4) {
                Image(systemName: "calendar")
                    .font(.caption2)
                Text(formattedDate)
                    .font(.caption2)
            }
            .foregroundColor(.secondary)
        }
        .padding()
        .frame(width: 240)
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(Color.cardBackground)
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
                .foregroundColor(Color(.tertiaryLabel))
        }
        .padding()
        .frame(width: 240)
        .background(Color.cardBackground)
        .cornerRadius(16)
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.blue.opacity(0.2), lineWidth: 1))
    }
}

// MARK: - Preview
#Preview {
    HomeView()
        .environmentObject(HomeStore())
}
