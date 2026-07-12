import SwiftUI
import UIKit
import AppTrackingTransparency

/// 觀看廣告前的「自訂追蹤同意預告」畫面
/// 顯示友善的綠色圖示與自訂文字，使用者按「同意並觀看」後
/// 才會真的觸發 iOS 系統的 ATT 同意框
struct AdConsentView: View {
    @ObservedObject var subscriptionManager: SubscriptionManager
    @Binding var isPresented: Bool

    var body: some View {
        ZStack {
            // 背景：柔和綠色漸層
            LinearGradient(
                colors: [
                    Color(red: 0.05, green: 0.20, blue: 0.12),
                    Color(red: 0.02, green: 0.10, blue: 0.08)
                ],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()

            VStack(spacing: 24) {
                Spacer()

                // 綠色圖示
                ZStack {
                    Circle()
                        .fill(Color.green.opacity(0.15))
                        .frame(width: 120, height: 120)

                    Image(systemName: "leaf.fill")
                        .font(.system(size: 56, weight: .semibold))
                        .foregroundColor(.green)
                        .shadow(color: .green.opacity(0.5), radius: 12)
                }

                // 標題
                Text("支援開發・解鎖個人化內容")
                    .font(.title2.bold())
                    .foregroundColor(.white)
                    .multilineTextAlignment(.center)

                // 自訂文字
                VStack(spacing: 12) {
                    Text("允許追蹤可協助我們提供個人化廣告內容，並支持 App 持續開發。")
                        .font(.body)
                        .foregroundColor(.white.opacity(0.9))
                        .multilineTextAlignment(.center)
                        .lineSpacing(4)
                        .padding(.horizontal, 24)

                    Text("您可隨時在 iOS 設定 → 隱私權與安全性 → 追蹤中關閉。")
                        .font(.footnote)
                        .foregroundColor(.white.opacity(0.6))
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 24)
                }

                Spacer()

                // 主要按鈕：同意並觀看 → 觸發系統 ATT
                Button(action: {
                    requestATTAndPlayAd()
                }) {
                    HStack(spacing: 8) {
                        Image(systemName: "checkmark.shield.fill")
                        Text("同意並觀看廣告")
                            .fontWeight(.semibold)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
                    .background(
                        LinearGradient(
                            colors: [.green, .green.opacity(0.8)],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .foregroundColor(.white)
                    .cornerRadius(14)
                    .shadow(color: .green.opacity(0.4), radius: 8, x: 0, y: 4)
                }
                .padding(.horizontal, 24)

                // 次要按鈕：跳過
                Button(action: {
                    isPresented = false
                }) {
                    Text("稍後再說")
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.7))
                        .padding(.vertical, 12)
                }
                .padding(.bottom, 24)
            }
        }
    }

    /// 點擊「同意並觀看」時：呼叫系統 ATT 同意框
    private func requestATTAndPlayAd() {
        if #available(iOS 14, *) {
            // 🆕 [2026-06-29] 先檢查目前 ATT 狀態
            let currentStatus = ATTrackingManager.trackingAuthorizationStatus
            #if DEBUG
            print("🔍 [ATT] 目前狀態: \(currentStatus.rawValue)")
            #endif

            switch currentStatus {
            case .notDetermined:
                // 尚未決定 → 呼叫系統 ATT 同意框
                #if DEBUG
                print("🔍 [ATT] 尚未決定，呼叫系統同意框")
                #endif
                ATTrackingManager.requestTrackingAuthorization { _ in
                    DispatchQueue.main.async {
                        self.playAd()
                    }
                }
            case .authorized, .denied, .restricted:
                // 已經決定過 → 不再彈同意框，直接播放廣告
                #if DEBUG
                print("🔍 [ATT] 已決定（狀態: \(currentStatus.rawValue)），跳過同意框")
                #endif
                playAd()
            @unknown default:
                playAd()
            }
        } else {
            // iOS 14 以下：直接播放廣告
            playAd()
        }
    }

    /// 關閉自己，然後透過 Notification 觸發 AdRewardCardView 開啟廣告 sheet
    private func playAd() {
        isPresented = false

        // 延遲一下讓子彈窗關閉後再開廣告 sheet
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
            NotificationCenter.default.post(name: .playRewardedAd, object: nil)
        }
    }
}

// MARK: - 通知名稱

extension Notification.Name {
    static let playRewardedAd = Notification.Name("playRewardedAd")
}