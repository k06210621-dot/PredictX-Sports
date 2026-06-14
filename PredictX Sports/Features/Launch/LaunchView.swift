import SwiftUI

struct LaunchView: View {
    // MARK: - 動態動畫狀態
    @State private var isLogoVisible: Bool = false      // 控制 Logo 粒子化浮現
    @State private var isLineScanning: Bool = false     // 控制 AI 掃描線動畫
    @State private var scanOffset: CGFloat = -120       // 掃描線的初始位置
    @State private var isAnimationCompleted: Bool = false // 動態是否結束
    
    // 用於回傳開機完成的閉包 (Closure)
    var onFinished: () -> Void

    var body: some View {
        ZStack {
            // 頂級開機必備：純黑背景
            Color.black
                .ignoresSafeArea()
            
            VStack(spacing: 25) {
                Spacer()
                
                // MARK: - LOGO 科技感浮現區
                ZStack {
                    // 載入 Assets 中的白金 Logo
                    Image("AppLogo")
                        .resizable()
                        .scaledToFit()
                        .frame(width: 220, height: 220)
                        .clipShape(Circle())
                        // 透過外發光與霧化，模擬粒子化浮現的科幻外觀
                        .shadow(color: Color.blue.opacity(isLogoVisible ? 0.6 : 0), radius: 20, x: 0, y: 0)
                        .opacity(isLogoVisible ? 1.0 : 0.0)
                        .scaleEffect(isLogoVisible ? 1.0 : 0.8)
                    
                    // MARK: - AI 藍光掃描線
                    if isLineScanning {
                        Rectangle()
                            .fill(
                                LinearGradient(
                                    gradient: Gradient(colors: [.clear, .blue.opacity(0.8), .clear]),
                                    startPoint: .top,
                                    endPoint: .bottom
                                )
                            )
                            .frame(width: 240, height: 8)
                            .offset(y: scanOffset)
                            .blendMode(.screen) // 讓藍光具備強烈的螢光發光質感
                    }
                }
                
                // 下方中英文標題文字漸顯
                VStack(spacing: 6) {
                    Text("PredictX Sports")
                        .font(.title2)
                        .bold()
                        .foregroundColor(.white)
                    
                    Text("智能球賽預測 APP")
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundColor(.gray)
                        .tracking(4) // 增加字距營造高級感
                }
                .opacity(isLogoVisible ? 0.9 : 0.0)
                .offset(y: isLogoVisible ? 0 : 20)
                
                Spacer()
                
                // 底部極簡加載提示
                ProgressView()
                    .progressViewStyle(CircularProgressViewStyle(tint: .blue))
                    .scaleEffect(1.2)
                    .opacity(isLogoVisible ? 1.0 : 0.0)
                    .padding(.bottom, 40)
            }
        }
        .onAppear {
            startLaunchSequence()
        }
    }
    
    // MARK: - 核心動畫序列排程
    private func startLaunchSequence() {
        // 1. 開機 0.3 秒後，啟動 Logo 粒子化浮現 (帶有流暢彈性)
        withAnimation(.interpolatingSpring(stiffness: 40, damping: 10).delay(0.3)) {
            isLogoVisible = true
        }
        
        // 2. 開機 1.5 秒後， Logo 浮現完畢，立刻召喚 AI 藍光掃描線
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
            isLineScanning = true
            // 讓掃描線由上至下平滑橫掃
            withAnimation(.easeInOut(duration: 1.2)) {
                scanOffset = 120
            }
        }
        
        // 3. 開機 3.0 秒後，動畫完美閉幕，切換進入首頁 UI
        DispatchQueue.main.asyncAfter(deadline: .now() + 3.0) {
            withAnimation(.easeOut(duration: 0.5)) {
                isAnimationCompleted = true
            }
            // 觸發外部回傳，通知 App 切換 View
            onFinished()
        }
    }
}
