//
//  SettlementDetailSheet.swift
//  PredictX Sports
//
//  從「AI 模型 10 場驗證紀錄」的 O/X 方塊點擊後，
//  開啟此 Sheet 顯示該場比賽的實際比分 + AI 分析卡片詳細資訊。
//
//  Created: 2026-06-20
//

import SwiftUI

struct SettlementDetailSheet: View {
    let settlement: RecentSettlement
    @Environment(\.dismiss) private var dismiss

    @State private var analysis: AIAnalysisModel? = nil
    @State private var isLoading = true
    @State private var errorMessage: String? = nil

    var body: some View {
        NavigationStack {
            ZStack {
                Color(UIColor.systemBackground).ignoresSafeArea()

                if isLoading {
                    ProgressView("載入 AI 分析中...")
                        .progressViewStyle(CircularProgressViewStyle(tint: .blue))
                } else if let error = errorMessage {
                    VStack(spacing: 16) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .font(.system(size: 48))
                            .foregroundColor(.orange)
                        Text(error)
                            .multilineTextAlignment(.center)
                            .foregroundColor(.secondary)
                            .padding(.horizontal, 32)
                        Button("重試") {
                            Task { await loadAnalysis() }
                        }
                        .buttonStyle(.borderedProminent)
                    }
                } else {
                    ScrollView {
                        VStack(spacing: 16) {
                            // 1. 賽事結果標題卡
                            headerCard

                            // 2. 實際比分 vs AI 預測比分
                            scoreComparisonCard

                            // 3. AI 預測摘要
                            if let summary = analysis?.analysis?.summary, !summary.isEmpty {
                                summaryCard(summary: summary)
                            }

                            // 4. AI 信心指數 + 機率
                            if let prediction = analysis?.prediction {
                                confidenceCard(prediction: prediction)
                            }

                            // 5. 關鍵因素
                            if let factors = analysis?.analysis?.key_factors, !factors.isEmpty {
                                keyFactorsCard(factors: factors)
                            }

                            // 6. 風險因素
                            if let risks = analysis?.analysis?.risk_factors, !risks.isEmpty {
                                riskFactorsCard(risks: risks)
                            }

                            // 7. 雷達圖
                            if let radar = analysis?.radar_chart,
                               let cats = radar.categories,
                               let h = radar.home_team,
                               let a = radar.away_team,
                               !cats.isEmpty {
                                RadarSection(categories: cats, home: h, away: a)
                            }
                        }
                        .padding()
                    }
                }
            }
            .navigationTitle("賽事驗證詳情")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("關閉") { dismiss() }
                }
            }
            .task {
                await loadAnalysis()
            }
        }
    }

    // MARK: - 載入 AI 分析
    private func loadAnalysis() async {
        isLoading = true
        errorMessage = nil
        do {
            let result = try await APIService.shared.fetchAIAnalysis(gameId: settlement.id)
            self.analysis = result
            self.isLoading = false
        } catch {
            self.errorMessage = "無法載入 AI 分析：\(error.localizedDescription)"
            self.isLoading = false
        }
    }

    // MARK: - 卡片元件

    private var headerCard: some View {
        VStack(spacing: 8) {
            HStack {
                Text(leagueIcon(settlement.league))
                    .font(.system(size: 28))
                VStack(alignment: .leading, spacing: 2) {
                    Text("\(settlement.awayTeam) @ \(settlement.homeTeam)")
                        .font(.headline)
                        .foregroundColor(.primary)
                    Text("\(settlement.league) · \(formattedDate)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                Spacer()
            }

            HStack(spacing: 8) {
                Image(systemName: settlement.isHit ? "checkmark.circle.fill" : "xmark.circle.fill")
                    .foregroundColor(settlement.isHit ? .green : .red)
                Text(settlement.isHit ? "AI 推論正確" : "AI 推論錯誤")
                    .font(.subheadline.bold())
                    .foregroundColor(settlement.isHit ? .green : .red)
            }
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(Color.cardBackground)
        .cornerRadius(16)
    }

    private var scoreComparisonCard: some View {
        VStack(spacing: 12) {
            Text("比分對照")
                .font(.subheadline.bold())
                .foregroundColor(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)

            HStack(spacing: 0) {
                scoreColumn(title: "模型推演比分", score: settlement.predictedScore ?? "—", tint: .blue)
                Divider().frame(height: 40)
                scoreColumn(title: "實際比分",
                            score: formatActualScore(),
                            tint: settlement.isHit ? .green : .red)
            }
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(Color.cardBackground)
        .cornerRadius(16)
    }

    private func scoreColumn(title: String, score: String, tint: Color) -> some View {
        VStack(spacing: 4) {
            Text(title)
                .font(.caption2)
                .foregroundColor(.secondary)
            Text(score)
                .font(.system(size: 28, weight: .heavy, design: .rounded))
                .foregroundColor(tint)
        }
        .frame(maxWidth: .infinity)
    }

    private func summaryCard(summary: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("AI 分析摘要", systemImage: "text.bubble.fill")
                .font(.subheadline.bold())
                .foregroundColor(.blue)
            Text(summary)
                .font(.callout)
                .foregroundColor(.primary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.cardBackground)
        .cornerRadius(16)
    }

    private func confidenceCard(prediction: AIAnalysisModel.Prediction) -> some View {
        VStack(spacing: 12) {
            Text("AI 推論機率與信心")
                .font(.subheadline.bold())
                .foregroundColor(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)

            // 機率條
            HStack(spacing: 0) {
                Text(settlement.homeTeam)
                    .font(.caption.bold())
                    .frame(maxWidth: .infinity, alignment: .leading)

                if let hp = prediction.home_win_probability {
                    Text("\(Int(hp * 100))%")
                        .font(.subheadline.bold())
                        .foregroundColor(.blue)
                }
                Text(" vs ").font(.caption2).foregroundColor(.secondary)

                if let ap = prediction.away_win_probability {
                    Text("\(Int(ap * 100))%")
                        .font(.subheadline.bold())
                        .foregroundColor(.red)
                }
                Text(settlement.awayTeam)
                    .font(.caption.bold())
                    .frame(maxWidth: .infinity, alignment: .trailing)
            }

            if let hp = prediction.home_win_probability {
                GeometryReader { geo in
                    HStack(spacing: 0) {
                        Rectangle()
                            .fill(Color.blue)
                            .frame(width: geo.size.width * CGFloat(hp))
                        Rectangle()
                            .fill(Color.red)
                    }
                }
                .frame(height: 8)
                .clipShape(Capsule())
            }

            // 信心指數
            if let confidence = prediction.confidence {
                HStack {
                    Image(systemName: "gauge.with.dots.needle.67percent")
                        .foregroundColor(.purple)
                    Text("信心指數：")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text("\(Int(confidence)) / 10")
                        .font(.subheadline.bold())
                        .foregroundColor(confidenceColor(confidence))
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(Color.cardBackground)
        .cornerRadius(16)
    }

    private func keyFactorsCard(factors: [String]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("關鍵因素", systemImage: "checkmark.seal.fill")
                .font(.subheadline.bold())
                .foregroundColor(.green)
            VStack(alignment: .leading, spacing: 6) {
                ForEach(Array(factors.enumerated()), id: \.offset) { _, factor in
                    HStack(alignment: .top, spacing: 6) {
                        Image(systemName: "circle.fill")
                            .font(.system(size: 5))
                            .foregroundColor(.green)
                            .padding(.top, 7)
                        Text(factor)
                            .font(.callout)
                            .foregroundColor(.primary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.cardBackground)
        .cornerRadius(16)
    }

    private func riskFactorsCard(risks: [String]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("風險因素", systemImage: "exclamationmark.triangle.fill")
                .font(.subheadline.bold())
                .foregroundColor(.orange)
            VStack(alignment: .leading, spacing: 6) {
                ForEach(Array(risks.enumerated()), id: \.offset) { _, risk in
                    HStack(alignment: .top, spacing: 6) {
                        Image(systemName: "circle.fill")
                            .font(.system(size: 5))
                            .foregroundColor(.orange)
                            .padding(.top, 7)
                        Text(risk)
                            .font(.callout)
                            .foregroundColor(.primary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.cardBackground)
        .cornerRadius(16)
    }

    // MARK: - 工具

    private func formatActualScore() -> String {
        guard let h = settlement.homeScore, let a = settlement.awayScore else {
            return "—"
        }
        return "\(h) - \(a)"
    }

    private func confidenceColor(_ value: Double) -> Color {
        switch value {
        case 0..<4: return .red
        case 4..<6: return .orange
        case 6..<8: return .yellow
        default: return .green
        }
    }

    private func leagueIcon(_ league: String) -> String {
        switch league {
        case "MLB": return "⚾"
        case "NBA": return "🏀"
        case "WNBA": return "🏀"
        case "NPB": return "🇯🇵"
        case "CPBL": return "🇹🇼"
        default: return "🏟"
        }
    }

    private var formattedDate: String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "zh_TW")
        formatter.dateFormat = "yyyy/MM/dd"
        return formatter.string(from: settlement.matchDate)
    }
}

// MARK: - 雷達圖元件

private struct RadarSection: View {
    let categories: [String]
    let home: [Double]
    let away: [Double]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("六維能力雷達圖", systemImage: "chart.pie.fill")
                .font(.subheadline.bold())
                .foregroundColor(.indigo)

            HStack(alignment: .top, spacing: 16) {
                ForEach(0..<categories.count, id: \.self) { i in
                    VStack(spacing: 4) {
                        Text(categories[i])
                            .font(.system(size: 10))
                            .foregroundColor(.secondary)
                            .lineLimit(1)
                            .frame(maxWidth: .infinity)
                        Text(home.count > i ? String(format: "%.1f", home[i]) : "—")
                            .font(.system(size: 14, weight: .bold))
                            .foregroundColor(.blue)
                        Text(away.count > i ? String(format: "%.1f", away[i]) : "—")
                            .font(.system(size: 14, weight: .bold))
                            .foregroundColor(.red)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
                    .background(Color(.tertiarySystemBackground))
                    .cornerRadius(8)
                }
            }
            .frame(maxWidth: .infinity)

            // 圖例
            HStack(spacing: 16) {
                HStack(spacing: 4) {
                    Circle().fill(Color.blue).frame(width: 8, height: 8)
                    Text("主隊").font(.caption2).foregroundColor(.secondary)
                }
                HStack(spacing: 4) {
                    Circle().fill(Color.red).frame(width: 8, height: 8)
                    Text("客隊").font(.caption2).foregroundColor(.secondary)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.cardBackground)
        .cornerRadius(16)
    }
}
