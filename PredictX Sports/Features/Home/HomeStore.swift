import Foundation
import SwiftUI
import Combine

/// 💡 首席專家優化：ViewModel 全面升級 Case-Insensitive 防禦機制，並與 Firebase 廣播源無縫咬合
@MainActor
class HomeStore: ObservableObject {
    
    // 對外釋出的響應式狀態機
    @Published var focusMatches: [Match] = []
    @Published var filteredPredictions: [Match] = []
    @Published var historicalMatches: [LeagueType: [Match]] = [:]
    @Published var selectedLeague: LeagueType = .mlb
    @Published var isLoading: Bool = false
    @Published var errorMessage: String? = nil
    
    // 內部全量賽事快取記憶體暫存區
    private var allMatches: [Match] = []
    private var cancellables = Set<AnyCancellable>()
    private var hasLoadedFullHistory: Bool = false
    
    init() {
        setupDataStreamObservers()
        
        // 開機時立即使用高優先權背景工作隔離，發送聯網請求，絕不阻塞主執行緒
        Task(priority: .userInitiated) {
            await importAllSportsData()
        }
    }
    
    /// 💡 核心優化：建立強韌的雙向數據流監聽管道
    private func setupDataStreamObservers() {
        // 監聽選中聯賽的即時改變，接收 newLeague 參數秒級動態過濾
        $selectedLeague
            .receive(on: RunLoop.main)
            .sink { [weak self] newLeague in
                self?.filterMatches(by: newLeague)
            }
            .store(in: &cancellables)
    }
    
    func importAllSportsData() async {
        guard !isLoading else { return }
        isLoading = true
        defer { isLoading = false }

        do {
            // 1. 抓取所有聯盟的賽事（跨聯盟組裝焦點賽事需要）
            //    改用 days=14 確保智慧分析首頁能完整顯示「今天 + 未來 7 天」
            //    之所有賽事（原本 days=7 會漏掉週一~週日的尾段，例：週一只能看到當天）
            var combined: [Match] = []
            for league in LeagueType.activeCases {
                let games = try await APIService.shared.fetchGames(for: league.rawValue, days: 14)
                combined.append(contentsOf: games.map { Match(from: $0, leagueType: league) })
            }
            // 以 id 去重, 避免跨聯盟或重複拉取造成的 duplicate ID 警告
            let unique = Dictionary(grouping: combined, by: { $0.id })
                .compactMapValues { $0.first }
                .values
                .sorted { $0.startTime < $1.startTime }

            await MainActor.run {
                let mappedMatches = Array(unique)
                self.allMatches = mappedMatches

                // 使用 UTC 計算今天起始，與 loadHistoryForLeague 一致
                var utcCalendar = Calendar(identifier: .gregorian)
                utcCalendar.timeZone = TimeZone(secondsFromGMT: 0)!
                let todayStartUTC = utcCalendar.startOfDay(for: Date())

                // 將各聯盟歷史資料分開存入
                let history = mappedMatches.filter { $0.startTime < todayStartUTC }
                // 按 league 分組存入
                for league in LeagueType.activeCases {
                    let leagueHistory = history.filter { $0.league == league }
                    if self.historicalMatches[league] == nil || self.historicalMatches[league]!.isEmpty {
                        self.historicalMatches[league] = leagueHistory
                    }
                }

                self.updateUIElements(for: selectedLeague)
            }
        } catch {
            print("❌ [Database Fetch Error]: \(error)")
            await MainActor.run {
                self.errorMessage = userFriendlyError(error)
            }
        }
    }

    /// 載入所有聯盟的歷史賽事（每次從 API 重新拉取，確保資料為最新）
    func loadHistoryForAllLeagues() async {
        var utcCalendar = Calendar(identifier: .gregorian)
        utcCalendar.timeZone = TimeZone(secondsFromGMT: 0)!
        let todayStartUTC = utcCalendar.startOfDay(for: Date())

        for league in LeagueType.activeCases {
            do {
                let models = try await APIService.shared.fetchGames(for: league.rawValue, days: 30)
                await MainActor.run {
                    let allMatches = models.map { Match(from: $0, leagueType: league) }
                    let history = allMatches.filter { match in
                        match.startTime < todayStartUTC || match.status == .completed
                    }.sorted { a, b in
                        a.startTime > b.startTime
                    }
                    // 以 id 去重, 避免重複拉取造成的 duplicate
                    let unique = Array(Dictionary(grouping: history, by: { $0.id })
                        .compactMapValues { $0.first }.values)
                    self.historicalMatches[league] = unique
                    print("✅ [History] \(league.rawValue) loaded \(unique.count) historical matches (from \(allMatches.count) total)")

                    // 🆕 警告：偵測 status=FINAL 但無比分的異常賽事（後端 cron 漏抓警示）
                    let incomplete = unique.filter { $0.status == .completed && ($0.homeScore == nil || $0.awayScore == nil) }
                    if !incomplete.isEmpty {
                        print("⚠️ [History] \(league.rawValue) \(incomplete.count) 場已完成但比分未紀錄：")
                        for m in incomplete.prefix(5) {
                            print("   - \(m.startTime) \(m.homeTeam) vs \(m.awayTeam)")
                        }
                    }
                }
            } catch {
                let nsError = error as NSError
                if nsError.code == NSURLErrorCancelled {
                    print("⚠️ [History] \(league.rawValue) request was cancelled, will retry on next visit")
                } else {
                    print("❌ [History Fetch Error] \(league.rawValue): \(error)")
                }
            }
        }
    }
    
    /// 💡 保留向後相容（單一聯賽載入）
    func loadHistoryForLeague(_ league: LeagueType) async {
        // 只載入一次完整歷史：第一次進入歷史頁面時抓取全部聯賽，之後跳過
        if hasLoadedFullHistory {
            print("✅ [History] Full history already loaded, using cache")
            return
        }
        hasLoadedFullHistory = true
        await loadHistoryForAllLeagues()
    }
    
    private func updateUIElements(for specificLeague: LeagueType? = nil) {
        // 統一在 UTC 層級進行比對，徹底消除時區偏移導致的資料消失問題
        var utcCalendar = Calendar(identifier: .gregorian)
        utcCalendar.timeZone = TimeZone(secondsFromGMT: 0)!
        let todayStartUTC = utcCalendar.startOfDay(for: Date())
        let yesterdayStartUTC = todayStartUTC.addingTimeInterval(-86400)
        let tomorrowEndUTC = todayStartUTC.addingTimeInterval(172800)
        
        let league = specificLeague ?? selectedLeague
        
        // 只保留當前選中聯盟的 upcoming 賽事
        let upcomingMatches = allMatches.filter {
            $0.league == league && $0.startTime >= todayStartUTC
        }
        self.filteredPredictions = upcomingMatches.sorted { a, b in
            a.startTime < b.startTime
        }
        
        // 焦點賽事：跨聯盟，只顯示昨天/今天/明天 + 數據置信度 > 8
        self.focusMatches = allMatches.filter {
            let dateInRange = $0.startTime >= yesterdayStartUTC && $0.startTime < tomorrowEndUTC
            let highConfidence = ($0.aiConfidence ?? 0.0) > 8.0
            return dateInRange && highConfidence
        }.sorted { ($0.aiConfidence ?? 0.0) > ($1.aiConfidence ?? 0.0) }
    }
    
    private func filterMatches(by league: LeagueType) {
        // 即時更新 UI，只顯示該聯盟賽事，不重新抓取全部資料
        updateUIElements(for: league)
    }
}
