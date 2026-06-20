
//
//  APIService.swift
//  PredictX Sports
//
//  Created by Jero on 2026-06-06.
//

import Foundation

struct MatchModel: Codable, Identifiable {
    let gameId: String
    let matchDate: String
    let status: String?
    let homeTeam: String
    let awayTeam: String
    let homeTeamScore: Double?
    let awayTeamScore: Double?
    let aiConfidence: Double?
    let aiHomeProb: Double?
    let aiPredictedScore: String?
    let aiIsHit: Bool?
    let aiActualScore: String?
    
    var id: String { gameId }
    
    enum CodingKeys: String, CodingKey {
        case gameId = "game_id"
        case matchDate = "match_date"
        case status
        case homeTeam = "home_team"
        case awayTeam = "away_team"
        case homeTeamScore = "home_team_score"
        case awayTeamScore = "away_team_score"
        case aiConfidence = "ai_confidence"
        case aiHomeProb = "ai_home_prob"
        case aiPredictedScore = "ai_predicted_score"
        case aiIsHit = "ai_is_hit"
        case aiActualScore = "ai_actual_score"
    }
}

struct AIAnalysisModel: Codable {
    let prediction: Prediction?
    let analysis: Analysis?
    let radar_chart: RadarChart?
    
    struct Prediction: Codable {
        let home_win_probability: Double?
        let away_win_probability: Double?
        let confidence: Double?
        let predicted_score: String?
    }
    
    struct Analysis: Codable {
        let summary: String?
        let key_factors: [String]?
        let risk_factors: [String]?
    }
    
    struct RadarChart: Codable {
        let categories: [String]?
        let home_team: [Double]?
        let away_team: [Double]?
    }
}

// --- Analytics Models ---
struct LeagueAccuracyModel: Codable {
    let league: String
    let total_analyzed: Int
    let total_hits: Int
    let hit_rate: Double
}

struct HitRateTrendModel: Codable {
    let date: String
    let games_count: Int
    let daily_hit_rate: Double
}

class APIService {
    static let shared = APIService()
    // 🚀 Railway 雲端後端（部署完成於 2026-06-14）
    private let baseURL = "https://predictx-sports-production.up.railway.app"
    
    func fetchGames(for league: String, days: Int = 7) async throws -> [MatchModel] {
        guard let url = URL(string: "\(baseURL)/api/games?league=\(league)&days=\(days)") else {
            throw URLError(.badURL)
        }
        
        let (data, response) = try await URLSession.shared.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        
        let decoder = JSONDecoder()
        return try decoder.decode([MatchModel].self, from: data)
    }
    
    func fetchAIAnalysis(gameId: String) async throws -> AIAnalysisModel {
        let cleanId = gameId.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let url = URL(string: "\(baseURL)/api/game_analysis/\(cleanId)") else {
            throw URLError(.badURL)
        }
        
        let (data, response) = try await URLSession.shared.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        
        let decoder = JSONDecoder()
        return try decoder.decode(AIAnalysisModel.self, from: data)
    }

    // MARK: - 🆕 球員資料（TheSportsDB）

    /// 取得球隊完整球員名單（最多 10 位，free tier 限制）
    func fetchTeamRoster(teamId: String) async throws -> TeamRosterResponse {
        guard let url = URL(string: "\(baseURL)/api/players/roster?team_id=\(teamId)") else {
            throw URLError(.badURL)
        }
        let (data, response) = try await URLSession.shared.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(TeamRosterResponse.self, from: data)
    }

    /// 取得單一球員完整資料（基本資料 + 合約 + 榮譽）
    func fetchPlayerDetail(playerId: String) async throws -> PlayerDetailResponse {
        guard let url = URL(string: "\(baseURL)/api/players/\(playerId)") else {
            throw URLError(.badURL)
        }
        let (data, response) = try await URLSession.shared.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(PlayerDetailResponse.self, from: data)
    }

    // --- New Analytics Endpoints ---
    
    func fetchOverallStats() async throws -> [LeagueAccuracyModel] {
        guard let url = URL(string: "\(baseURL)/analytics/overall") else {
            throw URLError(.badURL)
        }
        
        let (data, response) = try await URLSession.shared.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        
        return try JSONDecoder().decode([LeagueAccuracyModel].self, from: data)
    }
    
    func fetchHitRateTrend(league: String?) async throws -> [HitRateTrendModel] {
        var urlString = "\(baseURL)/analytics/trend"
        if let league = league {
            urlString += "?league=\(league)"
        }
        
        guard let url = URL(string: urlString) else {
            throw URLError(.badURL)
        }
        
        let (data, response) = try await URLSession.shared.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        
        return try JSONDecoder().decode([HitRateTrendModel].self, from: data)
    }
    
    func triggerSettlement() async throws -> Int {
        guard let url = URL(string: "\(baseURL)/analytics/settle") else {
            throw URLError(.badURL)
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        
        struct SettleResponse: Codable {
            let settled_count: Int
        }
        
        let res = try JSONDecoder().decode(SettleResponse.self, from: data)
        return res.settled_count
    }
}


// MARK: - 🆕 球員資料模型（TheSportsDB）

struct TeamRosterResponse: Codable {
    let team_id: String
    let count: Int
    let players: [PlayerBasic]
}

struct PlayerBasic: Codable, Identifiable {
    let id: String
    let name: String
    let position: String?
    let nationality: String?
    let birth_date: String?
    let height: String?
    let weight: String?
    let photo_url: String?
    let cutout_url: String?
}

struct PlayerDetailResponse: Codable {
    let player: PlayerDetail
    let contracts: [PlayerContract]?
    let honours: [PlayerHonour]?
}

struct PlayerDetail: Codable {
    let id: String
    let name: String
    let team: String?
    let team_id: String?
    let nationality: String?
    let position: String?
    let birth_date: String?
    let birth_location: String?
    let height: String?
    let weight: String?
    let jersey_number: String?
    let photo_url: String?
    let cutout_url: String?
    let description: String?
}

struct PlayerContract: Codable {
    let id: Int?
    let idPlayer: String?
    let idTeam: String?
    let strTeam: String?
    let strBadge: String?
    let strYearStart: String?
    let strYearEnd: String?
}

struct PlayerHonour: Codable {
    let id: Int?
    let idPlayer: String?
    let strHonour: String?
    let strSport: String?
    let strSeason: String?
}
