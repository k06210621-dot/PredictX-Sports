import SwiftUI
import Charts

struct AnalyticsView: View {
    @StateObject private var store = AnalyticsStore()
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                if let error = store.errorMessage {
                    HStack {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundColor(.orange)
                        Text(error)
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Spacer()
                        Button(action: {
                            store.errorMessage = nil
                            Task { await store.loadRealAnalyticsData() }
                        }) {
                            Text("重試")
                                .font(.caption).bold()
                                .padding(.horizontal, 10)
                                .padding(.vertical, 4)
                                .background(Color.orange.opacity(0.2))
                                .cornerRadius(6)
                        }
                    }
                    .padding()
                    .background(Color.orange.opacity(0.08))
                    .cornerRadius(10)
                }

                ScrollView(.vertical, showsIndicators: false) {
                    if store.isLoading && store.leagueAccuracies.isEmpty {
                        AnalyticsSkeletonView()
                    } else {
                        VStack(alignment: .leading, spacing: 25) {
                            OverallAccuracyCard(accuracy: store.overallAccuracy)
                            RecentFormSection(settlements: store.recentSettlements, hitRate: store.recentFormRate)
                            LeagueSelectionSection(store: store)
                            TrendChartSection(selectedLeague: store.selectedLeague, trends: store.winRateTrends)
                        }
                        .padding()
                    }
                }
            }
            .background(SportsDarkBackground())
            .navigationTitle("AI 模型驗證中心")
        }
    }
}

// MARK: - Subviews

struct OverallAccuracyCard: View {
    let accuracy: Double

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Label("PredictX AI 模型綜合驗證率", systemImage: "bolt.shield.fill")
                    .font(.caption)
                    .fontWeight(.bold)
                    .foregroundColor(.blue)
                Spacer()
                Text("全體聯賽加權計算")
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }

            HStack(alignment: .bottom) {
                Text(String(format: "%.1f%%", accuracy * 100))
                    .font(.system(size: 42, weight: .black, design: .rounded))
                    .foregroundColor(.primary)
                Text("平均驗證率")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .padding(.bottom, 6)
            }
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.cardBackground)
        .cornerRadius(16)
        .shadow(color: Color.blue.opacity(0.15), radius: 8, x: 0, y: 4)
    }
}

// MARK: - 🆕 最近 10 場戰績卡片
struct RecentFormSection: View {
    let settlements: [RecentSettlement]
    let hitRate: Double

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // 標題列
            HStack {
                Label("AI 模型 10 場驗證紀錄", systemImage: "list.number")
                    .font(.headline)
                    .bold()
                    .foregroundColor(.primary)
                Spacer()
                if !settlements.isEmpty {
                    HStack(spacing: 4) {
                        Text(String(format: "%.0f%%", hitRate * 100))
                            .font(.system(.subheadline, design: .rounded))
                            .bold()
                            .foregroundColor(hitRate >= 0.5 ? .green : .orange)
                        Text("對")
                            .font(.caption2)
                            .foregroundColor(Color(.tertiaryLabel))
                    }
                }
            }

            if settlements.isEmpty {
                // 載入中 / 無資料
                HStack(spacing: 8) {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .blue))
                        .scaleEffect(0.8)
                    Text("正在從已結算賽事載入戰績...")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .frame(maxWidth: .infinity, alignment: .center)
                .padding(.vertical, 12)
            } else {
                // W/L 圓形方塊（從左到右 = 從最新到最舊）
                // 🆕 用 offset 當 key 避免資料庫重複 game_id 導致 ID 衝突
                HStack(spacing: 6) {
                    ForEach(Array(settlements.enumerated()), id: \.offset) { index, item in
                        FormIndicator(item: item, index: index)
                    }
                }
                .padding(.vertical, 4)

                // 最近 3 場明細
                // 🆕 同上，用 offset 避免重複 ID 警告
                VStack(spacing: 8) {
                    ForEach(Array(settlements.prefix(3).enumerated()), id: \.offset) { _, item in
                        FormDetailRow(item: item)
                    }
                }
                .padding(.top, 4)

                // 提示
                HStack(spacing: 4) {
                    Image(systemName: "info.circle")
                        .font(.system(size: 10))
                    Text("綠 = AI 模型推論正確・紅 = 推論錯誤・含四大聯盟近 30 天已結算場次")
                        .font(.system(size: 10))
                }
                .foregroundColor(Color(.tertiaryLabel))
                .padding(.top, 2)
            }
        }
        .padding()
        .background(Color.cardBackground)
        .cornerRadius(16)
        .shadow(color: Color.black.opacity(0.2), radius: 8, x: 0, y: 4)
    }
}

/// 單格 W/L 圓角方塊
struct FormIndicator: View {
    let item: RecentSettlement
    let index: Int

    var body: some View {
        VStack(spacing: 3) {
            ZStack {
                RoundedRectangle(cornerRadius: 8)
                    .fill(item.isHit
                          ? LinearGradient(colors: [Color.green, Color.green.opacity(0.7)],
                                           startPoint: .topLeading, endPoint: .bottomTrailing)
                          : LinearGradient(colors: [Color.red, Color.red.opacity(0.7)],
                                           startPoint: .topLeading, endPoint: .bottomTrailing))
                    .shadow(color: (item.isHit ? Color.green : Color.red).opacity(0.4), radius: 4, x: 0, y: 2)

                Text(item.isHit ? "O" : "X")
                    .font(.system(size: 15, weight: .black, design: .rounded))
                    .foregroundColor(.primary)
            }
            .frame(width: 28, height: 28)

            Text(shortLeague(item.league))
                .font(.system(size: 8, weight: .bold))
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
    }

    private func shortLeague(_ league: String) -> String {
        switch league {
        case "MLB":  return "⚾"
        case "NBA":  return "🏀"
        case "NPB":  return "🇯🇵"
        case "CPBL": return "🇹🇼"
        default:     return ""
        }
    }
}

/// 紀錄明細單列
struct FormDetailRow: View {
    let item: RecentSettlement

