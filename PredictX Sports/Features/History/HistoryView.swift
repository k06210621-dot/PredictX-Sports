import SwiftUI

struct HistoryView: View {
    @EnvironmentObject private var store: HomeStore
    @State private var selectedLeague: LeagueType = .mlb
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                Spacer().frame(height: 8)
                
                LeagueBadgeWall(selectedLeague: $selectedLeague)
                    .padding(.bottom, 4)
                
                let matches = store.historicalMatches[selectedLeague] ?? []
                
                if matches.isEmpty {
                    ContentUnavailableView(
                        "載入歷史賽事中...",
                        systemImage: "clock.arrow.circlepath",
                        description: Text("\(selectedLeague.rawValue) 正在擷取資料")
                    )
                } else {
                    ScrollView {
                        LazyVStack(spacing: 12) {
                            ForEach(matches) { match in
                                HistoricalMatchCardView(match: match)
                            }
                        }
                        .padding()
                    }
                }
            }
            .background(SportsDarkBackground())
            .navigationTitle("歷史賽事")
            .navigationBarTitleDisplayMode(.inline)
            .task {
                await store.loadHistoryForLeague(selectedLeague)
            }
            .onChange(of: selectedLeague) { oldValue, newLeague in
                Task {
                    await store.loadHistoryForLeague(newLeague)
                }
            }
            .refreshable {
                await store.loadHistoryForLeague(selectedLeague)
            }
        }
    }
}

struct HistoricalMatchCardView: View {
    let match: Match
    
    private var themeColor: Color { LeagueTheme.color(for: match.league) }
    
    private var formattedDate: String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "zh_TW")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "MM/dd (EEE)"
        return formatter.string(from: match.startTime)
    }
    
    private var leagueLabel: String {
        switch match.league {
        case .nba: return "NBA 籃球"
        case .mlb: return "MLB 棒球"
        case .npb: return "NPB 日職"
        case .cpbl: return "CPBL 中職"
        case .fifa: return "FIFA 足球"
        }
    }
    
    var body: some View {
        VStack(spacing: 8) {
            HStack {
                Image(systemName: "calendar")
                    .font(.caption2)
                    .foregroundColor(themeColor)
                Text(formattedDate)
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.5))
                    .fontWeight(.medium)
                Spacer()
                Text(leagueLabel)
                    .font(.caption2)
                    .fontWeight(.bold)
                    .foregroundColor(themeColor)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(themeColor.opacity(0.15))
                    .cornerRadius(6)
            }
            
            HStack(spacing: 16) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(match.homeTeam)
                        .font(.headline)
                        .bold()
                        .foregroundColor(.white)
                    Text(match.homeTeamCN)
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.5))
                }

                Spacer()

                VStack(spacing: 4) {
                    if match.status == .completed, let homeScore = match.homeScore, let awayScore = match.awayScore {
                        Text("\(homeScore) - \(awayScore)")
                            .font(.title2)
                            .fontWeight(.heavy)
                            .foregroundColor(themeColor)
                        Text("最終比分")
                            .font(.system(size: 9))
                            .foregroundColor(.white.opacity(0.4))
                    } else if let predicted = match.aiTotalScorePredict, !predicted.isEmpty {
                        Text(predicted)
                            .font(.title3)
                            .fontWeight(.bold)
                            .foregroundColor(themeColor.opacity(0.6))
                        Text("推演比分")
                            .font(.system(size: 9))
                            .foregroundColor(.white.opacity(0.4))
                    } else {
                        Text("VS")
                            .font(.title3)
                            .fontWeight(.heavy)
                            .foregroundColor(themeColor.opacity(0.4))
                        Text(match.status == .scheduled ? "尚未開打" : "比分未紀錄")
                            .font(.system(size: 9))
                            .foregroundColor(.white.opacity(0.4))
                    }
                }

                Spacer()

                VStack(alignment: .trailing, spacing: 4) {
                    Text(match.awayTeam)
                        .font(.headline)
                        .bold()
                        .foregroundColor(.white)
                    Text(match.awayTeamCN)
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.5))
                }
            }
            
            if match.status == .completed, let isHit = match.aiIsHit {
                HStack {
                    Spacer()
                    HStack(spacing: 4) {
                        Image(systemName: isHit ? "checkmark.circle.fill" : "xmark.circle.fill")
                            .font(.system(size: 14))
                            .foregroundColor(isHit ? .green : .red)
                        Text(isHit ? "AI 分析準確" : "AI 分析未中")
                            .font(.caption)
                            .fontWeight(.semibold)
                            .foregroundColor(isHit ? .green : .red)
                    }
                    .padding(.horizontal, 10)
                    .padding(.vertical, 4)
                    .background((isHit ? Color.green : Color.red).opacity(0.12))
                    .cornerRadius(8)
                }
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(Color(red: 0.14, green: 0.16, blue: 0.26))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(themeColor.opacity(0.3), lineWidth: 1.5)
                )
        )
        .shadow(color: themeColor.opacity(0.2), radius: 8, x: 0, y: 3)
        .padding(.horizontal, 4)
    }
}
