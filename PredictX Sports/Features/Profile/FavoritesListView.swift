import SwiftUI
import Combine

struct FavoritesListView: View {
    @EnvironmentObject var favoritesStore: FavoritesStore
    @State private var selectedMatchForDetail: Match?
    
    var body: some View {
        Group {
            if favoritesStore.favorites.isEmpty {
                VStack(spacing: 20) {
                    Image(systemName: "star.slash")
                        .font(.system(size: 50))
                        .foregroundColor(.secondary.opacity(0.4))
                    Text("尚無收藏")
                        .font(.headline)
                        .foregroundColor(.secondary)
                    Text("在智能分析頁面點擊星星圖示\n即可收藏賽事分析")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.top, 80)
            } else {
                List {
                    ForEach(favoritesStore.favorites) { fav in
                        PredictionRowView(match: favoriteToMatch(fav))
                            .environmentObject(favoritesStore)
                            .listRowInsets(EdgeInsets())
                            .listRowSeparator(.hidden)
                            .padding(.vertical, 4)
                            .contentShape(Rectangle())
                            .onTapGesture {
                                selectedMatchForDetail = favoriteToMatch(fav)
                            }
                    }
                    .onDelete { indexSet in
                        for idx in indexSet {
                            favoritesStore.remove(id: favoritesStore.favorites[idx].id)
                        }
                    }
                    
                    Text("最多收藏 50 筆賽事分析")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                        .frame(maxWidth: .infinity)
                        .listRowBackground(Color.clear)
                }
                .listStyle(.plain)
                .sheet(item: $selectedMatchForDetail) { match in
                    AIAnalysisDetailView(match: match)
                }
            }
        }
        .navigationTitle("AI 推論分析收藏")
        .navigationBarTitleDisplayMode(.inline)
    }
    
    private func favoriteToMatch(_ fav: FavoriteMatch) -> Match {
        let league = LeagueType(rawValue: fav.league) ?? .mlb
        let date = ISO8601DateFormatter().date(from: fav.matchDate) ?? Date()
        
        return Match(
            id: fav.id,
            homeTeam: fav.homeTeam,
            awayTeam: fav.awayTeam,
            homeTeamCN: TeamNameMap.getChineseName(for: fav.homeTeam),
            awayTeamCN: TeamNameMap.getChineseName(for: fav.awayTeam),
            homeScore: fav.homeScore,
            awayScore: fav.awayScore,
            league: league,
            startTime: date,
            location: "",
            status: .scheduled
        )
    }
}