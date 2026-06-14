//
//  ScoreViewModel.swift
//  PredictX Sports
//

import Foundation
import SwiftUI
import Combine

@MainActor
class ScoreViewModel: ObservableObject {
    @Published var matches: [MatchModel] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    private let apiService = APIService.shared
    
    func loadMatches(league: String) async {
        isLoading = true
        errorMessage = nil
        do {
            self.matches = try await apiService.fetchGames(for: league, days: 7)
        } catch {
            self.errorMessage = userFriendlyError(error)
        }
        isLoading = false
    }
}
