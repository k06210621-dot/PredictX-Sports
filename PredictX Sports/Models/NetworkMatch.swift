import Foundation

// MARK: - GitHub 開源 ESPN 公開賽事 API 響應結構
struct ESPNResponse: Codable {
    let events: [ESPNEvent]
}

struct ESPNEvent: Codable {
    let id: String
    let name: String            // 例如: "Golden State Warriors at Los Angeles Lakers"
    let shortName: String       // 例如: "GS @ LAL"
    let date: String            // ISO8601 時間字串
    let competitions: [ESPNCompetition]
}

struct ESPNCompetition: Codable {
    let venue: ESPNVenue?
    let competitors: [ESPNCompetitor]
    let status: ESPNStatus
}

struct ESPNVenue: Codable {
    let fullName: String        // 球場名稱 (例如: "Crypto.com Arena")
}

struct ESPNCompetitor: Codable {
    let id: String
    let homeAway: String        // "home" 或 "away"
    let team: ESPNTeamData
}

struct ESPNTeamData: Codable {
    let displayName: String     // 球隊真實名稱
}

struct ESPNStatus: Codable {
    let type: ESPNStatusType
}

struct ESPNStatusType: Codable {
    let name: String            // 狀態碼，例如 "STATUS_SCHEDULED", "STATUS_FINAL"
}