    var body: some View {
        HStack(spacing: 10) {
            // 驗證/未驗證 icon
            Image(systemName: item.isHit ? "checkmark.circle.fill" : "xmark.circle.fill")
                .foregroundColor(item.isHit ? .green : .red)
                .font(.system(size: 14))

            // 球隊對戰
            VStack(alignment: .leading, spacing: 1) {
                Text("\(item.homeTeam) vs \(item.awayTeam)")
                    .font(.caption)
                    .fontWeight(.medium)
                    .foregroundColor(.primary)
                    .lineLimit(1)
                Text("\(item.league) · \(formattedDate)")
                    .font(.system(size: 10))
                    .foregroundColor(Color(.tertiaryLabel))
            }

            Spacer()

            // 比分 + 預測
            VStack(alignment: .trailing, spacing: 1) {
                if let h = item.homeScore, let a = item.awayScore {
                    Text("\(h)-\(a)")
                        .font(.system(size: 14, weight: .heavy, design: .rounded))
                        .foregroundColor(.primary)
                }
                if let predict = item.predictedScore, !predict.isEmpty {
                    Text("推 \(predict)")
                        .font(.system(size: 9))
                        .foregroundColor(Color(.tertiaryLabel))
                }
            }
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 6)
        .background(Color.cardBackground)
        .cornerRadius(8)
    }

    private var formattedDate: String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "zh_TW")
        formatter.dateFormat = "MM/dd"
        return formatter.string(from: item.matchDate)
    }
}

struct LeagueSelectionSection: View {
    @ObservedObject var store: AnalyticsStore
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("點選聯賽查看模型趨勢分析", systemImage: "list.bullet.indent")
                .font(.headline)
                .bold()
                .foregroundColor(.primary)
            
            VStack(spacing: 10) {
                ForEach(store.leagueAccuracies) { accuracy in
                    LeagueCard(accuracy: accuracy, isSelected: store.selectedLeague == accuracy.league) {
                        Task {
                            await store.updateTrendForLeague(league: accuracy.league)
                        }
                    }
                }
            }
        }
        .padding()
        .background(Color.cardBackground)
        .cornerRadius(16)
    }
}

struct LeagueCard: View {
    let accuracy: LeagueAccuracy
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(accuracy.league)
                        .font(.headline)
                        .foregroundColor(.primary)
                    Text("已分析 \(accuracy.totalAnalyzed) 場")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text(accuracy.settlementNote)
                        .font(.system(size: 10))
                        .foregroundColor(Color(.tertiaryLabel))
                        .padding(.top, 1)
                }
                Spacer()
                HStack {
                    Text(String(format: "%.1f%%", accuracy.hitRate * 100))
                        .font(.system(.body, design: .monospaced))
                        .bold()
                        .foregroundColor(isSelected ? .blue : .white.opacity(0.8))
                    Image(systemName: accuracy.hitRate > 0.5 ? "checkmark.circle.fill" : "xmark.circle.fill")
                        .foregroundColor(accuracy.hitRate > 0.5 ? .green : .red)
                }
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(isSelected ? Color.blue.opacity(0.15) : Color.cardBackground)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(isSelected ? Color.blue : Color.clear, lineWidth: 2)
            )
        }
        .buttonStyle(PlainButtonStyle())
    }
}

struct TrendChartSection: View {
    let selectedLeague: String
    let trends: [WinRateTrend]

    private let dateFormatter: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "zh_TW")
        f.dateFormat = "MM/dd"
        return f
    }()

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label("\(selectedLeague) 驗證率趨勢 (近 50 場)", systemImage: "chart.line.uptrend.xyaxis")
                    .font(.headline)
                    .bold()
                    .foregroundColor(.primary)
                Spacer()
                Text("日波動")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Chart {
                ForEach(trends) { trend in
                    LineMark(
                        x: .value("日期", trend.date),
                        y: .value("驗證率", trend.hitRate)
                    )
                    .foregroundStyle(Color.blue.gradient)
                    .interpolationMethod(.catmullRom)
                    .lineStyle(StrokeStyle(lineWidth: 3))

                    PointMark(
                        x: .value("日期", trend.date),
                        y: .value("驗證率", trend.hitRate)
                    )
                    .foregroundStyle(Color.blue)
                }
            }
            .frame(height: 220)
            .chartYScale(domain: 0.0 ... 1.0)
            .chartYAxis {
                AxisMarks(format: Decimal.FormatStyle.Percent.percent)
            }
            .chartXAxis {
                // 🆕 顯示日期標籤（MM/dd），用 desiredCount 控制標籤數量避免擠在一起
                AxisMarks(values: .automatic(desiredCount: 5)) { value in
                    if let date = value.as(Date.self) {
                        AxisValueLabel {
                            Text(dateFormatter.string(from: date))
                                .font(.caption2)
                        }
                    }
                    AxisGridLine()
                }
            }
        }
        .padding()
        .background(Color.cardBackground)
        .cornerRadius(16)
    }
}
