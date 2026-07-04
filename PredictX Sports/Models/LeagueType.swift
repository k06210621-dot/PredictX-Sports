import Foundation

/// 統一聯賽型別（僅顯示有真實賽事資料的聯賽）
enum LeagueType: String, Codable, CaseIterable, Identifiable {
    case mlb = "MLB"
    case npb = "NPB"
    case cpbl = "CPBL"
    case nba = "NBA"
    case wnba = "WNBA"

    var id: String { self.rawValue }

    var displayName: String {
        switch self {
        case .mlb: return "MLB 棒球"
        case .npb: return "日本職棒"
        case .cpbl: return "中華職棒"
        case .nba: return "NBA 籃球"
        case .wnba: return "WNBA 籃球"
        }
    }

    var shortLabel: String {
        switch self {
        case .mlb: return "棒球"
        case .npb: return "日職"
        case .cpbl: return "中職"
        case .nba: return "籃球"
        case .wnba: return "女籃"
        }
    }

    var isActive: Bool {
        switch self {
        case .mlb, .npb, .cpbl, .nba, .wnba: return true
        }
    }

    static var activeCases: [LeagueType] {
        allCases.filter { $0.isActive }
    }
}
