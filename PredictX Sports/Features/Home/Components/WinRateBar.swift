import SwiftUI

/// 雙向勝率能量條 — 主隊藍色、客隊紅色
///
/// 提供三種顯示狀態：
/// - `.real`：完整顯示勝率（已解鎖或付費會員）
/// - `.locked`：完全隱藏，只顯示灰底 + 解鎖按鈕（Free/Basic 會員未付費）
struct WinRateBar: View {
    var homeWinRate: Double // 0.0 ~ 1.0
    var homeTeam: String
    var awayTeam: String
    var isLocked: Bool = false  // 是否鎖定
    var onUnlockTapped: (() -> Void)? = nil  // 解鎖按鈕點擊

    var body: some View {
        VStack(spacing: 6) {
            if isLocked {
                // 鎖定狀態：只顯示灰底 + 解鎖提示
                HStack(spacing: 6) {
                    Image(systemName: "lock.fill")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Text(NSLocalizedString("card.locked_hint", comment: "🔒 點擊解鎖 AI 推論隊伍強度 (-20 點)"))
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Spacer()
                }

                GeometryReader { geometry in
                    Rectangle()
                        .fill(Color.gray.opacity(0.25))
                        .frame(height: 6)
                        .clipShape(Capsule())
                        .overlay(
                            // 中間有一條隱約的虛線，提示有內容
                            HStack(spacing: 3) {
                                ForEach(0..<8, id: \.self) { _ in
                                    Capsule()
                                        .fill(Color.gray.opacity(0.4))
                                        .frame(width: 8, height: 2)
                                }
                            }
                        )
                }
                .frame(height: 6)
                .contentShape(Rectangle())
                .onTapGesture {
                    onUnlockTapped?()
                }
            } else {
                // 已解鎖 / 付費會員：完整顯示
                HStack {
                    Text("\(homeTeam) \(Int(homeWinRate * 100))%")
                        .font(.caption2).bold().foregroundColor(Color.blue.opacity(0.9))
                    Spacer()
                    Text("\(Int((1.0 - homeWinRate) * 100))% \(awayTeam)")
                        .font(.caption2).bold().foregroundColor(Color.red.opacity(0.9))
                }

                GeometryReader { geometry in
                    HStack(spacing: 2) {
                        LinearGradient(
                            gradient: Gradient(colors: [Color.blue, Color.blue.opacity(0.8)]),
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                        .frame(width: max(geometry.size.width * CGFloat(homeWinRate) - 1, 0))
                        .clipShape(Capsule())
                        .shadow(color: Color.blue.opacity(0.4), radius: 4, x: 0, y: 1)

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
}