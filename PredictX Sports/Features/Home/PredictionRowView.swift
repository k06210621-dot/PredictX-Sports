import SwiftUI
import Combine

/// 大升級：發光質感 AI 數據預測卡片 (完美融合跨聯盟進階因子)
struct PredictionRowView: View {
    var match: Match
    @EnvironmentObject var favoritesStore: FavoritesStore
    @EnvironmentObject var subscriptionManager: SubscriptionManager
    /// 點擊解鎖按鈕的回呼（由 HomeView 處理扣點數 + 顯示確認對話框）
    var onUnlock: ((Match) -> Void)? = nil

    // 根據不同聯賽自動更換發光主題色 (NBA 溫暖橘、MLB 科技藍、NPB 日職金、CPBL 職棒綠)
    private var themeColor: Color { LeagueTheme.color(for: match.league) }

    // 格式化日期（只顯示日期，因為 API 只提供日期無實際時間）
    private var formattedDate: String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "zh_TW")
        formatter.dateFormat = "MM/dd"
        return formatter.string(from: match.startTime)
    }

    // 🆕 顯示數值或「—」（避免誤導用戶以為 0.00 是真實資料）
    private func displayValue(_ value: Double?, format: String = "%.2f", suffix: String = "") -> String {
        guard let v = value else { return "—" }
        return String(format: format, v) + suffix
    }
    private func displayPercent(_ value: Double?, multiplier: Double = 100) -> String {
        guard let v = value else { return "—" }
        return String(format: "%.1f%%", v * multiplier)
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            
            // 1. 卡片頂部：球種徽章、日期時間與 AI 信心指數勳章
            HStack {
                Label {
                    Text(match.league.rawValue)
                        .font(.caption)
                        .fontWeight(.bold)
                        .foregroundColor(.primary)
                } icon: {
                    Image(systemName: match.league == .nba ? "basketball.fill" : "baseball.fill")
                        .foregroundColor(themeColor)
                        .font(.caption)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 4)
                .background(themeColor.opacity(0.15))
                .clipShape(Capsule())
                
                Spacer()
                
                // 日期時間顯示
                HStack(spacing: 4) {
                    Image(systemName: "calendar")
                        .font(.caption2)
                    Text(formattedDate)
                        .font(.system(size: 11, weight: .medium, design: .rounded))
                }
                .foregroundColor(.secondary)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(Color.secondary.opacity(0.1))
                .cornerRadius(16)
                
                HStack(spacing: 3) {
                    Image(systemName: "cpu.fill")
                        .font(.caption2)
                    Text(String(format: "%.1f/10", match.aiConfidence ?? 0.0))
                        .font(.system(size: 12, weight: .bold, design: .rounded))
                }
                .foregroundColor(.blue)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(Color.blue.opacity(0.1))
                .cornerRadius(16)
                
                // 收藏星星按鈕
                Button(action: {
                    favoritesStore.toggle(match: match)
                }) {
                    Image(systemName: favoritesStore.isFavorited(gameId: match.id) ? "star.fill" : "star")
                        .font(.system(size: 16))
                        .foregroundColor(favoritesStore.isFavorited(gameId: match.id) ? .yellow : .gray.opacity(0.5))
                }
                .buttonStyle(.plain)
            }
            
            // 2. 卡片中部：主客球隊對決（VS 分隔）
            HStack(alignment: .center) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(match.homeTeam).font(.headline).bold().foregroundColor(.primary)
                    Text(match.homeTeamCN).font(.caption2).foregroundColor(.secondary)
                }
                
                Spacer()
                
                Text("VS")
                    .font(.title2)
                    .fontWeight(.black)
                    .foregroundColor(Color(.tertiaryLabel))
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 2) {
                    Text(match.awayTeam).font(.headline).bold().foregroundColor(.primary)
                    Text(match.awayTeamCN).font(.caption2).foregroundColor(.secondary)
                }
            }
            .padding(.vertical, 2)
            
            // 3. 安全調用 Components 下的獨立 WinRateBar 雙向勝率條
            // 邏輯：
            // - 付費會員 (Standard/Premium) 直接看 → isLocked = false
            // - 一般會員 (Free/Basic) 已解鎖 → isLocked = false
            // - 一般會員 (Free/Basic) 未解鎖 → isLocked = true（顯示灰底 + 解鎖提示）
            if let winRate = match.aiWinRateHome {
                let isLocked = UnlockManager.shared.requiresPayment(tier: subscriptionManager.tier)
                    && !UnlockManager.shared.isUnlocked(gameId: match.id)
                WinRateBar(
                    homeWinRate: winRate,
                    homeTeam: match.homeTeamCN,
                    awayTeam: match.awayTeamCN,
                    isLocked: isLocked,
                    onUnlockTapped: {
                        // 點擊鎖定區時，直接彈出扣點確認對話框（與卡片本身共用邏輯）
                        onUnlock?(match)
                    }
                )
                .padding(.vertical, 2)
            }
            
            // 4. 四大聯賽究極核心解包樞紐
            if match.league == .mlb, let mlb = match.mlbFeatures {
                expandMLBPanel(mlb)
            } else if match.league == .nba, let nba = match.nbaFeatures {
                expandNBAPanel(nba)
            } else if match.league == .cpbl, let cpbl = match.cpblFeatures {
                expandCPBLPanel(cpbl)
            } else if match.league == .npb, let npb = match.npbFeatures {
                expandNPBPanel(npb)
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 20)
                .fill(Color.cardBackground)
                .overlay(
                    RoundedRectangle(cornerRadius: 20)
                        .stroke(
                            LinearGradient(
                                colors: [themeColor.opacity(0.6), themeColor.opacity(0.2)],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            ),
                            lineWidth: 1.5
                        )
                )
        )
        .shadow(color: themeColor.opacity(0.25), radius: 12, x: 0, y: 4)
    }
    
    // MARK: - ⚾ MLB 數據面板
    @ViewBuilder
    private func expandMLBPanel(_ mlb: MLBSpecificTags) -> some View {
        Divider().background(Color.blue.opacity(0.15))
        VStack(alignment: .leading, spacing: 6) {
            Text("MLB 關鍵分析因子").font(.system(size: 10, weight: .bold)).foregroundColor(.blue)
            HStack(spacing: 20) {
                VStack(alignment: .leading) {
                    HStack(spacing: 4) {
                        Text("主投 FIP:").foregroundColor(.secondary)
                        Text(displayValue(mlb.homeStarterFIP, format: "%.2f"))
                            .foregroundColor(mlb.homeStarterFIP == nil ? Color(.tertiaryLabel) : .primary)
                    }
                    HStack(spacing: 4) {
                        Text("主隊 wOBA:").foregroundColor(.secondary)
                        Text(displayValue(mlb.homeTeamwOBA, format: "%.3f"))
                            .foregroundColor(mlb.homeTeamwOBA == nil ? Color(.tertiaryLabel) : .primary)
                    }
                }
                VStack(alignment: .leading) {
                    HStack(spacing: 4) {
                        Text("客投 FIP:").foregroundColor(.secondary)
                        Text(displayValue(mlb.awayStarterFIP, format: "%.2f"))
                            .foregroundColor(mlb.awayStarterFIP == nil ? Color(.tertiaryLabel) : .primary)
                    }
                    HStack(spacing: 4) {
                        Text("球場環境:").foregroundColor(.secondary)
                        Text(mlb.windDirection ?? "—")
                            .foregroundColor(mlb.windDirection == nil ? Color(.tertiaryLabel) : .primary)
                    }
                }
            }
            .font(.system(size: 11)).foregroundColor(.secondary)
        }
    }
    
    // MARK: - 🏀 NBA 數據面板
    @ViewBuilder
    private func expandNBAPanel(_ nba: NBASpecificTags) -> some View {
        Divider().background(Color.orange.opacity(0.2))
        VStack(alignment: .leading, spacing: 6) {
            Text("NBA 四大效率因子").font(.system(size: 10, weight: .bold)).foregroundColor(.orange)
            Grid(alignment: .leading, horizontalSpacing: 15, verticalSpacing: 4) {
                GridRow {
                    HStack(spacing: 4) {
                        Text("主隊 eFG%:").foregroundColor(.secondary)
                        Text(displayPercent(nba.homeEFG))
                            .foregroundColor(nba.homeEFG == nil ? Color(.tertiaryLabel) : .primary)
                    }
                    HStack(spacing: 4) {
                        Text("客隊 eFG%:").foregroundColor(.secondary)
                        Text(displayPercent(nba.awayEFG))
                            .foregroundColor(nba.awayEFG == nil ? Color(.tertiaryLabel) : .primary)
                    }
                }
                GridRow {
                    HStack(spacing: 4) {
                        Text("主隊 TOV%:").foregroundColor(.secondary)
                        Text(displayValue(nba.homeTOV, format: "%.1f%%"))
                            .foregroundColor(nba.homeTOV == nil ? Color(.tertiaryLabel) : .primary)
                    }
                    HStack(spacing: 4) {
                        Text("預估 Pace:").foregroundColor(.secondary)
                        Text(displayValue(nba.pace, format: "%.1f"))
                            .foregroundColor(nba.pace == nil ? Color(.tertiaryLabel) : .primary)
                    }
                }
            }
            .font(.system(size: 11)).foregroundColor(.secondary)
        }
    }

    // MARK: - 🇹🇼 CPBL 數據面板
    @ViewBuilder
    private func expandCPBLPanel(_ cpbl: CPBLSpecificTags) -> some View {
        Divider().background(Color.green.opacity(0.2))
        VStack(alignment: .leading, spacing: 6) {
            Label("CPBL 本土戰力與彈性因子", systemImage: "shield.fill")
                .font(.system(size: 10, weight: .bold))
                .foregroundColor(.green)

            Grid(alignment: .leading, horizontalSpacing: 15, verticalSpacing: 4) {
                GridRow {
                    HStack(spacing: 4) {
                        Text("本土 FIP:").foregroundColor(.secondary)
                        Text(displayValue(cpbl.localPitcherFIP, format: "%.2f"))
                            .foregroundColor(cpbl.localPitcherFIP == nil ? Color(.tertiaryLabel) : .primary)
                    }
                    HStack(spacing: 4) {
                        Text("洋投 FIP:").foregroundColor(.secondary)
                        Text(displayValue(cpbl.foreignPitcherFIP, format: "%.2f"))
                            .foregroundColor(cpbl.foreignPitcherFIP == nil ? Color(.tertiaryLabel) : .primary)
                    }
                }
                GridRow {
                    HStack(spacing: 4) {
                        Text("牛棚 WHIP:").foregroundColor(.secondary)
                        Text(displayValue(cpbl.bullpenWHIP, format: "%.2f"))
                            .foregroundColor(cpbl.bullpenWHIP == nil ? Color(.tertiaryLabel) : .primary)
                    }
                    HStack(spacing: 4) {
                        Text("HR 產出率:").foregroundColor(.secondary)
                        Text(displayValue(cpbl.homeRunDerbyRate, format: "%.2f"))
                            .foregroundColor(cpbl.homeRunDerbyRate == nil ? Color(.tertiaryLabel) : .primary)
                    }
                }
            }
            .font(.system(size: 11)).foregroundColor(.secondary)
        }
    }

    // MARK: - 🇯🇵 NPB 日本職棒進階數據面板
    @ViewBuilder
    private func expandNPBPanel(_ npb: NPBSpecificTags) -> some View {
        Divider().background(Color(red: 0.85, green: 0.65, blue: 0.13).opacity(0.2))
        VStack(alignment: .leading, spacing: 6) {
            Label("NPB 王牌壓制與戰術指標", systemImage: "star.circle.fill")
                .font(.system(size: 10, weight: .bold))
                .foregroundColor(Color(red: 0.7, green: 0.55, blue: 0.1))

            Grid(alignment: .leading, horizontalSpacing: 15, verticalSpacing: 4) {
                GridRow {
                    HStack(spacing: 4) {
                        Text("王牌 WHIP:").foregroundColor(.secondary)
                        Text(displayValue(npb.aceStarterWHIP, format: "%.2f"))
                            .foregroundColor(npb.aceStarterWHIP == nil ? Color(.tertiaryLabel) : .primary)
                    }
                    HStack(spacing: 4) {
                        Text("王牌 ERA:").foregroundColor(.secondary)
                        Text(displayValue(npb.aceStarterERA, format: "%.2f"))
                            .foregroundColor(npb.aceStarterERA == nil ? Color(.tertiaryLabel) : .primary)
                    }
                }
                GridRow {
                    HStack(spacing: 4) {
                        Text("團隊守備率:").foregroundColor(.secondary)
                        Text(displayValue(npb.teamFieldingPercentage, format: "%.3f"))
                            .foregroundColor(npb.teamFieldingPercentage == nil ? Color(.tertiaryLabel) : .primary)
                    }
                    HStack(spacing: 4) {
                        Text("戰術推進率:").foregroundColor(.secondary)
                        Text(displayPercent(npb.sacrificeAndSmallBallRate))
                            .foregroundColor(npb.sacrificeAndSmallBallRate == nil ? Color(.tertiaryLabel) : .primary)
                    }
                }
                GridRow {
                    HStack(spacing: 4) {
                        Text("球場修正:").foregroundColor(.secondary)
                        Text(displayValue(npb.npbParkFactor, format: "%.2f"))
                            .foregroundColor(npb.npbParkFactor == nil ? Color(.tertiaryLabel) : .primary)
                    }
                    HStack(spacing: 4) {
                        Text("遠征疲勞:").foregroundColor(.secondary)
                        Text(displayValue(npb.travelFatigueIndex, format: "%.2f"))
                            .foregroundColor(npb.travelFatigueIndex == nil ? Color(.tertiaryLabel) : .primary)
                    }
                }
            }
            .font(.system(size: 11))
            .foregroundColor(.secondary)
        }
    }
}