import SwiftUI
import StoreKit

// MARK: - 訂閱 Paywall 主頁（卡片式舊版介面）
/// 點 ProfileView「升級 Premium」或「訂閱中心」後彈出
struct SubscribeView: View {
    @EnvironmentObject var subscriptionManager: SubscriptionManager
    @Environment(\.dismiss) private var dismiss
    @State private var selectedTier: ProductTier = .standard
    @State private var isAnnual: Bool = false
    @State private var products: [StoreKit.Product] = []
    @State private var loadError: String? = nil

    // 月付／年付方案差價（年訂約等於 8 折）
    private let annualDiscount: Double = 0.2

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
                        tierSelection
                        if !isAnnual {
                            Text("切換年訂可享約 83 折優惠・每年最高省 NT$ \(annuallySavedForSelectedTier())")
                                .font(.callout)
                                .foregroundColor(Color(.tertiaryLabel))
                                .multilineTextAlignment(.center)
                        }
                        paywallButton
                        paywallLoadError()
                        featuresChart
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
                        .font(.body)
                }
            }
            .toolbarBackground(Color(red: 0.06, green: 0.08, blue: 0.18), for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .task {
                await loadProducts()
            }
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
                .font(.callout)
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
        .font(.system(size: 12, weight: .medium))
        .foregroundColor(.secondary)
        .padding(.vertical, 12)
        .padding(.horizontal, 12)
        .background(Color(.systemGray6))
        .clipShape(Capsule())
    }

    // MARK: - 方案選擇

    private var tierSelection: some View {
        VStack(spacing: 12) {
            HStack(spacing: 0) {
                billingToggle(title: "月訂", isSelected: !isAnnual) {
                    isAnnual = false
                }
                billingToggle(title: "年訂・約 83 折", isSelected: isAnnual) {
                    isAnnual = true
                }
            }
            .frame(maxWidth: .infinity)
            .padding(4)
            .background(Color(.systemGray6).opacity(0.5))
            .clipShape(RoundedRectangle(cornerRadius: 14))
            .padding(.bottom, 4)

            ForEach(ProductTier.allCases, id: \.self) { tier in
                TierCard(
                    tier: tier,
                    isSelected: selectedTier == tier,
                    isAnnual: isAnnual,
                    annualDiscount: annualDiscount
                )
                .onTapGesture {
                    withAnimation(.spring(response: 0.35, dampingFraction: 0.7)) {
                        selectedTier = tier
                    }
                }
            }
        }
    }

    private func billingToggle(title: String, isSelected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.callout.bold())
                .padding(.vertical, 10)
                .frame(maxWidth: .infinity)
                .foregroundColor(isSelected ? .white : .white.opacity(0.5))
                .background(isSelected ? Color.blue : Color.clear)
                .clipShape(RoundedRectangle(cornerRadius: 10))
        }
    }

    // MARK: - 付費按鈕

    private var paywallButton: some View {
        Button(action: { Task { await purchase() } }) {
            HStack {
                if subscriptionManager.isProcessing {
                    ProgressView().tint(.white)
                } else {
                    Image(systemName: "crown.fill")
                    Text(priceStringForPaywall())
                        .font(.title3.bold())
                    if isAnnual {
                        Text("/ 年")
                            .font(.headline)
                            .opacity(0.85)
                    } else {
                        Text("/ 月")
                            .font(.headline)
                            .opacity(0.85)
                    }
                }
            }
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 18)
            .background(
                LinearGradient(colors: [.blue, .purple],
                               startPoint: .leading, endPoint: .trailing)
            )
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .shadow(color: .blue.opacity(0.4), radius: 12, x: 0, y: 6)
        }
        .disabled(subscriptionManager.isProcessing || products.isEmpty)
        .opacity(subscriptionManager.isProcessing ? 0.7 : 1.0)
    }

    @ViewBuilder
    private func paywallLoadError() -> some View {
        if let err = loadError {
            Text(err)
                .font(.caption2)
                .foregroundColor(.orange)
                .multilineTextAlignment(.center)
        }
    }

    private func priceStringForPaywall() -> String {
        if isAnnual {
            return "NT$ \(selectedTier.yearlyPriceTWD)"
        } else {
            return "NT$ \(selectedTier.monthlyPriceTWD)"
        }
    }

    // MARK: - 方案功能對照表

    private var featuresChart: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label(NSLocalizedString("subscribe.features.title", comment: "方案功能對照"), systemImage: "list.bullet.rectangle")
                .font(.headline.bold())
                .foregroundColor(.white)

            VStack(spacing: 0) {
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
        VStack(spacing: 12) {
            // 隱私政策與使用條款卡片
            HStack(spacing: 12) {
                Link(destination: privacyPolicyURL) {
                    LegalLinkCard(
                        icon: "lock.shield.fill",
                        iconColor: .blue,
                        title: "隱私政策",
                        subtitle: "個資蒐集與使用"
                    )
                }
                
                Link(destination: URL(string: "https://www.apple.com/legal/internet-services/itunes/dev/stdeula/")!) {
                    LegalLinkCard(
                        icon: "doc.text.fill",
                        iconColor: .purple,
                        title: "使用條款",
                        subtitle: "Apple 標準 EULA"
                    )
                }
            }
            
            // 新手贈禮說明
            Text(NSLocalizedString("gift.info", comment: "新手登入即享 30 天贈禮：每天補充 60 分析點數。30 天後如未訂閱，仍可透過觀看廣告獲得額外點數。"))
                .font(.footnote)
                .foregroundColor(Color(.tertiaryLabel))
                .multilineTextAlignment(.center)

            Text(NSLocalizedString("legal.auto_renew", comment: "• 訂閱會自動續訂・可在 iPhone「設定」>「Apple ID」>「訂閱項目」中隨時取消"))
                .font(.footnote)
                .foregroundColor(Color(.tertiaryLabel))
                .multilineTextAlignment(.center)

            Text(NSLocalizedString("legal.disclaimer", comment: "• PredictX Sports 為運動數據分析工具・所有 AI 推論結果僅供參考・不構成任何投注建議"))
                .font(.footnote)
                .foregroundColor(Color(.tertiaryLabel))
                .multilineTextAlignment(.center)
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
            .font(.callout.bold())
            .foregroundColor(.blue)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(Color.blue.opacity(0.12))
            .clipShape(RoundedRectangle(cornerRadius: 10))
        }
    }

    // MARK: - StoreKit

    private func loadProducts() async {
        loadError = nil
        do {
            let ids = ProductTier.allCases.flatMap { $0.allProductIDs }
            let fetched = try await Product.products(for: ids)
            self.products = fetched
            if fetched.isEmpty {
                loadError = "尚未設定訂閱方案。請聯絡客服或稍後再試。"
            }
        } catch {
            loadError = "載入方案失敗：\(error.localizedDescription)"
        }
    }

    private func purchase() async {
        let id = selectedTier.productID(isAnnual: isAnnual)
        await subscriptionManager.purchase(id)
        if subscriptionManager.lastPurchaseSucceeded {
            try? await Task.sleep(nanoseconds: 600_000_000)
            dismiss()
        }
    }

    private func annuallySavedForSelectedTier() -> Int {
        let monthly = selectedTier.monthlyPriceTWD
        let annualTotal = monthly * 12
        return annualTotal - selectedTier.yearlyPriceTWD
    }
}

