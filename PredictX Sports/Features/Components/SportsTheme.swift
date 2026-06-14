import SwiftUI

// MARK: - 運動主題共用定義

/// 運動深色背景漸層（模擬球場夜間氛圍）
struct SportsDarkBackground: View {
    @State private var animate = false
    
    var body: some View {
        LinearGradient(
            colors: [
                Color(red: 0.06, green: 0.08, blue: 0.18),
                Color(red: 0.10, green: 0.12, blue: 0.22),
                Color(red: 0.06, green: 0.08, blue: 0.18)
            ],
            startPoint: animate ? .topLeading : .bottomTrailing,
            endPoint: animate ? .bottomTrailing : .topLeading
        )
        .ignoresSafeArea()
        .onAppear {
            withAnimation(.linear(duration: 15).repeatForever(autoreverses: true)) {
                animate.toggle()
            }
        }
    }
}

/// 各聯賽主題色
enum LeagueTheme {
    static func color(for league: LeagueType) -> Color {
        switch league {
        case .mlb:  return Color(red: 0.12, green: 0.35, blue: 0.75)
        case .nba:  return Color(red: 0.85, green: 0.40, blue: 0.05)
        case .npb:  return Color(red: 0.85, green: 0.65, blue: 0.13)
        case .cpbl: return Color(red: 0.15, green: 0.65, blue: 0.25)
        case .fifa: return Color(red: 0.55, green: 0.15, blue: 0.75)
        }
    }
    
    /// 聯賽按鈕漸層（深色背景用）
    static func gradient(for league: LeagueType) -> LinearGradient {
        let c = color(for: league)
        return LinearGradient(
            colors: [c, c.opacity(0.7)],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
    }
    
    /// 聯賽未選中色（深色背景用，半透明）
    static func unselectedBg(for league: LeagueType) -> Color {
        color(for: league).opacity(0.18)
    }
    
    /// 聯賽陰影色
    static func shadowColor(for league: LeagueType) -> Color {
        color(for: league).opacity(0.25)
    }
}

/// 深色運動卡片背景
struct SportsCardBackground: View {
    var body: some View {
        RoundedRectangle(cornerRadius: 16)
            .fill(Color(red: 0.14, green: 0.16, blue: 0.26))
    }
}

/// 深色輔助卡片背景（比主卡片略淺）
struct SportsCardSecondaryBackground: View {
    var body: some View {
        RoundedRectangle(cornerRadius: 16)
            .fill(Color(red: 0.16, green: 0.18, blue: 0.28))
    }
}
