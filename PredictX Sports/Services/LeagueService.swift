import Foundation

protocol LeagueService {
    // 獲取特定日期的比賽
    func fetchGames(date: Date) async throws -> [Match]
    
    // 獲取球隊資訊 (回傳統一的 Team 模型)
    func fetchTeams() async throws -> [Team]
    
    // 獲取特定球隊的球員名單 (回傳統一的 Player 模型)
    func fetchPlayers(teamID: String) async throws -> [Player]
}
