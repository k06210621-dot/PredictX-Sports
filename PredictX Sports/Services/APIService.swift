
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
    // ⚠️ 部署 Railway 後，請將下方 URL 換成 Railway 提供的公開網域（例如 https://predictx-sports.up.railway.app）
    private let baseURL = "https://YOUR_RAILWAY_DOMAIN.up.railway.app"
    
    func fetchGames(for league: String, days: Int = 7) async throws -> [MatchModel] {
        guard let url = URL(string: "\(baseURL)/api/games?league=\(league)") else {
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
