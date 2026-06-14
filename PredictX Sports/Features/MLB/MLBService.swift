import Foundation

struct MLBService {
    static let baseURL = "https://statsapi.mlb.com/api/v1"
    
    static func fetchBoxscore(for gameId: Int) async throws -> BoxscoreResponse {
        let urlString = "\(baseURL)/game/\(gameId)/boxscore"
        guard let url = URL(string: urlString) else {
            throw URLError(.badURL)
        }
        
        let (data, response) = try await URLSession.shared.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(BoxscoreResponse.self, from: data)
    }
}