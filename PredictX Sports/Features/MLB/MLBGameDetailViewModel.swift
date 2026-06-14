import Foundation
import Combine

@MainActor
final class MLBGameDetailViewModel: ObservableObject {
    @Published var gameId: Int
    @Published var isLoading = true
    @Published var errorMessage: String?
    
    // Boxscore data
    @Published var awayTeamName: String = ""
    @Published var homeTeamName: String = ""
    @Published var awayScore: Int?
    @Published var homeScore: Int?
    @Published var gameDate: Date?
    @Published var venue: String = ""
    @Published var status: String = ""
    
    // Pitching stats
    @Published var awayPitchers: [PitcherStats] = []
    @Published var homePitchers: [PitcherStats] = []
    
    // Batting stats
    @Published var awayBatting: TeamBattingStats?
    @Published var homeBatting: TeamBattingStats?
    
    private var cancellables = Set<AnyCancellable>()
    
    init(gameId: Int) {
        self.gameId = gameId
        fetchGameData()
    }
    
    private func fetchGameData() {
        isLoading = true
        errorMessage = nil
        
        Task {
            do {
                let boxscore = try await MLBService.fetchBoxscore(for: gameId)
                await MainActor.run {
                    self.updateWithBoxscore(boxscore)
                    self.isLoading = false
                }
            } catch {
                await MainActor.run {
                    self.errorMessage = userFriendlyError(error)
                    self.isLoading = false
                }
            }
        }
    }
    
    private func updateWithBoxscore(_ boxscore: BoxscoreResponse) {
        // Teams
        awayTeamName = boxscore.teams.away.team.name ?? ""
        homeTeamName = boxscore.teams.home.team.name ?? ""
        awayScore = boxscore.teams.away.score
        homeScore = boxscore.teams.home.score
        
        // Game info
        if let dateString = boxscore.gameDate {
            let formatter = ISO8601DateFormatter()
            gameDate = formatter.date(from: dateString)
        }
        venue = boxscore.venue?.name ?? ""
        status = boxscore.status?.detailedState ?? ""
        
        // Pitching stats
        awayPitchers = extractPitchers(from: boxscore.teams.away)
        homePitchers = extractPitchers(from: boxscore.teams.home)
        
        // Batting stats
        awayBatting = TeamBattingStats(from: boxscore.teams.away.teamStats?.batting)
        homeBatting = TeamBattingStats(from: boxscore.teams.home.teamStats?.batting)
    }
    
    private func extractPitchers(from team: BoxscoreTeam) -> [PitcherStats] {
        var pitchers: [PitcherStats] = []
        for (_, playerInfo) in team.players {
            guard let position = playerInfo.position?.abbreviation, position == "P",
                  let stats = playerInfo.stats?.pitching else { continue }
            pitchers.append(PitcherStats(
                name: playerInfo.person?.fullName ?? "Unknown",
                stats: stats
            ))
        }
        // Sort by innings pitched descending
        pitchers.sort { ($0.stats.inningsPitched ?? 0.0) > ($1.stats.inningsPitched ?? 0.0) }
        return pitchers
    }
}

// MARK: - Data Models

struct BoxscoreResponse: Codable {
    let teams: Teams
    let gameDate: String?
    let venue: Venue?
    let status: GameStatus?
}

struct Teams: Codable {
    let away: BoxscoreTeam
    let home: BoxscoreTeam
}

struct BoxscoreTeam: Codable {
    let team: TeamInfo
    let score: Int?
    let teamStats: TeamStats?
    let players: [String: PlayerInfo]
}

struct TeamInfo: Codable {
    let name: String?
}

struct Venue: Codable {
    let name: String?
}

struct GameStatus: Codable {
    let detailedState: String?
}

struct TeamStats: Codable {
    let batting: TeamBatting?
    let pitching: TeamPitching?
}

struct TeamBatting: Codable {
    let hits: Int?
    let runs: Int?
    let homeRuns: Int?
    let rbi: Int?
    let avg: Double?
    let obp: Double?
    let slg: Double?
}

struct TeamPitching: Codable {
    let era: Double?
    let whip: Double?
    let hitsPerNineInnings: Double?
    let strikeouts: Int?
    let walks: Int?
}

struct PlayerInfo: Codable {
    let person: Person?
    let position: Position?
    let stats: PlayerStats?
}

struct Person: Codable {
    let fullName: String?
}

struct Position: Codable {
    let abbreviation: String?
}

struct PlayerStats: Codable {
    let pitching: PitchingStats?
}

struct PitchingStats: Codable {
    let inningsPitched: Double?
    let hits: Int?
    let runs: Int?
    let earnedRuns: Int?
    let baseOnBalls: Int?
    let strikeOuts: Int?
    let era: Double?
    let whip: Double?
}

struct PitcherStats: Identifiable {
    let id = UUID()
    let name: String
    let stats: PitchingStats
}

struct TeamBattingStats {
    let hits: Int
    let runs: Int
    let homeRuns: Int
    let rbi: Int
    let avg: Double
    let obp: Double
    let slg: Double
    
    init(from batting: TeamBatting?) {
        self.hits = batting?.hits ?? 0
        self.runs = batting?.runs ?? 0
        self.homeRuns = batting?.homeRuns ?? 0
        self.rbi = batting?.rbi ?? 0
        self.avg = batting?.avg ?? 0.0
        self.obp = batting?.obp ?? 0.0
        self.slg = batting?.slg ?? 0.0
    }
}