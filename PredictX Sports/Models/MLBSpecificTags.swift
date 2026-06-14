import Foundation

/// ⚾ MLB 專屬 AI 預測進階特徵因子
struct MLBSpecificTags: Codable, Hashable {
    // 投手端核心指標
    var homeStarterFIP: Double?   // 主隊先發投手獨立防禦率 (FIP)
    var awayStarterFIP: Double?   // 客隊先發投手獨立防禦率 (FIP)
    var homeStarterWHIP: Double?  // 主隊先發每局被上壘率 (WHIP)
    var awayStarterWHIP: Double?  // 客隊先發每局被上壘率 (WHIP)
    
    // 打擊與環境端核心指標
    var homeTeamwOBA: Double?     // 主隊加權上壘率 (wOBA)
    var awayTeamwOBA: Double?     // 客隊加權上壘率 (wOBA)
    var parkFactor: Double?       // 球場因素修正值 (Park Factor)
    var windDirection: String?    // 即時風向 (例如: "逆風", "順風 15mph")
}
