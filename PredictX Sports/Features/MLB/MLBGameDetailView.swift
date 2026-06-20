import SwiftUI

struct MLBGameDetailView: View {
    @StateObject private var viewModel: MLBGameDetailViewModel
    
    // For expandable cards
    @State private var isPitchingExpanded = false
    @State private var isBattingExpanded = false
    
    init(gameId: Int) {
        _viewModel = StateObject(wrappedValue: MLBGameDetailViewModel(gameId: gameId))
    }
    
    var body: some View {
        ZStack {
            // Background
            Color(UIColor.systemBackground)
                .ignoresSafeArea()
            
            if viewModel.isLoading {
                ProgressView("載入比賽詳情...")
                    .progressViewStyle(CircularProgressViewStyle(tint: .blue))
                    .scaleEffect(1.2)
            } else if let error = viewModel.errorMessage {
                VStack {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .font(.largeTitle)
                        .foregroundColor(.orange)
                    Text(error)
                        .multilineTextAlignment(.center)
                        .padding()
                }
            } else {
                ScrollView {
                    VStack(spacing: 20) {
                        // Game Header
                        GameHeaderView(
                            awayTeam: viewModel.awayTeamName,
                            homeTeam: viewModel.homeTeamName,
                            awayScore: viewModel.awayScore,
                            homeScore: viewModel.homeScore,
                            gameDate: viewModel.gameDate,
                            venue: viewModel.venue,
                            status: viewModel.status
                        )
                        .padding(.horizontal)
                        
                        // Pitching Card
                        DisclosureGroup(
                            isExpanded: $isPitchingExpanded,
                            content: {
                                PitchingStatsView(
                                    awayPitchers: viewModel.awayPitchers,
                                    homePitchers: viewModel.homePitchers
                                )
                            },
                            label: {
                                HStack {
                                    Image(systemName: "figure.baseball")
                                        .font(.title2)
                                    Text("投手統計")
                                        .font(.headline)
                                    Spacer()
                                    Image(systemName: isPitchingExpanded ? "chevron.up" : "chevron.down")
                                        .font(.subheadline)
                                }
                                .padding()
                                .background(
                                    RoundedRectangle(cornerRadius: 12)
                                        .fill(Color(UIColor.systemGray6))
                                )
                            }
                        )
                        .padding(.horizontal)
                        
                        // Batting Card
                        DisclosureGroup(
                            isExpanded: $isBattingExpanded,
                            content: {
                                BattingStatsView(
                                    awayBatting: viewModel.awayBatting,
                                    homeBatting: viewModel.homeBatting
                                )
                            },
                            label: {
                                HStack {
                                    Image(systemName: "bolt.fill")
                                        .font(.title2)
                                    Text("打擊統計")
                                        .font(.headline)
                                    Spacer()
                                    Image(systemName: isBattingExpanded ? "chevron.up" : "chevron.down")
                                        .font(.subheadline)
                                }
                                .padding()
                                .background(
                                    RoundedRectangle(cornerRadius: 12)
                                        .fill(Color(UIColor.systemGray6))
                                )
                            }
                        )
                        .padding(.horizontal)
                    }
                    .padding(.vertical)
                }
            }
        }
        .navigationTitle("MLB 比賽詳情")
        .navigationBarTitleDisplayMode(.inline)
    }
}

// MARK: - Subviews

struct GameHeaderView: View {
    let awayTeam: String
    let homeTeam: String
    let awayScore: Int?
    let homeScore: Int?
    let gameDate: Date?
    let venue: String
    let status: String
    
    var body: some View {
        VStack(spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(awayTeam)
                        .font(.title2)
                        .fontWeight(.semibold)
                    Text("@")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text(homeTeam)
                        .font(.title2)
                        .fontWeight(.semibold)
                }
                Spacer()
                
                VStack(alignment: .trailing, spacing: 4) {
                    Text("\(awayScore ?? 0)")
                        .font(.title)
                        .fontWeight(.bold)
                    Text("-")
                        .font(.caption)
                    Text("\(homeScore ?? 0)")
                        .font(.title)
                        .fontWeight(.bold)
                }
            }
            
            HStack {
                Label(venue, systemImage: "mappin.and.ellipse")
                    .font(.subheadline)
                Spacer()
                Label(formattedDate, systemImage: "calendar")
                    .font(.subheadline)
            }
            .foregroundColor(.secondary)
            
            Text(status)
                .font(.caption)
                .fontWeight(.medium)
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(
                    Capsule()
                        .fill(status == "Final" ? Color.green.opacity(0.2) : Color.blue.opacity(0.2))
                )
                .foregroundColor(status == "Final" ? .green : .blue)
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(Color(UIColor.systemBackground))
                .shadow(color: Color.black.opacity(0.05), radius: 5, x: 0, y: 2)
        )
    }
    
    private var formattedDate: String {
        guard let date = gameDate else { return "" }
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }
}

struct PitchingStatsView: View {
    let awayPitchers: [PitcherStats]
    let homePitchers: [PitcherStats]
    
