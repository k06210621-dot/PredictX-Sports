import SwiftUI

struct HistoryView: View {
    @EnvironmentObject private var store: HomeStore
    @State private var selectedLeague: LeagueType = .mlb
    @State private var leagueFilter: LeagueFilter = .specific(.mlb)
    @State private var searchText: String = ""
    @State private var dateRange: DateRangeFilter = .last30

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                Spacer().frame(height: 4)

                HistoryFilterBar(
                    searchText: $searchText,
                    selectedLeague: $leagueFilter,
                    dateRange: $dateRange
                )

                let allMatches = store.historicalMatches[selectedLeague] ?? []
                let matches = filtered(allMatches)

                if allMatches.isEmpty {
                    ContentUnavailableView(
                        "載入歷史賽事中...",
                        systemImage: "clock.arrow.circlepath",
                        description: Text("\(selectedLeague.rawValue) 正在擷取資料")
                    )
                } else if matches.isEmpty {
                    ContentUnavailableView.search(text: searchText)
                } else {
                    ScrollView {
                        LazyVStack(spacing: 12) {
                            ForEach(matches) { match in
                                HistoricalMatchCardView(match: match)
                            }
                        }
                        .padding()
                    }
                }
            }
            .background(SportsDarkBackground())
            .navigationTitle("歷史賽事")
            .navigationBarTitleDisplayMode(.inline)
            .task {
                await store.loadHistoryForLeague(selectedLeague)
            }
            .onChange(of: selectedLeague) { oldValue, newValue in
                leagueFilter = .specific(newValue)
                Task {
                    await store.loadHistoryForLeague(newValue)
                }
            }
            .onChange(of: leagueFilter) { oldValue, newValue in
                if case .specific(let lg) = newValue, lg != selectedLeague {
                    selectedLeague = lg
                }
            }
            .refreshable {
                await store.loadHistoryForLeague(selectedLeague)
            }
        }
    }

    // MARK: - 篩選邏輯
    private func filtered(_ matches: [Match]) -> [Match] {
        // 1. 日期範圍
        var result = matches.sorted { $0.startTime > $1.startTime }
        if let days = dateRange.days {
            let cutoff = Date().addingTimeInterval(-Double(days) * 86400)
            result = result.filter { $0.startTime >= cutoff }
        }
        // 2. 搜尋（球隊英文 / 中文）
        let trimmed = searchText.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmed.isEmpty {
            let needle = trimmed.lowercased()
            result = result.filter { m in
                m.homeTeam.lowercased().contains(needle)
                    || m.awayTeam.lowercased().contains(needle)
                    || m.homeTeamCN.lowercased().contains(needle)
                    || m.awayTeamCN.lowercased().contains(needle)
            }
        }
        // 3. 聯賽
        if let lg = leagueFilter.unwrap(), lg != selectedLeague {
            // 載入其他聯盟的歷史，比對即可
            let otherMatches = store.historicalMatches[lg] ?? []
            var combined = result + otherMatches
            // 日期 + 搜尋再過濾一次（其他聯盟）
            if let days = dateRange.days {
                let cutoff = Date().addingTimeInterval(-Double(days) * 86400)
                combined = combined.filter { $0.startTime >= cutoff }
            }
            if !trimmed.isEmpty {
                let needle = trimmed.lowercased()
                combined = combined.filter { m in
                    m.homeTeam.lowercased().contains(needle)
                        || m.awayTeam.lowercased().contains(needle)
                        || m.homeTeamCN.lowercased().contains(needle)
                        || m.awayTeamCN.lowercased().contains(needle)
                }
            }
            return combined.sorted { $0.startTime > $1.startTime }
        }
        return result
    }
}

struct HistoricalMatchCardView: View {
    let match: Match

    private var themeColor: Color { LeagueTheme.color(for: match.league) }

