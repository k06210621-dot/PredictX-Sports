import SwiftUI

/// 🦴 可重用骨架螢幕元件 — 支援 Shimmer 動畫效果（深色主題適配）
/// 在資料載入期間顯示，給使用者「資料即將呈現」的視覺暗示
struct SkeletonCardView: View {
    var width: CGFloat? = nil
    var height: CGFloat? = nil
    
    var body: some View {
        RoundedRectangle(cornerRadius: 16)
            .fill(Color(.systemGray4))
            .frame(width: width, height: height)
            .shimmer()
    }
}

// MARK: - 預測卡片專用骨架

struct PredictionRowSkeleton: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // 頂部：徽章 + 日期 + 信心指數
            HStack {
                SkeletonCardView(width: 80, height: 24)
                Spacer()
                SkeletonCardView(width: 60, height: 24)
                SkeletonCardView(width: 60, height: 24)
                SkeletonCardView(width: 28, height: 24)
            }
            
            // 中部：主客隊 VS 對決
            HStack(alignment: .center) {
                VStack(alignment: .leading, spacing: 6) {
                    SkeletonCardView(width: 120, height: 20)
                    SkeletonCardView(width: 80, height: 14)
                }
                Spacer()
                SkeletonCardView(width: 36, height: 24)
                Spacer()
                VStack(alignment: .trailing, spacing: 6) {
                    SkeletonCardView(width: 120, height: 20)
                    SkeletonCardView(width: 80, height: 14)
                }
            }
            
            // 底部：勝率條
            SkeletonCardView(width: nil, height: 20)
                .frame(maxWidth: .infinity)
        }
        .padding()
        .background(Color.cardBackground)
        .cornerRadius(20)
        .overlay(
            RoundedRectangle(cornerRadius: 20)
                .stroke(Color(red: 0.20, green: 0.22, blue: 0.32), lineWidth: 1)
        )
    }
}

// MARK: - 焦點賽事卡片骨架

struct FocusMatchSkeleton: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                SkeletonCardView(width: 60, height: 18)
                Spacer()
                SkeletonCardView(width: 40, height: 18)
            }
            SkeletonCardView(width: 180, height: 22)
            SkeletonCardView(width: 80, height: 16)
        }
        .padding()
        .frame(width: 240)
        .background(Color.cardBackground)
        .cornerRadius(16)
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color(red: 0.20, green: 0.22, blue: 0.32), lineWidth: 1)
        )
    }
}

// MARK: - 聯賽按鈕骨架

struct LeagueFilterSkeleton: View {
    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 12) {
                ForEach(0..<4) { _ in
                    SkeletonCardView(width: 80, height: 40)
                }
            }
            .padding(.horizontal)
        }
    }
}

// MARK: - 主頁面完整骨架螢幕

struct HomeSkeletonView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            HStack {
                SkeletonCardView(width: 24, height: 24)
                SkeletonCardView(width: 200, height: 24)
                Spacer()
            }
            .padding(.horizontal)
            
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 16) {
                    ForEach(0..<3) { _ in
                        FocusMatchSkeleton()
                    }
                }
                .padding(.horizontal)
            }
            
            HStack {
                SkeletonCardView(width: 24, height: 24)
                SkeletonCardView(width: 150, height: 24)
                Spacer()
            }
            .padding(.horizontal)
            
            LeagueFilterSkeleton()
            
            HStack {
                SkeletonCardView(width: 24, height: 24)
                SkeletonCardView(width: 180, height: 24)
                Spacer()
            }
            .padding(.horizontal)
            
            VStack(spacing: 14) {
                ForEach(0..<4) { _ in
                    PredictionRowSkeleton()
                }
            }
            .padding(.horizontal)
        }
        .padding(.vertical)
    }
}

// MARK: - 分析詳細頁面骨架

