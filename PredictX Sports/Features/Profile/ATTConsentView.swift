import SwiftUI
import AppTrackingTransparency

/// 啟動後的 ATT 說明卡片
/// - 位置：LaunchView 動畫結束後、MainTabView 之前
/// - 觸發時機：每次 ATT 狀態為 notDetermined 時
/// - 「繼續」→ 觸發 iOS 系統 ATT 同意框（使用者可選同意或拒絕）
/// - 無退出按鈕：Apple 審查要求不得讓使用者跳過 ATT 請求
struct ATTConsentView: View {
    var onFinished: () -> Void

    var body: some View {
        ZStack {
            // 半透明黑色背景遮罩
            Color.black.opacity(0.4)
                .ignoresSafeArea()

            VStack(spacing: 20) {
                // 標題
                Text("廣告偏好設定")
                    .font(.title2.bold())
                    .foregroundColor(.primary)
                    .multilineTextAlignment(.center)

                // 內容
                Text("""
                PredictX Sports 與 Google AdMob 合作，透過此識別碼
                為您提供更相關的運動賽事廣告。
                您可隨時在 iOS 設定 → 隱私權與安全性 → 追蹤中調整。
                """)
                .font(.body)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 16)

                // 主要按鈕（中性用語）
                Button {
                    requestATT()
                } label: {
                    Text("繼續")
                        .fontWeight(.semibold)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                        .background(Color.blue)
                        .foregroundColor(.white)
                        .cornerRadius(12)
                }
                .padding(.horizontal, 16)

                // 次要按鈕已移除（Apple 審查要求 ATT 說明卡片不得有退出按鈕）
                // 使用者必須點擊「繼續」進入系統 ATT 彈窗
                // 系統 ATT 彈窗本身提供「要求 App 不要追蹤」選項
            }
            .padding(24)
            .background(
                RoundedRectangle(cornerRadius: 20)
                    .fill(Color(.systemBackground))
            )
            .padding(.horizontal, 32)
        }
    }

    private func requestATT() {
        if #available(iOS 14, *) {
            ATTrackingManager.requestTrackingAuthorization { _ in
                DispatchQueue.main.async {
                    onFinished()
                }
            }
        } else {
            // iOS 14 以下無 ATT，直接進入主畫面
            onFinished()
        }
    }
}