    private var formattedDate: String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "zh_TW")
        // 使用本地時區顯示日期，確保台灣用戶看到的日期與賽事實際日期一致
        formatter.timeZone = .current
        formatter.dateFormat = "MM/dd (EEE)"
        return formatter.string(from: match.startTime)
    }

    private var leagueLabel: String {
        switch match.league {
        case .nba: return "NBA 籃球"
        case .mlb: return "MLB 棒球"
        case .npb: return "NPB 日職"
        case .cpbl: return "CPBL 中職"
        }
    }

    /// 根據賽事狀態與比分資料，產生誠實的狀態描述（不顯示 AI 推演為最終比分）
    private var statusDescription: String {
        // 若 status 為 scheduled → 尚未開打
        if match.status == .scheduled {
            return "尚未開打"
        }
        // status 為 live/postponed/cancelled → 對應狀態
        switch match.status {
        case .live: return "進行中"
        case .postponed: return "延期"
        case .cancelled: return "取消"
        default: break
        }
        // status 為 completed 但無比分資料 → 資料待補（cron 明日會補抓）
        return "比分未紀錄"
    }
    
    var body: some View {
        VStack(spacing: 8) {
            HStack {
                Image(systemName: "calendar")
                    .font(.caption2)
                    .foregroundColor(themeColor)
                Text(formattedDate)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .fontWeight(.medium)
                Spacer()
                Text(leagueLabel)
                    .font(.caption2)
                    .fontWeight(.bold)
                    .foregroundColor(themeColor)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(themeColor.opacity(0.15))
                    .cornerRadius(16)
            }
            
            // 🆕 [2026-06-24] 完全還原為備份版（2026-06-19 v1.0.0_最終完整版）
            // - 隊伍名稱不額外加 lineLimit（備份版沒有）
            // - 比分區保留 lineLimit + minimumScaleFactor + frame(minWidth: 40)
            HStack(spacing: 16) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(match.homeTeam)
                        .font(.headline)
                        .bold()
                        .foregroundColor(.primary)
                    Text(match.homeTeamCN)
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }

                Spacer()

                VStack(spacing: 4) {
                    // ✅ 永遠只顯示「真實比分」（homeScore + awayScore 兩者皆有才顯示）
                    // 不再用 aiTotalScorePredict 作為「最終比分」替代，避免誤導
                    if let homeScore = match.homeScore, let awayScore = match.awayScore {
                        // 用 lineLimit(1) + minimumScaleFactor 避免大數字被擠壓變形
                        Text("\(homeScore) - \(awayScore)")
                            .font(.title2)
                            .fontWeight(.heavy)
                            .foregroundColor(themeColor)
                            .lineLimit(1)
                            .minimumScaleFactor(0.6)
                            .frame(minWidth: 40)  // 防止 layout 擠壓
                        Text("最終比分")
                            .font(.system(size: 9))
                            .foregroundColor(Color(.tertiaryLabel))
                    } else {
                        // 沒有真實比分 → 誠實顯示資料狀態
                        Text("VS")
                            .font(.title3)
                            .fontWeight(.heavy)
                            .foregroundColor(themeColor.opacity(0.4))
                        Text(statusDescription)
                            .font(.system(size: 9))
                            .foregroundColor(Color(.tertiaryLabel))
                    }
                }

                Spacer()

                VStack(alignment: .trailing, spacing: 4) {
                    Text(match.awayTeam)
                        .font(.headline)
                        .bold()
                        .foregroundColor(.primary)
                    Text(match.awayTeamCN)
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
            }
            
            // 🆕 顯示 AI 驗證狀態：
            // - isHit 為 true → 綠色「AI 分析準確」
            // - isHit 為 false → 紅色「AI 分析未中」
            // - score 已有但 isHit 仍為 nil → 灰色「等待 AI 結算」
            // - 無 score → 不顯示（歷史比分未紀錄時誠實呈現）
            if match.homeScore != nil && match.awayScore != nil {
                HStack {
                    Spacer()
                    if let isHit = match.aiIsHit {
                        HStack(spacing: 4) {
                            Image(systemName: isHit ? "checkmark.circle.fill" : "xmark.circle.fill")
                                .font(.system(size: 14))
                                .foregroundColor(isHit ? .green : .red)
                            Text(isHit ? "AI 分析準確" : "AI 分析未中")
                                .font(.caption)
                                .fontWeight(.semibold)
                                .foregroundColor(isHit ? .green : .red)
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 4)
                        .background((isHit ? Color.green : Color.red).opacity(0.12))
                        .cornerRadius(16)
                    } else {
                        // 比分已有但 settlement 尚未跑（cron 還沒結算）
                        HStack(spacing: 4) {
                            Image(systemName: "hourglass")
                                .font(.system(size: 14))
                                .foregroundColor(Color(.tertiaryLabel))
                            Text("等待 AI 結算")
                                .font(.caption)
                                .fontWeight(.semibold)
                                .foregroundColor(Color(.tertiaryLabel))
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 4)
                        .background(Color(.tertiarySystemFill).opacity(0.5))
                        .cornerRadius(16)
                    }
                }
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(Color.cardBackground)
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(themeColor.opacity(0.3), lineWidth: 1.5)
                )
        )
        .shadow(color: themeColor.opacity(0.2), radius: 8, x: 0, y: 3)
        .padding(.horizontal, 4)
    }
}
