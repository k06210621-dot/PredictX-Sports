import SwiftUI

/// 雙向勝率能量條 — 主隊藍色、客隊紅色，營造運動對抗張力
struct WinRateBar: View {
    var homeWinRate: Double // 0.0 ~ 1.0
    var homeTeam: String
    var awayTeam: String
    
    var body: some View {
        VStack(spacing: 6) {
            // 百分比文字
            HStack {
                Text("\(homeTeam) \(Int(homeWinRate * 100))%")
                    .font(.caption2).bold().foregroundColor(Color.blue.opacity(0.9))
                Spacer()
                Text("\(Int((1.0 - homeWinRate) * 100))% \(awayTeam)")
                    .font(.caption2).bold().foregroundColor(Color.red.opacity(0.9))
            }
            
            // 雙色對比條
            GeometryReader { geometry in
                HStack(spacing: 2) {
                    // 主隊藍色
                    LinearGradient(
                        gradient: Gradient(colors: [Color.blue, Color.blue.opacity(0.8)]),
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                    .frame(width: max(geometry.size.width * CGFloat(homeWinRate) - 1, 0))
                    .clipShape(Capsule())
                    .shadow(color: Color.blue.opacity(0.4), radius: 4, x: 0, y: 1)
                    
                    // 客隊紅色
                    LinearGradient(
                        gradient: Gradient(colors: [Color.red.opacity(0.8), Color.red]),
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                    .frame(width: max(geometry.size.width * CGFloat(1.0 - homeWinRate) - 1, 0))
                    .clipShape(Capsule())
                    .shadow(color: Color.red.opacity(0.4), radius: 4, x: 0, y: 1)
                }
            }
            .frame(height: 6)
        }
    }
}