struct AnalysisSkeletonView: View {
    var body: some View {
        ScrollView(.vertical, showsIndicators: false) {
            VStack(alignment: .leading, spacing: 20) {
                VStack(spacing: 15) {
                    SkeletonCardView(width: 120, height: 20)
                    SkeletonCardView(width: nil, height: 50)
                    HStack {
                        SkeletonCardView(width: 100, height: 14)
                        Spacer()
                        SkeletonCardView(width: 100, height: 14)
                    }
                    HStack {
                        SkeletonCardView(width: 150, height: 16)
                        Spacer()
                        SkeletonCardView(width: 150, height: 16)
                    }
                }
                .padding()
                .background(Color.cardBackground)
                .cornerRadius(16)
                
                VStack(alignment: .leading, spacing: 12) {
                    SkeletonCardView(width: 160, height: 20)
                    SkeletonCardView(width: nil, height: 200)
                }
                .padding()
                .background(Color.cardBackground)
                .cornerRadius(16)
                
                VStack(alignment: .leading, spacing: 12) {
                    SkeletonCardView(width: 180, height: 20)
                    SkeletonCardView(width: nil, height: 60)
                    SkeletonCardView(width: 140, height: 18)
                    SkeletonCardView(width: nil, height: 16)
                    SkeletonCardView(width: nil, height: 16)
                    SkeletonCardView(width: nil, height: 16)
                }
                .padding()
                .background(Color.cardBackground)
                .cornerRadius(16)
            }
            .padding()
        }
    }
}

// MARK: - Shimmer 動畫修飾器

struct ShimmerModifier: ViewModifier {
    @State private var phase: CGFloat = -0.3
    
    func body(content: Content) -> some View {
        content
            .overlay(
                GeometryReader { geo in
                    LinearGradient(
                        gradient: Gradient(stops: [
                            .init(color: .clear, location: phase - 0.15),
                            .init(color: Color.white.opacity(0.15), location: phase),
                            .init(color: .clear, location: phase + 0.15)
                        ]),
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                    .frame(width: geo.size.width * 1.5)
                    .offset(x: -geo.size.width * 0.25)
                    .animation(
                        Animation.linear(duration: 1.5)
                            .repeatForever(autoreverses: false),
                        value: phase
                    )
                }
                .clipped()
            )
            .onAppear {
                withAnimation(.linear(duration: 1.5).repeatForever(autoreverses: false)) {
                    phase = 1.3
                }
            }
    }
}

extension View {
    func shimmer() -> some View {
        modifier(ShimmerModifier())
    }
}

// MARK: - Preview

#Preview("完整骨架螢幕") {
    ScrollView {
        HomeSkeletonView()
    }
    .background(Color(red: 0.06, green: 0.08, blue: 0.18))
}

// MARK: - Analytics 骨架

struct AnalyticsSkeletonView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 25) {
            // 綜合準確率卡片
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    SkeletonCardView(width: 160, height: 14)
                    Spacer()
                    SkeletonCardView(width: 80, height: 12)
                }
                HStack(alignment: .bottom, spacing: 8) {
                    SkeletonCardView(width: 120, height: 44)
                    Spacer()
                    SkeletonCardView(width: 80, height: 14)
                }
            }
            .padding()
            .background(Color.cardBackground)
            .cornerRadius(16)

            // 10場戰績卡片
            VStack(alignment: .leading, spacing: 12) {
                SkeletonCardView(width: 180, height: 16)
                HStack(spacing: 6) {
                    ForEach(0..<10) { _ in
                        SkeletonCardView(width: 28, height: 28)
                    }
                }
                .padding(.vertical, 4)
                ForEach(0..<3) { _ in
                    SkeletonCardView(width: nil, height: 44)
                }
            }
            .padding()
            .background(Color.cardBackground)
            .cornerRadius(16)

            // 聯賽選擇
            VStack(alignment: .leading, spacing: 12) {
                SkeletonCardView(width: 200, height: 16)
                ForEach(0..<4) { _ in
                    SkeletonCardView(width: nil, height: 72)
                }
            }
            .padding()
            .background(Color.cardBackground)
            .cornerRadius(16)

            // 趨勢圖
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    SkeletonCardView(width: 200, height: 16)
                    Spacer()
                    SkeletonCardView(width: 60, height: 12)
                }
                SkeletonCardView(width: nil, height: 220)
            }
            .padding()
            .background(Color.cardBackground)
            .cornerRadius(16)
        }
        .padding()
    }
}

#Preview("賽事卡片骨架") {
    PredictionRowSkeleton()
        .padding()
}

#Preview("焦點賽事骨架") {
    FocusMatchSkeleton()
}
