
import Foundation
import SwiftUI
import Combine

@MainActor
class AnalyticsStore: ObservableObject {

    @Published var leagueAccuracies: [LeagueAccuracy] = []
    @Published var winRateTrends: [WinRateTrend] = []
    @Published var selectedLeague: String = "MLB"
    @Published var overallAccuracy: Double = 0.0
    @Published var recentSettlements: [RecentSettlement] = []   // 🆕 最近 10 場戰績
    @Published var isLoading: Bool = false
    @Published var errorMessage: String? = nil

    init() {
        Task {
            await loadRealAnalyticsData()
        }
    }

    func loadRealAnalyticsData() async {
        isLoading = true

        do {
            let realLeagues = try await APIService.shared.fetchOverallStats()

            self.leagueAccuracies = realLeagues
                .filter { $0.league != "FIFA" }  // 排除 FIFA（已停用）
                .map {
                LeagueAccuracy(
                    league: $0.league,
                    hitRate: $0.hit_rate,
                    totalAnalyzed: $0.total_analyzed
                )
            }

            let totalHits = realLeagues
                .filter { $0.league != "FIFA" }
                .reduce(0) { $0 + $1.total_hits }
            let totalGames = realLeagues
                .filter { $0.league != "FIFA" }
                .reduce(0) { $0 + $1.total_analyzed }
            self.overallAccuracy = totalGames > 0 ? Double(totalHits) / Double(totalGames) : 0.0

            let defaultLeague = self.leagueAccuracies.first?.league ?? "MLB"
            await updateTrendForLeague(league: defaultLeague)

            // 🆕 載入最近 10 場紀錄（背景跑，不擋趨勢圖）
            await loadRecentSettlements()

            self.isLoading = false
        } catch {
            print("Error loading real analytics: \(error)")
            self.errorMessage = "無法載入驗證率統計"
            self.isLoading = false
        }
    }

    func updateTrendForLeague(league: String) async {
        self.selectedLeague = league

        do {
            let realTrends = try await APIService.shared.fetchHitRateTrend(league: league)

            self.winRateTrends = realTrends.compactMap { trend -> WinRateTrend? in
                // 後端回傳 ISO 日期字串 (e.g., "2026-06-13")，轉為 Date 才能讓 Chart 正確排序
                guard let date = parseDate(trend.date) else { return nil }
                return WinRateTrend(date: date, hitRate: trend.daily_hit_rate)
            }
        } catch {
            print("Error updating trend for \(league): \(error)")
            self.errorMessage = "無法載入 \(league) 驗證率趨勢"
        }
    }

    // 🆕 並行抓所有聯盟近 30 天賽事，過濾已完成且已結算的，取最近 10 場
    private func loadRecentSettlements() async {
        var rawHits: [(league: LeagueType, id: String, homeTeam: String, awayTeam: String,
                       dateString: String, homeScore: Int?, awayScore: Int?,
                       predictedScore: String?, isHit: Bool)] = []

        // 五聯盟並行抓取（最多 30 天，確保樣本足夠）
        // 注意：先在背景 context 篩選「已結算」資料，parseDate 統一回到 MainActor 內執行，
        //       避免子任務中跨 actor 呼叫的 strict concurrency 警告。
        await withTaskGroup(of: [(league: LeagueType, id: String, homeTeam: String, awayTeam: String,
                                  dateString: String, homeScore: Int?, awayScore: Int?,
                                  predictedScore: String?, isHit: Bool)].self) { group in
            for league in LeagueType.activeCases {
                group.addTask {
                    do {
                        let models = try await APIService.shared.fetchGames(for: league.rawValue, days: 30)
                        return models.compactMap { m -> (league: LeagueType, id: String, homeTeam: String, awayTeam: String,
                                                         dateString: String, homeScore: Int?, awayScore: Int?,
                                                         predictedScore: String?, isHit: Bool)? in
                            // 條件：必須有結算結果（aiIsHit 非 nil）+ 比分存在
                            guard let isHit = m.aiIsHit,
                                  m.homeTeamScore != nil || m.awayTeamScore != nil else {
                                return nil
                            }
                            return (league,
                                    m.gameId,
                                    m.homeTeam,
                                    m.awayTeam,
                                    m.matchDate,
                                    m.homeTeamScore.map { Int($0) },
                                    m.awayTeamScore.map { Int($0) },
                                    m.aiPredictedScore,
                                    isHit)
                        }
                    } catch {
                        print("⚠️ [RecentForm] \(league.rawValue) 拉取失敗: \(error)")
                        return []
                    }
                }
            }

            for await batch in group {
                rawHits.append(contentsOf: batch)
            }
        }

        // 回到 MainActor，把 dateString 解析為 Date 並組裝 RecentSettlement
        let settlements: [RecentSettlement] = rawHits.compactMap { item in
            guard let date = parseDate(item.dateString) else { return nil }
            return RecentSettlement(
                id: item.id,
                league: item.league.rawValue,
                homeTeam: item.homeTeam,
                awayTeam: item.awayTeam,
                matchDate: date,
                homeScore: item.homeScore,
                awayScore: item.awayScore,
                predictedScore: item.predictedScore,
                isHit: item.isHit
            )
        }

        // 按日期降冪排序，取最近 10 場
        let sorted = settlements.sorted { $0.matchDate > $1.matchDate }
        // 🆕 去重：同一場比賽可能因時區在資料庫存成多筆（同 game_id），保留最新一筆
        var seen = Set<String>()
        let deduped = sorted.filter { seen.insert($0.id).inserted }
        self.recentSettlements = Array(deduped.prefix(10))
    }

    // 🆕 最近 10 場的命中率（給卡片副標題用）
    var recentFormRate: Double {
        guard !recentSettlements.isEmpty else { return 0.0 }
        let hits = recentSettlements.filter { $0.isHit }.count
        return Double(hits) / Double(recentSettlements.count)
    }

    /// 解析後端回傳的 ISO 日期字串（"YYYY-MM-DD"）為 Date 型別
    private func parseDate(_ dateString: String) -> Date? {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.timeZone = TimeZone(identifier: "Asia/Taipei")
        return formatter.date(from: dateString)
    }
}
