import SwiftUI
import Combine

/// 大升級：發光質感 AI 數據預測卡片 (完美融合跨聯賽進階因子)
struct PredictionRowView: View {
    var match: Match
    @EnvironmentObject var favoritesStore: FavoritesStore
    
    // 根據不同聯賽自動更換發光主題色 (NBA 溫暖橘、MLB 科技藍、NPB 日職金、CPBL 職棒綠、FIFA 皇家紫)
    private var themeColor: Color { LeagueTheme.color(for: match.league) }
    
    // 格式化日期（只顯示日期，因為 API 只提供日期無實際時間）
    private var formattedDate: String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "zh_TW")
        formatter.dateFormat = "MM/dd"
        return formatter.string(from: match.startTime)
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            
            // 1. 卡片頂部：球種徽章、日期時間與 AI 信心指數勳章
            HStack {
                Label {
                    Text(match.league.rawValue)
                        .font(.caption)
                        .fontWeight(.bold)
                        .foregroundColor(.white)
                } icon: {
                    Image(systemName: match.league == .nba ? "basketball.fill" : (match.league == .fifa ? "figure.soccer" : "baseball.fill"))
                        .foregroundColor(themeColor)
                        .font(.caption)
                }
                .padding(.horizontal, 10)
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
                .cornerRadius(8)
                
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
                .cornerRadius(8)
                
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
                    Text(match.homeTeam).font(.headline).bold().foregroundColor(.white)
                    Text(match.homeTeamCN).font(.caption2).foregroundColor(.white.opacity(0.5))
                }
                
                Spacer()
                
                Text("VS")
                    .font(.title2)
                    .fontWeight(.black)
                    .foregroundColor(.white.opacity(0.25))
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 2) {
                    Text(match.awayTeam).font(.headline).bold().foregroundColor(.white)
                    Text(match.awayTeamCN).font(.caption2).foregroundColor(.white.opacity(0.5))
                }
            }
            .padding(.vertical, 2)
            
            // 3. 安全調用 Components 下的獨立 WinRateBar 雙向勝率條
            if let winRate = match.aiWinRateHome {
                WinRateBar(homeWinRate: winRate, homeTeam: match.homeTeamCN, awayTeam: match.awayTeamCN)
                    .padding(.vertical, 2)
            }
            
            // 4. 五大聯賽究極核心解包樞紐
            if match.league == .mlb, let mlb = match.mlbFeatures {
                expandMLBPanel(mlb)
            } else if match.league == .nba, let nba = match.nbaFeatures {
                expandNBAPanel(nba)
            } else if match.league == .cpbl, let cpbl = match.cpblFeatures {
                expandCPBLPanel(cpbl)
            } else if match.league == .fifa, let fifa = match.fifaFeatures {
                expandFIFAPanel(fifa)
            } else if match.league == .npb, let npb = match.npbFeatures {
                expandNPBPanel(npb)
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 20)
                .fill(Color(red: 0.14, green: 0.16, blue: 0.26))
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
            Text("MLB 關鍵預測因子已匯入").font(.system(size: 10, weight: .bold)).foregroundColor(.blue)
            HStack(spacing: 20) {
                VStack(alignment: .leading) {
                    Text("主投 FIP: \(String(format: "%.2f", mlb.homeStarterFIP ?? 0.0))")
                    Text("主隊戰力 wOBA: \(String(format: "%.3f", mlb.homeTeamwOBA ?? 0.0))")
                }
                VStack(alignment: .leading) {
                    Text("客投 FIP: \(String(format: "%.2f", mlb.awayStarterFIP ?? 0.0))")
                    Text("球場環境: \(mlb.windDirection ?? "未知")")
                }
            }
            .font(.system(size: 11)).foregroundColor(.white.opacity(0.55))
        }
    }
    
    // MARK: - 🏀 NBA 數據面板
    @ViewBuilder
    private func expandNBAPanel(_ nba: NBASpecificTags) -> some View {
        Divider().background(Color.orange.opacity(0.2))
        VStack(alignment: .leading, spacing: 6) {
            Text("NBA 四大效率因子已匯入").font(.system(size: 10, weight: .bold)).foregroundColor(.orange)
            Grid(alignment: .leading, horizontalSpacing: 15, verticalSpacing: 4) {
                GridRow {
                    Text("主隊 eFG%: \(String(format: "%.1f%%", (nba.homeEFG ?? 0.0) * 100))")
                    Text("客隊 eFG%: \(String(format: "%.1f%%", (nba.awayEFG ?? 0.0) * 100))")
                }
                GridRow {
                    Text("主隊 TOV%: \(String(format: "%.1f%%", nba.homeTOV ?? 0.0))")
                    Text("預估比賽 Pace: \(String(format: "%.1f", nba.pace ?? 0.0))")
                }
            }
            .font(.system(size: 11)).foregroundColor(.white.opacity(0.55))
        }
    }

    // MARK: - 🇹🇼 CPBL 數據面板
    @ViewBuilder
    private func expandCPBLPanel(_ cpbl: CPBLSpecificTags) -> some View {
        Divider().background(Color.green.opacity(0.2))
        VStack(alignment: .leading, spacing: 6) {
            Label("CPBL 本土戰力與彈性因子已匯入", systemImage: "shield.fill")
                .font(.system(size: 10, weight: .bold))
                .foregroundColor(.green)
            
            Grid(alignment: .leading, horizontalSpacing: 15, verticalSpacing: 4) {
                GridRow {
                    Text("本土先發 FIP: \(String(format: "%.2f", cpbl.localPitcherFIP ?? 0.0))")
                    Text("洋投先發 FIP: \(String(format: "%.2f", cpbl.foreignPitcherFIP ?? 0.0))")
                }
                GridRow {
                    Text("牛棚後援 WHIP: \(String(format: "%.2f", cpbl.bullpenWHIP ?? 0.0))")
                    Text("預估 HR 產出率: \(String(format: "%.2f", cpbl.homeRunDerbyRate ?? 0.0))")
                }
            }
            .font(.system(size: 11)).foregroundColor(.white.opacity(0.55))
        }
    }

    // MARK: - ⚽ FIFA 世界盃數據面板
    @ViewBuilder
    private func expandFIFAPanel(_ fifa: FIFASpecificTags) -> some View {
        Divider().background(Color.purple.opacity(0.2))
        VStack(alignment: .leading, spacing: 6) {
            Label("FIFA 預期進球與國家隊戰術指標已匯入", systemImage: "trophy.fill").font(.system(size: 10, weight: .bold)).foregroundColor(.purple)
            Grid(alignment: .leading, horizontalSpacing: 15, verticalSpacing: 4) {
                GridRow {
                    Text("主隊預期進球 (xG): \(String(format: "%.2f", fifa.homeExpectedGoals ?? 0.0))")
                    Text("客隊預期進球 (xG): \(String(format: "%.2f", fifa.awayExpectedGoals ?? 0.0))")
                }
                GridRow {
                    Text("國家隊磨合默契: \(String(format: "%.1f/10", fifa.nationalChemistry ?? 0.0))")
                    Text("戰術體系適應度: \(String(format: "%.0f%%", (fifa.tacticalSystemAdaptation ?? 0.0) * 100))")
                }
            }
            .font(.system(size: 11)).foregroundColor(.white.opacity(0.55))
        }
    }

    // MARK: - 🇯🇵 NPB 日本職棒進階數據面板
    @ViewBuilder
    private func expandNPBPanel(_ npb: NPBSpecificTags) -> some View {
        Divider().background(Color(red: 0.85, green: 0.65, blue: 0.13).opacity(0.2))
        VStack(alignment: .leading, spacing: 6) {
            Label("NPB 細膩特徵工程與王牌壓制指標已匯入", systemImage: "star.circle.fill")
                .font(.system(size: 10, weight: .bold))
                .foregroundColor(Color(red: 0.7, green: 0.55, blue: 0.1))
            
            Grid(alignment: .leading, horizontalSpacing: 15, verticalSpacing: 4) {
                GridRow {
                    Text("王牌 WHIP: \(String(format: "%.2f", npb.aceStarterWHIP ?? 0.0))")
                    Text("王牌 ERA: \(String(format: "%.2f", npb.aceStarterERA ?? 0.0))")
                }
                GridRow {
                    Text("團隊守備率: \(String(format: "%.3f", npb.teamFieldingPercentage ?? 0.0))")
                    Text("戰術推進率: \(String(format: "%.1f%%", (npb.sacrificeAndSmallBallRate ?? 0.0) * 100))")
                }
                GridRow {
                    Text("球場打擊修正: \(String(format: "%.2f", npb.npbParkFactor ?? 0.0))")
                    Text("遠征疲勞指數: \(String(format: "%.2f", npb.travelFatigueIndex ?? 0.0))")
                }
            }
            .font(.system(size: 11))
            .foregroundColor(.white.opacity(0.55))
        }
    }
}