// MARK: - 方案卡片

private struct TierCard: View {
    let tier: ProductTier
    let isSelected: Bool
    let isAnnual: Bool
    let annualDiscount: Double

    var body: some View {
        HStack(spacing: 14) {
            ZStack {
                Circle()
                    .fill(tier.tint.opacity(0.18))
                    .frame(width: 52, height: 52)
                Image(systemName: tier.icon)
                    .font(.title2)
                    .foregroundColor(tier.tint)
            }

            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 6) {
                    Text(tier.displayName)
                        .font(.title3.bold())
                        .foregroundColor(.white)
                    if tier == .standard {
                        Text("推薦")
                            .font(.system(size: 11, weight: .black))
                            .foregroundColor(.white)
                            .padding(.horizontal, 8).padding(.vertical, 2)
                            .background(Color.orange)
                            .clipShape(Capsule())
                    }
                    if tier == .premium {
                        Text("最高性價比")
                            .font(.system(size: 11, weight: .black))
                            .foregroundColor(.white)
                            .padding(.horizontal, 8).padding(.vertical, 2)
                            .background(Color.purple)
                            .clipShape(Capsule())
                    }
                }

                Text(tier.tagline)
                    .font(.callout)
                    .foregroundColor(.secondary)

                Text(displayPrice)
                    .font(.headline.bold())
                    .foregroundColor(tier.tint)
            }

            Spacer()

