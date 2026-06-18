import SwiftUI

// MARK: - 競技聯盟徽章牆
struct LeagueBadgeWall: View {
    @Binding var selectedLeague: LeagueType

    // 上排：棒球聯賽
    private let topRow: [LeagueType] = [.mlb, .npb, .cpbl]
    // 下排：其他聯賽
    private let bottomRow: [LeagueType] = [.nba]

    var body: some View {
        VStack(spacing: 8) {
            // 上排：MLB / NPB / CPBL
            HStack(spacing: 20) {
                ForEach(topRow) { league in
                    LeagueBadgeView(
                        league: league,
                        isSelected: selectedLeague == league
                    )
                    .onTapGesture {
                        withAnimation(.spring(response: 0.4, dampingFraction: 0.7)) {
                            selectedLeague = league
                        }
                    }
                }
            }

            // 下排：NBA
            HStack(spacing: 20) {
                ForEach(bottomRow) { league in
                    LeagueBadgeView(
                        league: league,
                        isSelected: selectedLeague == league
                    )
                    .onTapGesture {
                        withAnimation(.spring(response: 0.4, dampingFraction: 0.7)) {
                            selectedLeague = league
                        }
                    }
                }
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .padding(.top, 12) // 整體下移，避免貼頂
    }
}

// MARK: - 單一聯賽徽章
struct LeagueBadgeView: View {
    let league: LeagueType
    let isSelected: Bool

    @State private var pulseAnim: CGFloat = 0.5

    var body: some View {
        VStack(spacing: 6) {
            // 徽章本體
            ZStack {
                // 選中光暈
                if isSelected {
                    Circle()
                        .fill(leagueColor.opacity(0.2))
                        .frame(width: 80, height: 80)
                        .blur(radius: 10)
                }

                // 徽章圓底
                Circle()
                    .fill(
                        isSelected
                            ? leagueColor
                            : Color(.systemGray6)
                    )
                    .frame(width: 68, height: 68)
                    .overlay(
                        Circle()
                            .stroke(
                                isSelected ? leagueColor.opacity(0.6) : Color.gray.opacity(0.2),
                                lineWidth: isSelected ? 2.5 : 1
                            )
                    )
                    .shadow(
                        color: isSelected ? leagueColor.opacity(0.4) : .clear,
                        radius: 8, x: 0, y: 4
                    )

                // 徽章圖示
                badgeIcon
                    .font(.system(size: 30, weight: .bold))
                    .foregroundColor(isSelected ? .white : leagueColor)

                // 選中時的外圈光暈動畫
                if isSelected && league.hasPulse {
                    Circle()
                        .stroke(leagueColor.opacity(0.3 * pulseAnim), lineWidth: 3)
                        .frame(width: 76, height: 76)
                        .scaleEffect(1 + 0.08 * pulseAnim)
                }
            }

            // 聯賽名稱（加大字體）
            Text(league.rawValue)
                .font(.system(size: 16, weight: .bold))
                .foregroundColor(isSelected ? leagueColor : .secondary)

            // 中文名稱（加大字體）
            Text(league.shortLabel)
                .font(.system(size: 13, weight: .medium))
                .foregroundColor(.secondary.opacity(0.7))
        }
        .scaleEffect(isSelected ? 1.05 : 0.95)
        .onAppear {
            if league.hasPulse {
                withAnimation(.easeInOut(duration: 1.2).repeatForever()) {
                    pulseAnim = 1.0
                }
            }
        }
    }

    @ViewBuilder
    private var badgeIcon: some View {
        switch league {
        case .mlb:
            Image(systemName: "baseball.fill")
        case .npb:
            Image(systemName: "baseball") // 空心棒球輪廓
        case .cpbl:
            Image(systemName: "baseball.fill")
        case .nba:
            Image(systemName: "basketball.fill")
        }
    }

    private var leagueColor: Color {
        switch league {
        case .mlb:  return Color(red: 0.15, green: 0.35, blue: 0.75)
        case .npb:  return Color(red: 0.8, green: 0.55, blue: 0.08)
        case .cpbl: return Color(red: 0.85, green: 0.15, blue: 0.08)
        case .nba:  return Color(red: 0.85, green: 0.4, blue: 0.05)
        }
    }
}

extension LeagueType {
    var hasPulse: Bool {
        switch self {
        case .cpbl, .nba: return true
        case .mlb, .npb: return false
        }
    }
}

#Preview {
    VStack {
        LeagueBadgeWall(selectedLeague: .constant(.mlb))
            .padding()
        Spacer()
    }
}
