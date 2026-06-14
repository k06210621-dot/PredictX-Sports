import Foundation

/// 跨球種標準化球員模型 (Unified Player Model)
struct Player: Codable, Identifiable, Hashable {
    var id: String
    var name: String
    var teamId: String
    var jerseyNumber: String
    var position: String
    var age: Int
    var injuryStatus: InjuryStatus // Active / Day-to-Day / OUT
    var avatarUrl: String?
    
    // 跨球種專屬外掛特徵欄位 (特徵工程映射)
    var nbaStats: NBAPlayerStats?
    var baseballStats: BaseballPlayerStats? // 相容 MLB / NPB / CPBL
    var fifaStats: FIFAPlayerStats?
    
    enum InjuryStatus: String, Codable {
        case active = "ACTIVE"
        case dayToDay = "DAY_TO_DAY"
        case out = "OUT" // 💡 觸發基礎戰力修正模組扣減
    }
}

// MARK: - 🏀 籃球員進階效率指標
struct NBAPlayerStats: Codable, Hashable {
    var ppg: Double     // 場均得分
    var rpg: Double     // 場均籃板
    var apg: Double     // 場均助攻
    var tsPercent: Double // TS% 真實命中率
    var usgPercent: Double // USG% 球權使用率
    var shotCoordinates: [HeatmapNode] // 投籃命中率熱區座標集
}

// MARK: - ⚾ 棒球員進階技術指標 (Sabermetrics)
struct BaseballPlayerStats: Codable, Hashable {
    // 打者/投手通用進階欄位
    var war: Double     // WAR 勝場貢獻值
    var wrcPlus: Double? // wRC+ 標準化加權得分創造力 (打者)
    var fip: Double?    // FIP 獨立防禦率 (投手)
    var whip: Double?   // WHIP 每局被上壘率 (投手)
    var strikeZoneHotspots: [Double] // 投手九宮格進壘率或打者打擊熱區 (9個元素)
}

// MARK: - ⚽ 足球員機會質量指標
struct FIFAPlayerStats: Codable, Hashable {
    var goals: Int
    var assists: Int
    var xa: Double      // xA 預期助攻數
    var shotCreatingActions: Double // 每 90 分鐘創造射門機會次數
}

// MARK: - 📊 虛擬熱區基礎節點
struct HeatmapNode: Codable, Hashable, Identifiable {
    var id: String { "\(x)-\(y)" }
    let x: Int          // 矩陣橫座標
    let y: Int          // 矩陣縱座標
    let frequency: Double // 出手或進攻頻率 (0.0 ~ 1.0)
    let efficiency: Double // 該區域真實命中率 (0.0 ~ 1.0)
}
