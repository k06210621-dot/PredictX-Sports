//
//  ScoreListView.swift
//  PredictX Sports
//

import SwiftUI

struct ScoreListView: View {
    @StateObject private var viewModel = ScoreViewModel()
    let league: String
    
    var body: some View {
        List(viewModel.matches) { match in
            HStack {
                Text(match.awayTeam)
                Spacer()
                Text("\(match.awayTeamScore ?? 0) - \(match.homeTeamScore ?? 0)")
                Spacer()
                Text(match.homeTeam)
            }
        }
        .navigationTitle("\(league) 比賽資訊")
        .task {
            await viewModel.loadMatches(league: league)
        }
        .overlay {
            if viewModel.isLoading { ProgressView() }
        }
    }
}