    var body: some View {
        VStack(spacing: 16) {
            HStack {
                VStack(alignment: .leading, spacing: 8) {
                    Text("客隊投手")
                        .font(.headline)
                    ForEach(awayPitchers.prefix(3)) { pitcher in
                        PitcherRowView(pitcher: pitcher)
                    }
                }
                Spacer()
                VStack(alignment: .leading, spacing: 8) {
                    Text("主隊投手")
                        .font(.headline)
                    ForEach(homePitchers.prefix(3)) { pitcher in
                        PitcherRowView(pitcher: pitcher)
                    }
                }
            }
            
            // Team pitching totals
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("客隊總計")
                        .font(.subheadline)
                        .fontWeight(.medium)
                    Text("ERA: \(String(format: "%.2f", awayPitchers.reduce(0.0) { $0 + ($1.stats.era ?? 0.0) } / Double(max(awayPitchers.count, 1))))")
                        .font(.caption)
                    Text("WHIP: \(String(format: "%.2f", awayPitchers.reduce(0.0) { $0 + ($1.stats.whip ?? 0.0) } / Double(max(awayPitchers.count, 1))))")
                        .font(.caption)
                }
                Spacer()
                VStack(alignment: .leading, spacing: 4) {
                    Text("主隊總計")
                        .font(.subheadline)
                        .fontWeight(.medium)
                    Text("ERA: \(String(format: "%.2f", homePitchers.reduce(0.0) { $0 + ($1.stats.era ?? 0.0) } / Double(max(homePitchers.count, 1))))")
                        .font(.caption)
                    Text("WHIP: \(String(format: "%.2f", homePitchers.reduce(0.0) { $0 + ($1.stats.whip ?? 0.0) } / Double(max(homePitchers.count, 1))))")
                        .font(.caption)
                }
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(Color(UIColor.systemGray5))
            )
        }
        .padding()
    }
}

struct PitcherRowView: View {
    let pitcher: PitcherStats
    
    var body: some View {
        HStack {
            Text(pitcher.name)
                .font(.subheadline)
                .lineLimit(1)
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                Text("\(pitcher.stats.inningsPitched ?? 0.0, specifier: "%.1f") IP")
                    .font(.caption2)
                HStack(spacing: 4) {
                    Text("\(pitcher.stats.hits ?? 0)H")
                    Text("\(pitcher.stats.runs ?? 0)R")
                    Text("\(pitcher.stats.earnedRuns ?? 0)ER")
                    Text("\(pitcher.stats.baseOnBalls ?? 0)BB")
                    Text("\(pitcher.stats.strikeOuts ?? 0)K")
                }
                .font(.caption2)
            }
            .frame(width: 120)
        }
        .padding(.vertical, 4)
    }
}

struct BattingStatsView: View {
    let awayBatting: TeamBattingStats?
    let homeBatting: TeamBattingStats?
    
    var body: some View {
        VStack(spacing: 16) {
            HStack {
                VStack(alignment: .leading, spacing: 8) {
                    Text("客隊打擊")
                        .font(.headline)
                    BattingStatRow(label: "安打", value: "\(awayBatting?.hits ?? 0)")
                    BattingStatRow(label: "得分", value: "\(awayBatting?.runs ?? 0)")
                    BattingStatRow(label: "全壘打", value: "\(awayBatting?.homeRuns ?? 0)")
                    BattingStatRow(label: "打點", value: "\(awayBatting?.rbi ?? 0)")
                }
                Spacer()
                VStack(alignment: .leading, spacing: 8) {
                    Text("主隊打擊")
                        .font(.headline)
                    BattingStatRow(label: "安打", value: "\(homeBatting?.hits ?? 0)")
                    BattingStatRow(label: "得分", value: "\(homeBatting?.runs ?? 0)")
                    BattingStatRow(label: "全壘打", value: "\(homeBatting?.homeRuns ?? 0)")
                    BattingStatRow(label: "打點", value: "\(homeBatting?.rbi ?? 0)")
                }
            }
            
            // Rate stats
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("客隊")
                        .font(.subheadline)
                        .fontWeight(.medium)
                    HStack(spacing: 12) {
                        Text("AVG: \(awayBatting?.avg.asString ?? ".000")")
                        Text("OBP: \(awayBatting?.obp.asString ?? ".000")")
                        Text("SLG: \(awayBatting?.slg.asString ?? ".000")")
                    }
                    .font(.caption)
                }
                Spacer()
                VStack(alignment: .leading, spacing: 4) {
                    Text("主隊")
                        .font(.subheadline)
                        .fontWeight(.medium)
                    HStack(spacing: 12) {
                        Text("AVG: \(homeBatting?.avg.asString ?? ".000")")
                        Text("OBP: \(homeBatting?.obp.asString ?? ".000")")
                        Text("SLG: \(homeBatting?.slg.asString ?? ".000")")
                    }
                    .font(.caption)
                }
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(Color(UIColor.systemGray5))
            )
        }
        .padding()
    }
}

struct BattingStatRow: View {
    let label: String
    let value: String
    
    var body: some View {
        HStack {
            Text(label)
                .font(.caption2)
                .foregroundColor(.secondary)
            Spacer()
            Text(value)
                .font(.caption2)
                .fontWeight(.medium)
        }
    }
}

// MARK: - Extensions

extension Double {
    var asString: String {
        String(format: "%.3f", self)
    }
}

extension Int {
    var asString: String {
        String(self)
    }
}

struct MLBGameDetailView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            MLBGameDetailView(gameId: 824593) // Example game ID
        }
    }
}