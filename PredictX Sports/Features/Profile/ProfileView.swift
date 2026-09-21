
import SwiftUI
import Combine

// MARK: - 個人資訊主頁
struct ProfileView: View {
    @EnvironmentObject var favoritesStore: FavoritesStore
    @EnvironmentObject var subscriptionManager: SubscriptionManager
    @EnvironmentObject var themeManager: ThemeManager
    @StateObject private var pushManager = PushServiceManager.shared
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    
                    // MARK: ① 會員卡
                    MembershipCardView(subscriptionManager: subscriptionManager)
                    
                    // MARK: ② 訂閱中心
                    NavigationLink {
                        SubscribeView()
                    } label: {
                        ProfileMenuRow(
                            icon: "crown.fill",
                            iconColor: .yellow,
                            title: "訂閱中心",
                            subtitle: "管理您的 Premium 訂閱方案"
                        )
                    }
                    
                    // MARK: ⑥ AI 推論分析收藏
                    NavigationLink {
                        if subscriptionManager.canUseFavorites() {
                            FavoritesListView()
                                .environmentObject(favoritesStore)
                        } else {
                            Text("升級 Basic 以上方案\n即可使用收藏功能")
                                .font(.headline)
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.center)
                                .navigationTitle("推論收藏")
                        }
                    } label: {
                        ProfileMenuRow(
                            icon: "star.fill",
                            iconColor: .purple,
                            title: "AI 推論分析收藏",
                            subtitle: subscriptionManager.canUseFavorites()
                                ? "\(favoritesStore.favorites.count) 筆收藏"
                                : "升級後解鎖"
                        )
                    }
                    
                    // MARK: ⑦ 推播通知開關（僅 Premium 用戶可見）
                    if subscriptionManager.tier == .premium {
                        PushNotificationToggleRow(pushManager: pushManager)
                    }

                    // MARK: ⑧ 客服中心
                    NavigationLink {
                        SupportCenterView()
                    } label: {
                        ProfileMenuRow(
                            icon: "headphones",
                            iconColor: .green,
                            title: "客服中心",
                            subtitle: "常見問題、意見回饋、聯絡客服"
                        )
                    }
                    
                    // MARK: ⑧ 恢復購買
                    Button(action: {
                        Task { await subscriptionManager.restorePurchases() }
                    }) {
                        ProfileMenuRow(
                            icon: "arrow.uturn.backward.circle.fill",
                            iconColor: .blue,
                            title: "恢復購買",
                            subtitle: "恢復您之前的訂閱或購買項目"
                        )
                    }
                    .buttonStyle(.plain)
                    
                    // MARK: ⑨ 法律聲明
                    NavigationLink {
                        LegalDisclaimerView()
                    } label: {
                        ProfileMenuRow(
                            icon: "doc.text.fill",
                            iconColor: .gray,
                            title: "法律聲明",
                            subtitle: "數據來源與研究性質聲明"
                        )
                    }
                    
                    // MARK: ⑩ APP 版本資訊
                    ProfileMenuRow(
                        icon: "info.circle.fill",
                        iconColor: .gray,
                        title: "APP 版本資訊",
                        subtitle: "v1.2.1"
                    )
                    .disabled(true)

                    // 🆕 [2026-06-23] 開發者測試面板已移除（明晚 Archive 上架前）
                    // 原本用 #if DEBUG 守衛，但有 archive 設定錯誤時被編譯入 IPA 的風險
                    // 從 git history 仍可找回：git log --all --oneline -- "PredictX Sports/Features/Profile/ProfileView.swift"
                    // 開發測試可在 Xcode console 用：defaults write com.predictxsports.app membership_tier -string "Premium"

                }
                .padding()
            }
            .background(SportsDarkBackground())
            .navigationTitle("個人資訊")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: {
                        themeManager.isDarkMode.toggle()
                    }) {
                        Image(systemName: themeManager.isDarkMode ? "sun.max.fill" : "moon.fill")
                            .font(.body)
                            .foregroundColor(themeManager.isDarkMode ? .yellow : .blue)
                    }
                }
            }
            .sheet(isPresented: $subscriptionManager.showSubscribeView) {
                SubscribeView()
            }
            .alert("AI 分析點數說明", isPresented: $subscriptionManager.showDiamondsInfo) {
                Button("了解", role: .cancel) { }
                Button("升級方案") { subscriptionManager.showSubscribeView = true }
            } message: {
                Text("分析點數可用於解鎖 Basic 方案的 AI 詳細分析。升級 Standard 或 Premium 方案即可享有無限分析額度。")
            }
        }
    }
}

// MARK: - 會員卡元件
struct MembershipCardView: View {
    @ObservedObject var subscriptionManager: SubscriptionManager
    
