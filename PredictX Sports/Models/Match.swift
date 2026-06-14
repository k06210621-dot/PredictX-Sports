import Foundation

/// 萬能賽事資料模型 (已完美閉環相容五大聯賽進階特徵集)
struct Match: Codable, Identifiable, Hashable {
    var id: String
    var league: LeagueType
    var homeTeam: String
    var awayTeam: String
    var homeTeamCN: String
    var awayTeamCN: String
    var homeScore: Int?
    var awayScore: Int?
    var startTime: Date
    var location: String
    var status: MatchStatus
    
    var aiWinRateHome: Double?
    var aiConfidence: Double?
    var aiRecommendation: String?
    var aiTotalScorePredict: String?
    var aiIsHit: Bool?
    var aiActualScore: String?
    
    var nbaFeatures: NBASpecificTags?
    var mlbFeatures: MLBSpecificTags?
    var cpblFeatures: CPBLSpecificTags?
    var fifaFeatures: FIFASpecificTags?
    var npbFeatures: NPBSpecificTags?
    
    init(from model: MatchModel, leagueType: LeagueType = .nba) {
        self.id = model.gameId
        self.league = leagueType
        self.homeTeam = model.homeTeam
        self.awayTeam = model.awayTeam
        self.homeTeamCN = TeamNameMap.getChineseName(for: model.homeTeam)
        self.awayTeamCN = TeamNameMap.getChineseName(for: model.awayTeam)
        self.homeScore = model.homeTeamScore.map { Int($0) }
        self.awayScore = model.awayTeamScore.map { Int($0) }
        
        // 💡 極限容錯：如果解析失敗，給予 1970-01-01，確保資料會出現在歷史賽事而非消失
        var parsed = parseDate(model.matchDate) ?? Date(timeIntervalSince1970: 0)
        // 🕐 NBA/MLB 日期來自美國 API（美東時間），轉換為台北時間（+1 天）
        if leagueType == .nba || leagueType == .mlb {
            parsed = parsed.addingTimeInterval(86400) // 加 24 小時
        }
        self.startTime = parsed
        
        self.location = "Unknown"
        let statusStr = (model.status ?? "").uppercased()
        self.status = switch statusStr {
        case "SCHEDULED": .scheduled
        case "LIVE": .live
        case "COMPLETED", "FINAL", "FINISHED": .completed
        case "POSTPONED": .postponed
        case "CANCELLED": .cancelled
        default: .scheduled
        }
        
        // AI 預測資料直接從賽事列表 API 帶入
        self.aiConfidence = model.aiConfidence
        self.aiWinRateHome = model.aiHomeProb
        self.aiTotalScorePredict = model.aiPredictedScore
        self.aiIsHit = model.aiIsHit
        self.aiActualScore = model.aiActualScore
    }
    
    init(id: String = UUID().uuidString,
         homeTeam: String,
         awayTeam: String,
         homeTeamCN: String = "",
         awayTeamCN: String = "",
         homeScore: Int? = nil,
         awayScore: Int? = nil,
         league: LeagueType,
         startTime: Date,
         location: String,
         status: MatchStatus) {
        self.id = id
        self.homeTeam = homeTeam
        self.awayTeam = awayTeam
        self.homeTeamCN = homeTeamCN.isEmpty ? homeTeam : homeTeamCN
        self.awayTeamCN = awayTeamCN.isEmpty ? awayTeam : awayTeamCN
        self.homeScore = homeScore
        self.awayScore = awayScore
        self.league = league
        self.startTime = startTime
        self.location = location
        self.status = status
    }
}

// MARK: - 日期解析輔助函數 (極限容錯版)

func parseDate(_ dateString: String) -> Date? {
    guard !dateString.isEmpty else { return nil }
    
    let hasTimezone = dateString.contains("GMT") || dateString.contains("+") || dateString.contains("Z")
    let timeFormats = ["yyyy-MM-dd'T'HH:mm:ssX", "yyyy-MM-dd'T'HH:mm:ss", "EEE, dd MMM yyyy HH:mm:ss ZZZZ", "EEE, dd MMM yyyy HH:mm:ss zzz"]
    let dateFormats = ["yyyy-MM-dd HH:mm:ss", "yyyy-MM-dd"]
    let formats = hasTimezone ? timeFormats : dateFormats
    let tz = hasTimezone ? TimeZone(secondsFromGMT: 0) : TimeZone(identifier: "Asia/Taipei")
    
    let formatter = DateFormatter()
    formatter.locale = Locale(identifier: "en_US_POSIX")
    formatter.timeZone = tz
    
    for format in formats {
        formatter.dateFormat = format
        if let date = formatter.date(from: dateString) {
            return date
        }
    }
    
    return nil
}
