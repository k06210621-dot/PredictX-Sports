import Foundation

struct Team: Identifiable, Codable, Hashable {
    // 這裡使用 String 作為 ID，方便直接對應 Firebase 的 Document ID 或 ESPN 的 Team ID
    let id: String
    var name: String         // 球隊全稱，例如 "Los Angeles Lakers"
    var shortName: String?   // 球隊簡稱，例如 "Lakers"
    var code: String?        // 球隊縮寫，例如 "LAL"
    var logoUrl: String?     // 球隊 Logo 的網路圖片連結
    var conference: String?  // 聯盟分區 (e.g., 東區、西區)，非必填可相容棒球
    
    // 用於聯賽戰績排名 (Standings) 的可選欄位
    var wins: Int?
    var losses: Int?
    var winPercentage: Double?
}
