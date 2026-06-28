import SwiftUI
import StoreKit

// MARK: - 訂閱 Paywall 主頁（使用 Apple SubscriptionStoreView）
/// 點 ProfileView「升級 Premium」或「訂閱中心」後彈出
/// 使用 Apple 官方 SubscriptionStoreView，自動包含所有必要資訊（Guideline 3.1.2(c) 合規）
struct SubscribeView: View {
    @EnvironmentObject var subscriptionManager: SubscriptionManager
    @Environment(\.dismiss) private var dismiss
    
    // 隱私權政策網址
    private let privacyPolicyURL = URL(string: "https://k06210621-dot.github.io/privacy/")!
    
    var body: some View {
        NavigationStack {
            ZStack {
                SportsDarkBackground()
                
                ScrollView {
                    VStack(spacing: 24) {
                        header
                        legalShield
                        
                        // Apple 官方 SubscriptionStoreView
                        // 自動包含：方案名稱、訂閱長度、價格、隱私權政策連結、服務條款連結
                        subscriptionStoreView
                        
                        // 方案功能對照表
                        featuresChart
                        
                        // 補充說明（在 SubscriptionStoreView 下方）
                        additionalInfo
                        
                        restoreButton
                    }
                    .padding(.horizontal, 20)
                    .padding(.bottom, 40)
                }
            }
            .navigationTitle(NSLocalizedString("subscribe.title", comment: "AI 額度儲值中心"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(NSLocalizedString("nav.close", comment: "關閉")) { dismiss() }
                        .foregroundColor(.primary)
                }
            }
            .toolbarBackground(Color(red: 0.06, green: 0.08, blue: 0.18), for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
    }
    
    // MARK: - Header
    
    private var header: some View {
        VStack(spacing: 10) {
            Image(systemName: "crown.fill")
                .font(.system(size: 56))
                .foregroundStyle(LinearGradient(colors: [.yellow, .orange],
                                                startPoint: .topLeading, endPoint: .bottomTrailing))
                .shadow(color: .yellow.opacity(0.4), radius: 12)
            
            Text("解鎖完整 AI 分析引擎")
                .font(.title2)
                .fontWeight(.heavy)
                .foregroundColor(.white)
                .multilineTextAlignment(.center)
            
            Text("四大運動聯盟 50+ 項特徵因子・即時推論・模型驗證率公開透明")
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 12)
        }
        .padding(.top, 20)
    }
    
    // MARK: - 法律保證列
    
    private var legalShield: some View {
        HStack(spacing: 8) {
            Label("新手登入贈禮：30 天・每天 60 點", systemImage: "gift.fill")
            Divider().frame(height: 14).background(Color(.separator))
            Label("隨時升級", systemImage: "star.fill")
            Divider().frame(height: 14).background(Color(.separator))
            Label("App Store 安全交易", systemImage: "lock.shield.fill")
        }
        .font(.system(size: 10, weight: .medium))
        .foregroundColor(.secondary)
        .padding(.vertical, 12)
        .padding(.horizontal, 12)
        .background(Color(.systemGray6))
        .clipShape(Capsule())
    }
    
    // MARK: - Apple SubscriptionStoreView
    
    @ViewBuilder
    private var subscriptionStoreView: some View {
        if #available(iOS 17.0, *) {
            // iOS 17+ 使用標準 SubscriptionStoreView
            // 自動包含所有 Guideline 3.1.2(c) 要求的資訊：
            // - 訂閱方案名稱
            // - 訂閱長度（月/年）
            // - 價格
            // - 隱私權政策連結
            // - 服務條款連結（Apple 標準 EULA）
            SubscriptionStoreView(productIDs: subscriptionManager.allProductIDs)
                .frame(height: 400)
                .cornerRadius(12)
        } else {
            // iOS 16 fallback（舊版使用者極少）
            legacySubscriptionView
        }
    }
    
    // MARK: - iOS 16 Fallback（簡化版）
    
