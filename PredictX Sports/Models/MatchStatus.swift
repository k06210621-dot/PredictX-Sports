import Foundation

/// 跨聯賽標準化賽事即時生命週期狀態
enum MatchStatus: String, Codable, Hashable, Equatable {
    case scheduled = "SCHEDULED"   // 賽前排程
    case live = "LIVE"             // 賽事進行中
    case completed = "COMPLETED"   // 賽事已結束
    case postponed = "POSTPONED"   // 賽事延期
    case cancelled = "CANCELLED"   // 賽事取消
}
