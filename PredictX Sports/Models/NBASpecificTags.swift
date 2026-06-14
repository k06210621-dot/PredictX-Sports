import Foundation

/// 🏀 NBA 專屬 AI 預測進階特徵因子 (Four Factors & Pace)
struct NBASpecificTags: Codable, Hashable {
    // 四大核心因素 (Four Factors) - 主隊
    var homeEFG: Double?          // 主隊有效投籃命中率 (eFG%)
    var homeTOV: Double?          // 主隊失誤率 (TOV%)
    var homeORB: Double?          // 主隊進攻籃板率 (ORB%)
    var homeFTRate: Double?       // 主隊罰球率 (FT Rate)
    
    // 四大核心因素 (Four Factors) - 客隊
    var awayEFG: Double?          // 客隊有效投籃命中率 (eFG%)
    var awayTOV: Double?          // 客隊失誤率 (TOV%)
    var awayORB: Double?          // 客隊進攻籃板率 (ORB%)
    var awayFTRate: Double?       // 客隊罰球率 (FT Rate)
    
    // 戰術與動態節奏
    var pace: Double?             // 預估比賽節奏 (Pace/每48分鐘回合數)
    var homeNetRating: Double?    // 主隊百回合淨效率 (Net Rating)
    var awayNetRating: Double?    // 客隊百回合淨效率 (Net Rating)
}