    @ViewBuilder
    private var legacySubscriptionView: some View {
        VStack(spacing: 16) {
            Text("您的 iOS 版本較舊，請在 iPhone 設定中管理訂閱")
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
            
            Text("或使用其他裝置（iOS 17+）查看完整訂閱方案")
                .font(.caption2)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
            
            // 隱私權政策連結（iOS 16 也需要）
            Link("隱私權政策", destination: privacyPolicyURL)
                .font(.caption)
                .foregroundColor(.blue)
        }
        .padding()
        .background(Color.black.opacity(0.2))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
    
    // MARK: - 方案功能對照表
    
    private var featuresChart: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label(NSLocalizedString("subscribe.features.title", comment: "方案功能對照"), systemImage: "list.bullet.rectangle")
                .font(.headline.bold())
                .foregroundColor(.white)
            
            VStack(spacing: 0) {
                // 方案名稱標題列
                HStack(spacing: 8) {
                    Text("")
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .layoutPriority(1)
                    headerCell(text: "Free", color: .gray)
                    headerCell(text: "Basic", color: .green)
                    headerCell(text: "Standard", color: .blue)
                    headerCell(text: "Premium", color: .purple)
                }
                .padding(.vertical, 6).padding(.horizontal, 4)
                
                Divider().background(Color(.separator))
                FeatureRow(label: NSLocalizedString("feature.daily_points", comment: "每日 AI 分析點數"),
                           free: NSLocalizedString("feature.free.60pts", comment: "60 點"),
                           basic: NSLocalizedString("feature.basic.120pts", comment: "120 點"),
                           standard: NSLocalizedString("feature.unlimited", comment: "無限"),
                           premium: NSLocalizedString("feature.unlimited", comment: "無限"))
                Divider().background(Color(.separator))
                FeatureRow(label: NSLocalizedString("feature.history", comment: "歷史賽事比分與分析對照"),
                           free: "✓", basic: "✓", standard: "✓", premium: "✓")
                Divider().background(Color(.separator))
                FeatureRow(label: NSLocalizedString("feature.favorites", comment: "收藏賽事分析"),
                           free: "—", basic: "✓", standard: "✓", premium: "✓")
                Divider().background(Color(.separator))
                FeatureRow(label: NSLocalizedString("feature.watch_ads", comment: "觀看廣告 (每日上限三則)"),
                           free: "20 點", basic: "20 點", standard: "—", premium: "—")
                Divider().background(Color(.separator))
                FeatureRow(label: NSLocalizedString("feature.dashboard", comment: "模型驗證率儀表板"),
                           free: "—", basic: "—", standard: "✓", premium: "✓")
                Divider().background(Color(.separator))
                FeatureRow(label: NSLocalizedString("feature.push", comment: "推播通知"),
                           free: "—", basic: "—", standard: "—", premium: "✓")
            }
            .padding(8)
            .background(Color.black.opacity(0.2))
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
    }
    
    // MARK: - 補充說明
    
    private var additionalInfo: some View {
        VStack(spacing: 6) {
            // 新手贈禮說明
            Text(NSLocalizedString("gift.info", comment: "新手登入即享 30 天贈禮：每天補充 60 分析點數。30 天後如未訂閱，仍可透過觀看廣告獲得額外點數。"))
                .font(.caption2)
                .foregroundColor(Color(.tertiaryLabel))
                .multilineTextAlignment(.center)
            
            Text(NSLocalizedString("legal.auto_renew", comment: "• 訂閱會自動續訂・可在 iPhone「設定」>「Apple ID」>「訂閱項目」中隨時取消"))
                .font(.caption2)
                .foregroundColor(Color(.tertiaryLabel))
                .multilineTextAlignment(.center)
            
            Text(NSLocalizedString("legal.disclaimer", comment: "• PredictX Sports 為運動數據分析工具・所有 AI 推論結果僅供參考・不構成任何投注建議"))
                .font(.caption2)
                .foregroundColor(Color(.tertiaryLabel))
                .multilineTextAlignment(.center)
            
            // 隱私權政策連結（iOS 16 也需要）
            if #available(iOS 17.0, *) {
                // 已在 SubscriptionStoreView 中自動處理
            } else {
                Divider()
                Link("隱私政策", destination: privacyPolicyURL)
                    .font(.caption)
                    .foregroundColor(.blue)
            }
        }
        .padding(.top, 8)
    }
    
    // MARK: - 恢復購買
    
    private var restoreButton: some View {
        Button(action: { Task { await subscriptionManager.restorePurchases() } }) {
            HStack {
                Image(systemName: "arrow.clockwise")
                Text("恢復購買")
            }
            .font(.caption.bold())
            .foregroundColor(.blue)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
            .background(Color.blue.opacity(0.12))
            .clipShape(RoundedRectangle(cornerRadius: 10))
        }
    }
}

// MARK: - 功能對照表 row

private struct FeatureRow: View {
    let label: String
    let free: String
    let basic: String
    let standard: String
    let premium: String

    var body: some View {
        HStack(spacing: 8) {
            Text(label)
                .font(.caption)
                .foregroundColor(.primary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .layoutPriority(1)

            cell(text: free, color: .gray.opacity(0.5))
            cell(text: basic, color: .green.opacity(0.7))
            cell(text: standard, color: .blue)
            cell(text: premium, color: .purple)
        }
        .padding(.vertical, 8).padding(.horizontal, 4)
    }

    private func cell(text: String, color: Color) -> some View {
        Text(text)
            .font(.caption2.bold())
            .foregroundColor(text == "—" ? .white.opacity(0.3) : .white)
            .frame(width: 48)
            .padding(.vertical, 4)
            .background(color.opacity(0.15))
            .clipShape(RoundedRectangle(cornerRadius: 6))
    }
}

/// 方案名稱標題列用（字體較大、無背景）
private func headerCell(text: String, color: Color) -> some View {
    Text(text)
        .font(.caption.bold())
        .foregroundColor(color)
        .frame(width: 48)
}

#Preview {
    SubscribeView()
        .environmentObject(SubscriptionManager())
}