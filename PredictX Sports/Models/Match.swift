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
        
        // 💡 移除舊版 NBA/MLB +24h 的過時調整，現在 parseDate 已統一以 UTC 中午為基準
        let parsed = parseDate(model.matchDate) ?? Date(timeIntervalSince1970: 0)
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
        self.aiTotalScorePredict = Match.sanitizePredictedScore(model.aiPredictedScore)
        self.aiIsHit = model.aiIsHit
        self.aiActualScore = model.aiActualScore
    }

    /// 是否已有 AI 分析內容
    /// 條件：aiConfidence 或 aiWinRateHome 有值，且 game_analysis 資料存在
    var hasAnalysis: Bool {
        return aiConfidence != nil || aiWinRateHome != nil
    }

    /// 清洗 AI 預測比分，僅保留「整數-整數」格式（例如 "5-4"）。
    /// 不合規的污染字串（中英隊名、空格格式）一律回傳 nil，避免誤顯示。
    /// 注意：純數字-數字格式中允許全形「－」（U+FF0D）轉為半形「-」。
    static func sanitizePredictedScore(_ raw: String?) -> String? {
        guard let raw = raw?.trimmingCharacters(in: .whitespacesAndNewlines),
              !raw.isEmpty else { return nil }
        let normalized = raw
            .replacingOccurrences(of: "－", with: "-")  // 全形 → 半形
            .replacingOccurrences(of: "—", with: "-")  // em-dash → 半形
            .replacingOccurrences(of: "–", with: "-")  // en-dash → 半形
            .replacingOccurrences(of: " ", with: "")
        // 嚴格正則：可選空白 + 整數 + 半形減號 + 整數 + 可選空白
        let pattern = #"^(\d+)-(\d+)$"#
        if let regex = try? NSRegularExpression(pattern: pattern),
           let m = regex.firstMatch(in: normalized,
                                    range: NSRange(normalized.startIndex..., in: normalized)),
           m.numberOfRanges == 3 {
            let homeRange = Range(m.range(at: 1), in: normalized)!
            let awayRange = Range(m.range(at: 2), in: normalized)!
            return "\(normalized[homeRange])-\(normalized[awayRange])"
        }
        return nil
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
            // 如果是純日期（無時區資訊），強制將時間設為 UTC 中午，避免時區偏移誤判為前一天
            if !hasTimezone {
                var components = Calendar.current.dateComponents([.year, .month, .day], from: date)
                components.hour = 12
                components.minute = 0
                return Calendar.current.date(from: components) ?? date
            }
            return date
        }
    }
    
    return nil
}
