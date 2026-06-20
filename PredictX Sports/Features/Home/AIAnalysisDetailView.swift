import SwiftUI
import Charts

struct AIAnalysisDetailView: View {
    let match: Match
    @EnvironmentObject private var favoritesStore: FavoritesStore
    @State private var analysis: AIAnalysisModel? = nil
    @State private var isLoading = true
    @State private var errorMessage: String? = nil
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationStack {
            ZStack {
                Color(red: 0.06, green: 0.08, blue: 0.18).ignoresSafeArea()
                
                if isLoading {
                    AnalysisSkeletonView()
                } else if let error = errorMessage {
                    VStack(spacing: 20) {
                        Image(systemName: "exclamationmark.triangle.fill").font(.largeTitle).foregroundColor(.orange)
                        Text(NSLocalizedString("analysis.load_failed", comment: "")).font(.headline).foregroundColor(.primary)
                        Text(error).font(.caption).foregroundColor(.secondary).multilineTextAlignment(.center)
                        // 🆕 [E] 強化重試按鈕：加箭頭圖示 + 標準化樣式
                        Button(action: { Task { await loadAnalysis() } }) {
                            HStack(spacing: 6) {
                                Image(systemName: "arrow.clockwise")
                                    .font(.subheadline.bold())
                                Text(NSLocalizedString("action.retry", comment: ""))
                                    .font(.subheadline.bold())
                            }
                            .foregroundColor(.white)
                            .padding(.horizontal, 22)
                            .padding(.vertical, 10)
                            .background(Color.blue)
                            .clipShape(Capsule())
                        }
                    }
                    .padding()
                } else if let analysis = analysis {
                    ScrollView(.vertical, showsIndicators: false) {
                        VStack(alignment: .leading, spacing: 20) {
                            
                            // MARK: - 1. 勝率推論卡片
                            VStack(spacing: 15) {
                                Text(NSLocalizedString("section.ai_win_rate", comment: "")).font(.headline).foregroundColor(.secondary)
                                
                                let homeWinProb = analysis.prediction?.home_win_probability ?? 0.0
                                let awayWinProb = analysis.prediction?.away_win_probability ?? 0.0
                                let confidence = analysis.prediction?.confidence ?? 0.0
                                let score = analysis.prediction?.predicted_score ?? "N/A"
                                
                                HStack(spacing: 0) {
                                    ZStack(alignment: .leading) {
                                        Capsule().fill(Color.blue.opacity(0.25))
                                        Capsule().fill(Color.blue)
                                            .frame(width: CGFloat(homeWinProb) * 200)
                                        Text(String(format: "%.0f%%", homeWinProb * 100))
                                            .font(.caption).bold().foregroundColor(.primary)
                                            .padding(.leading, 10)
                                    }
                                    .frame(width: 200, height: 24)
                                    
                                    Text("vs")
                                        .font(.caption2)
                                        .foregroundColor(Color(.tertiaryLabel))
                                        .opacity(0.5)
                                    
                                    ZStack(alignment: .trailing) {
                                        Capsule().fill(Color.red.opacity(0.25))
                                        Capsule().fill(Color.red)
                                            .frame(width: CGFloat(awayWinProb) * 200)
                                        Text(String(format: "%.0f%%", awayWinProb * 100))
                                            .font(.caption).bold().foregroundColor(.primary)
                                            .padding(.trailing, 10)
                                    }
                                    .frame(width: 200, height: 24)
                                }
                                .frame(maxWidth: .infinity)
                                
                                HStack {
                                    Label(match.homeTeam, systemImage: "circle.fill")
                                        .font(.caption).foregroundColor(.blue)
                                    Spacer()
                                    Label(match.awayTeam, systemImage: "circle.fill")
                                        .font(.caption).foregroundColor(.red)
                                }
                                .padding(.horizontal, 4)
                                
                                HStack {
                                    Label(String.localizedStringWithFormat(NSLocalizedString("label.confidence", comment: ""), String(format: "%.1f", confidence)), systemImage: "checkmark.seal.fill")
                                    Spacer()
                                    Label(String.localizedStringWithFormat(NSLocalizedString("label.predicted_score", comment: ""), score), systemImage: "list.bullet.rectangle")
                                }
                                .font(.subheadline).foregroundColor(.secondary)
                                
                                // 🆕 Apple 審核合規：AI 分析免責提示
                                HStack {
                                    Image(systemName: "info.circle")
                                        .font(.caption2)
                                        .foregroundColor(.orange)
                                    Text(NSLocalizedString("disclaimer.ai_accuracy", comment: ""))
                                        .font(.caption2)
                                        .foregroundColor(.secondary)
                                        .multilineTextAlignment(.leading)
                                }
                                .padding(.top, 4)
                            }
                            .padding()
                            .background(Color.cardBackground)
                            .cornerRadius(16)
                            
                            // MARK: - 2. 能力維度分析 (雷達圖)
                            if let radar = analysis.radar_chart, 
                               let cats = radar.categories, 
                               let homeVals = radar.home_team, 
                               let awayVals = radar.away_team {
                                VStack(alignment: .leading, spacing: 12) {
                                    Label(NSLocalizedString("section.radar_chart", comment: ""), systemImage: "chart.pie.fill")
                                        .font(.headline)
                                        .foregroundColor(.primary)
                                    
                                    RadarChartView(
                                        categories: cats,
                                        homeValues: homeVals,
                                        awayValues: awayVals,
                                        homeTeamName: match.homeTeam,
                                        awayTeamName: match.awayTeam
                                    )
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 5)
                                }
                                .padding()
                                .background(Color.cardBackground)
                                .cornerRadius(16)
                            }
                            
                            // MARK: - 3. 深度分析文字
                            if let analysisContent = analysis.analysis {
                                VStack(alignment: .leading, spacing: 12) {
                                    Label(NSLocalizedString("section.ai_summary", comment: ""), systemImage: "doc.text.magnifyingglass")
                                        .font(.headline)
                                        .foregroundColor(.primary)
                                    Text(analysisContent.summary ?? NSLocalizedString("empty.no_analysis", comment: ""))
                                        .font(.body)
                                        .foregroundColor(.primary)
                                        .lineSpacing(4)
                                    
                                    if let factors = analysisContent.key_factors, !factors.isEmpty {
                                        Text(NSLocalizedString("label.key_factors", comment: "")).font(.subheadline).bold().foregroundColor(.primary).padding(.top)
                                        ForEach(factors, id: \.self) { factor in
                                            HStack(alignment: .top) {
                                                Image(systemName: "checkmark.circle.fill").foregroundColor(.blue).font(.caption)
                                                Text(factor).font(.subheadline).foregroundColor(.primary)
                                            }
                                            .padding(.vertical, 2)
                                        }
                                    }
                                    
                                    if let risks = analysisContent.risk_factors, !risks.isEmpty {
                                        Text(NSLocalizedString("label.risk_factors", comment: "")).font(.subheadline).bold().foregroundColor(.primary).padding(.top, 8)
                                        ForEach(risks, id: \.self) { risk in
                                            HStack(alignment: .top) {
                                                Image(systemName: "exclamationmark.triangle.fill").foregroundColor(.orange).font(.caption)
                                                Text(risk).font(.subheadline).foregroundColor(.primary)
                                            }
                                            .padding(.vertical, 2)
                                        }
                                    }
                                }
                                .padding()
                                .background(Color.cardBackground)
                                .cornerRadius(16)
                            }
                            
                            // MARK: - 4. 合規免責聲明
                            Text(NSLocalizedString("disclaimer.full", comment: ""))
                                .font(.caption2)
                                .foregroundColor(Color(.tertiaryLabel))
                                .multilineTextAlignment(.center)
                                .padding(.vertical, 20)
                                .padding(.horizontal)
                        }
                        .padding()
                    }
                }
            }
            .navigationTitle(NSLocalizedString("nav.title", comment: ""))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button(action: { dismiss() }) {
                        Text(NSLocalizedString("nav.close", comment: "")).foregroundColor(.primary)
                    }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: {
                        favoritesStore.toggle(match: match)
                    }) {
                        Image(systemName: favoritesStore.isFavorited(gameId: match.id) ? "star.fill" : "star")
                            .foregroundColor(favoritesStore.isFavorited(gameId: match.id) ? .yellow : .gray)
                    }
                }
            }
            .task {
                await loadAnalysis()
            }
        }
    }
    
    private func loadAnalysis() async {
        // 🆕 [C] 快取優先：避免重複扣點困擾
        if let cached = AnalysisCache.shared.get(gameId: match.id) {
            print("⚡ [Analysis] cache hit for gameId: \(match.id)")
            self.analysis = cached
            self.isLoading = false
            return
        }

        isLoading = true
        print("🔍 [Analysis] loading for gameId: \(match.id)")
        do {
            let result = try await APIService.shared.fetchAIAnalysis(gameId: match.id)
            self.analysis = result
            AnalysisCache.shared.set(result, gameId: match.id)
            print("✅ [Analysis] loaded successfully: conf=\(self.analysis?.prediction?.confidence ?? -1)")
            isLoading = false
        } catch {
            print("❌ [Analysis] fetch error: \(error)")
            self.errorMessage = userFriendlyError(error)
            isLoading = false
        }
    }
}
