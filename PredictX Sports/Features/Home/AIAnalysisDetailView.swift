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
                        Text("分析資料載入失敗").font(.headline).foregroundColor(.primary)
                        Text(error).font(.caption).foregroundColor(.secondary).multilineTextAlignment(.center)
                        Button("重試") { Task { await loadAnalysis() } }
                            .buttonStyle(.borderedProminent)
                    }
                    .padding()
                } else if let analysis = analysis {
                    ScrollView(.vertical, showsIndicators: false) {
                        VStack(alignment: .leading, spacing: 20) {
                            
                            // MARK: - 1. 勝率推論卡片
                            VStack(spacing: 15) {
                                Text("AI 推論勝率").font(.headline).foregroundColor(.secondary)
                                
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
                                    
                                    Text("vs").font(.caption).bold().foregroundColor(Color(.tertiaryLabel))
                                    
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
                                    Label("數據置信度：\(String(format: "%.1f", confidence))/10", systemImage: "checkmark.seal.fill")
                                    Spacer()
                                    Label("模型推演比分：\(score)", systemImage: "list.bullet.rectangle")
                                }
                                .font(.subheadline).foregroundColor(.secondary)
                                
                                // 🆕 Apple 審核合規：AI 分析免責提示
                                HStack {
                                    Image(systemName: "info.circle")
                                        .font(.caption2)
                                        .foregroundColor(.orange)
                                    Text("AI 推論結果僅供參考，不保證準確性。實際賽事結果受多種不可預測因素影響。")
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
                                    Label("能力維度分析", systemImage: "chart.pie.fill")
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
                                    Label("AI 深度分析摘要", systemImage: "doc.text.magnifyingglass")
                                        .font(.headline)
                                        .foregroundColor(.primary)
                                    Text(analysisContent.summary ?? "無分析資料")
                                        .font(.body)
                                        .foregroundColor(.primary)
                                        .lineSpacing(4)
                                    
                                    if let factors = analysisContent.key_factors, !factors.isEmpty {
                                        Text("關鍵影響因子").font(.subheadline).bold().foregroundColor(.primary).padding(.top)
                                        ForEach(factors, id: \.self) { factor in
                                            HStack(alignment: .top) {
                                                Image(systemName: "checkmark.circle.fill").foregroundColor(.blue).font(.caption)
                                                Text(factor).font(.subheadline).foregroundColor(.primary)
                                            }
                                            .padding(.vertical, 2)
                                        }
                                    }
                                    
                                    if let risks = analysisContent.risk_factors, !risks.isEmpty {
                                        Text("潛在風險因子").font(.subheadline).bold().foregroundColor(.primary).padding(.top, 8)
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
                            Text("本分析結果由 AI 模型基於歷史數據生成，僅供體育數據研究與統計參考，不構成任何形式的投注建議。")
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
            .navigationTitle("AI 賽事詳情分析")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button(action: { dismiss() }) {
                        Text("關閉").foregroundColor(.primary)
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
        isLoading = true
        print("🔍 [Analysis] loading for gameId: \(match.id)")
        do {
            self.analysis = try await APIService.shared.fetchAIAnalysis(gameId: match.id)
            print("✅ [Analysis] loaded successfully: conf=\(self.analysis?.prediction?.confidence ?? -1)")
            isLoading = false
        } catch {
            print("❌ [Analysis] fetch error: \(error)")
            self.errorMessage = userFriendlyError(error)
            isLoading = false
        }
    }
}