            VStack {
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(.title2)
                    .foregroundColor(isSelected ? tier.tint : .white.opacity(0.3))
                Spacer()
                Text(unitLabel)
                    .font(.caption2)
                    .foregroundColor(Color(.tertiaryLabel))
            }
        }
        .padding(16)
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(Color.cardBackground)
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(isSelected ? tier.tint : Color.clear, lineWidth: 2)
                )
        )
        .shadow(color: tier.tint.opacity(isSelected ? 0.25 : 0), radius: 10, x: 0, y: 4)
    }

    private var unitLabel: String { isAnnual ? "年" : "月" }

    private var displayPrice: String {
        if isAnnual {
            return "NT$ \(tier.yearlyPriceTWD) / 年"
        } else {
            return "NT$ \(tier.monthlyPriceTWD) / 月"
        }
    }
}

/// 方案名稱標題列用
private func headerCell(text: String, color: Color) -> some View {
    Text(text)
        .font(.callout.bold())
        .foregroundColor(color)
        .frame(width: 56)
}

// MARK: - 法律連結卡片

private struct LegalLinkCard: View {
    let icon: String
    let iconColor: Color
    let title: String
    let subtitle: String
    
    var body: some View {
        HStack(spacing: 10) {
            ZStack {
                RoundedRectangle(cornerRadius: 10)
                    .fill(iconColor.opacity(0.15))
                    .frame(width: 40, height: 40)
                Image(systemName: icon)
                    .font(.body)
                    .foregroundColor(iconColor)
            }
            
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.callout.bold())
                    .foregroundColor(.primary)
                Text(subtitle)
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            Image(systemName: "arrow.up.right.square")
                .font(.callout)
                .foregroundColor(iconColor)
        }
        .padding(12)
        .frame(maxWidth: .infinity)
        .background(Color(.secondarySystemBackground).opacity(0.6))
        .clipShape(RoundedRectangle(cornerRadius: 12))
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
                .font(.callout)
                .foregroundColor(.primary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .layoutPriority(1)

            cell(text: free, color: .gray.opacity(0.5))
            cell(text: basic, color: .green.opacity(0.7))
            cell(text: standard, color: .blue)
            cell(text: premium, color: .purple)
        }
        .padding(.vertical, 10).padding(.horizontal, 4)
    }

    private func cell(text: String, color: Color) -> some View {
        Text(text)
            .font(.callout.bold())
            .foregroundColor(text == "—" ? .white.opacity(0.3) : .white)
            .frame(width: 56)
            .padding(.vertical, 6)
            .background(color.opacity(0.15))
            .clipShape(RoundedRectangle(cornerRadius: 6))
    }
}

// MARK: - Product Tier 定義

enum ProductTier: CaseIterable {
    case basic
    case standard
    case premium

    var displayName: String {
        switch self {
        case .basic: return "Basic"
        case .standard: return "Standard"
        case .premium: return "Premium"
        }
    }

    var tagline: String {
        switch self {
        case .basic: return "每日 120 分析點數（可累積・無上限）"
        case .standard: return "無限點數・含驗證率儀表板"
        case .premium: return "無限 + 推播通知"
        }
    }

    var icon: String {
        switch self {
        case .basic: return "leaf.fill"
        case .standard: return "star.fill"
        case .premium: return "crown.fill"
        }
    }

    var tint: Color {
        switch self {
        case .basic: return .green
        case .standard: return .blue
        case .premium: return .purple
        }
    }

    var monthlyPriceTWD: Int {
        switch self {
        case .basic: return 100
        case .standard: return 290
        case .premium: return 390
        }
    }

    var yearlyPriceTWD: Int {
        switch self {
        case .basic: return 990
        case .standard: return 2990
        case .premium: return 3850
        }
    }

    func productID(isAnnual: Bool) -> String {
        let suffix = isAnnual ? "yearly" : "monthly"
        return "com.predictxsports.\(rawValue).\(suffix)"
    }

    var allProductIDs: [String] {
        [productID(isAnnual: false), productID(isAnnual: true)]
    }

    private var rawValue: String {
        switch self {
        case .basic: return "basic"
        case .standard: return "standard"
        case .premium: return "premium"
        }
    }

    func fallbackPrice(isAnnual: Bool) -> String {
        if isAnnual {
            return "NT$ \(yearlyPriceTWD)"
        }
        return "NT$ \(monthlyPriceTWD) / 月"
    }
}

#Preview {
    SubscribeView()
        .environmentObject(SubscriptionManager())
}
