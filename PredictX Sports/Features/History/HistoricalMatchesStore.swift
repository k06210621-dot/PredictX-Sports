import Foundation
import SwiftUI
import Combine

@MainActor
class HistoricalMatchesStore: ObservableObject {
    @Published var historicalMatches: [LeagueType: [Match]] = [:]
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    private let apiService = APIService.shared
    
    func loadHistoricalMatches() async {
        guard !isLoading else { return }
        isLoading = true
        defer { isLoading = false }
        
        for league in LeagueType.activeCases {
            do {
                let matches = try await apiService.fetchGames(for: league.rawValue, days: 14)
                await MainActor.run {
                    // Define "today" as starting at 00:00:00 UTC
                    var utcCalendar = Calendar(identifier: .gregorian)
                    utcCalendar.timeZone = TimeZone(secondsFromGMT: 0)!
                    let todayStartUTC = utcCalendar.startOfDay(for: Date())
                    
                    let history = matches.filter { model in
                        if let utcDate = parseDate(model.matchDate) {
                            return utcDate < todayStartUTC
                        }
                        return false
                    }
                    self.historicalMatches[league] = history.map {
                        Match(from: $0, leagueType: league)
                    }
                }
            } catch {
                print("❌ [History] Failed to load \(league.rawValue): \(error)")
            }
        }
    }
    
    func matches(for league: LeagueType) -> [Match] {
        return historicalMatches[league] ?? []
    }
}