import Foundation
import SwiftUI
import Combine

/// 收藏賽事資料模型
struct FavoriteMatch: Codable, Identifiable {
    let id: String
    let league: String
    let homeTeam: String
    let awayTeam: String
    let matchDate: String
    let homeScore: Int?
    let awayScore: Int?
    let aiConfidence: Double?
    let aiHomeProb: Double?
    let savedAt: Date
}

/// 收藏管理（UserDefaults 持久化，最多 50 筆）
class FavoritesStore: ObservableObject {
    @Published var favorites: [FavoriteMatch] = []
    
    private let maxFavorites = 50
    private let storageKey = "predictx_favorites"
    
    init() {
        load()
    }
    
    func isFavorited(gameId: String) -> Bool {
        favorites.contains { $0.id == gameId }
    }
    
    func toggle(match: Match) {
        if let idx = favorites.firstIndex(where: { $0.id == match.id }) {
            favorites.remove(at: idx)
        } else {
            let fm = FavoriteMatch(
                id: match.id,
                league: match.league.rawValue,
                homeTeam: match.homeTeam,
                awayTeam: match.awayTeam,
                matchDate: ISO8601DateFormatter().string(from: match.startTime),
                homeScore: match.homeScore,
                awayScore: match.awayScore,
                aiConfidence: match.aiConfidence,
                aiHomeProb: match.aiWinRateHome,
                savedAt: Date()
            )
            favorites.insert(fm, at: 0)
            if favorites.count > maxFavorites {
                favorites = Array(favorites.prefix(maxFavorites))
            }
        }
        save()
    }
    
    func remove(id: String) {
        favorites.removeAll { $0.id == id }
        save()
    }
    
    private func load() {
        guard let data = UserDefaults.standard.data(forKey: storageKey) else { return }
        favorites = (try? JSONDecoder().decode([FavoriteMatch].self, from: data)) ?? []
    }
    
    private func save() {
        if let data = try? JSONEncoder().encode(favorites) {
            UserDefaults.standard.set(data, forKey: storageKey)
        }
    }
}
