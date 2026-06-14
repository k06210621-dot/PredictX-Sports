import Foundation

/// ⚽ FIFA 世界盃足球專屬 AI 預測進階特徵因子
struct FIFASpecificTags: Codable, Hashable {
    // 機會創造與進攻質量指標 (排除運氣)
    var homeExpectedGoals: Double?   // 主隊預期進球數 (xG)
    var awayExpectedGoals: Double?   // 客隊預期進球數 (xG)
    
    // 團隊動態與大賽變量
    var nationalChemistry: Double?  // 國家隊球員間默契與磨合度得分 (1.0 ~ 10.0)
    var tacticalSystemAdaptation: Double? // 戰術體系適應變量 (0.0 ~ 1.0)
    
    // 盤口與控球維度
    var possessionPredict: Double?  // AI 預估控球率 (例如: 0.55 代表 55%)
    var cleanSheetProbability: Double? // 零封（無失分）機率
}
