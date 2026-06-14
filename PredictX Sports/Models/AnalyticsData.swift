
import Foundation

/// 用於趨勢圖顯示的命中率數據結構
struct WinRateTrend: Identifiable, Hashable {
    let id = UUID()
    var date: String      // 日期 (e.g., "06/01")
    var hitRate: Double   // 當日命中率 (e.684)
}

/// 用於分聯賽命中率顯示的結構
struct LeagueAccuracy: Identifiable, Hashable {
    let id = UUID()
    var league: String    // 聯賽名稱 (e.g., "MLB")
    var hitRate: Double   // 命中率
    var totalAnalyzed: Int // 分析總場數

    /// 結算依據說明
    var settlementNote: String {
        switch league {
        case "FIFA": return "以總分大小 2.5 為依據"
        default:     return "以主客隊勝負為依據"
        }
    }
}

/// 單場 AI 結算結果 — 最近戰績條使用
struct RecentSettlement: Identifiable, Hashable {
    let id: String
    let league: String      // 聯賽名稱（顯示用）
    let homeTeam: String
    let awayTeam: String
    let matchDate: Date
    let homeScore: Int?
    let awayScore: Int?
    let predictedScore: String?
    let isHit: Bool         // AI 是否命中
}