    private var cardGradient: LinearGradient {
        switch subscriptionManager.tier {
        case .premium:
            return LinearGradient(
                colors: [Color(red: 0.85, green: 0.65, blue: 0.0),
                         Color(red: 0.95, green: 0.75, blue: 0.1),
                         Color(red: 0.9, green: 0.7, blue: 0.05)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        case .standard:
            return LinearGradient(
                colors: [Color(red: 0.2, green: 0.4, blue: 0.8),
                         Color(red: 0.3, green: 0.5, blue: 0.9)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        case .basic:
            return LinearGradient(
                colors: [Color(red: 0.3, green: 0.7, blue: 0.3),
                         Color(red: 0.4, green: 0.8, blue: 0.4)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        case .free:
            return LinearGradient(
                colors: [Color(red: 0.25, green: 0.25, blue: 0.30),
                         Color(red: 0.35, green: 0.35, blue: 0.42)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        }
    }
    
    var body: some View {
        VStack(spacing: 0) {
            HStack {
                VStack(alignment: .leading, spacing: 8) {
                    HStack(spacing: 8) {
                        Image(systemName: iconForTier)
                            .font(.title3)
                            .foregroundColor(.white)
                        Text(subscriptionManager.tier.rawValue)
                            .font(.title3)
                            .fontWeight(.bold)
                            .foregroundColor(.white)
                    }
                    
                    Text(subtitleText)
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.8))
                    
                    // Free 試用期間顯示每日補滿說明
                    if subscriptionManager.tier == .free && !subscriptionManager.trialExpired {
                        Text("每日 AI 分析點數補滿 60 點")
                            .font(.caption2)
                            .foregroundColor(.white.opacity(0.7))
                    }
                }
                
                Spacer()
                
                VStack(spacing: 4) {
                    Image(systemName: "cpu.fill")
                        .font(.title2)
                        .foregroundColor(.white)
                    Text(diamondDisplay)
                        .font(.title2)
                        .fontWeight(.heavy)
                        .foregroundColor(.white)
                    Text("分析點數")
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.8))
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
                .background(Color.white.opacity(0.15))
                .cornerRadius(16)
            }
            .padding()
        }
        .background(cardGradient)
        .cornerRadius(16)
        .shadow(color: shadowColor.opacity(0.3), radius: 12, x: 0, y: 6)
    }
    
    private var iconForTier: String {
        switch subscriptionManager.tier {
        case .premium: return "crown.fill"
        case .standard: return "star.fill"
        case .basic: return "leaf.fill"
        case .free: return "person.fill"
        }
    }
    
    private var subtitleText: String {
        switch subscriptionManager.tier {
        case .free:
            if subscriptionManager.trialExpired {
                return "試用已過期・請升級方案"
            }
            return "試用期剩餘 \(subscriptionManager.trialDaysRemaining) 天"
        case .basic, .standard, .premium:
            return "月費訂閱中・已解鎖所有權限"
        }
    }
    
    private var diamondDisplay: String {
        switch subscriptionManager.tier {
        case .free, .basic:
            return "\(subscriptionManager.diamonds)"
        case .standard, .premium:
            return "∞"
        }
    }
    
    private var shadowColor: Color {
        switch subscriptionManager.tier {
        case .premium: return .yellow
        case .standard: return .blue
        case .basic: return .green
        case .free: return .gray
        }
    }
}

// MARK: - 選單列元件
struct ProfileMenuRow: View {
    let icon: String
    let iconColor: Color
    let title: String
    let subtitle: String
    
    var body: some View {
        HStack(spacing: 16) {
            ZStack {
                RoundedRectangle(cornerRadius: 12)
                    .fill(iconColor.opacity(0.15))
                    .frame(width: 44, height: 44)
                Image(systemName: icon)
                    .font(.body)
                    .foregroundColor(iconColor)
            }
            
            VStack(alignment: .leading, spacing: 3) {
                Text(title)
                    .font(.body)
                    .fontWeight(.semibold)
                    .foregroundColor(.primary)
                Text(subtitle)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            Image(systemName: "chevron.right")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(16)
        .shadow(color: Color.black.opacity(0.1), radius: 6, x: 0, y: 3)
    }
}

#Preview {
    ProfileView()
}

// MARK: - 🆕 推播通知開關 Row（僅 Premium 用戶可見）
struct PushNotificationToggleRow: View {
    @ObservedObject var pushManager: PushServiceManager

    var body: some View {
        HStack(spacing: 12) {
            ZStack {
                Circle()
                    .fill(pushManager.isPushEnabled ? Color.orange.opacity(0.15) : Color.gray.opacity(0.15))
                    .frame(width: 36, height: 36)
                Image(systemName: pushManager.isPushEnabled ? "bell.badge.fill" : "bell.slash")
                    .font(.system(size: 16, weight: .bold))
                    .foregroundColor(pushManager.isPushEnabled ? .orange : .secondary)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text("推播通知")
                    .font(.body)
                    .fontWeight(.medium)
                    .foregroundColor(.primary)
                Text(statusText)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()

            Toggle("", isOn: Binding(
                get: { pushManager.isPushEnabled },
                set: { newValue in
                    Task { await pushManager.setPushEnabled(newValue) }
                }
            ))
            .labelsHidden()
            .tint(.orange)
        }
        .padding(.vertical, 8)
    }

    private var statusText: String {
        if pushManager.isPushEnabled {
            return "AI 信心度 ≥ 8 的賽事即時通知"
        }
        return "開啟後接收高信心度賽事推播"
    }
}
