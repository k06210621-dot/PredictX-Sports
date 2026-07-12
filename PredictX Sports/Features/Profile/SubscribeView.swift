import SwiftUI
import StoreKit

// MARK: - 訂閱 Paywall 主頁（Carousel 風格優化版）
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
                        billingToggle
                        tierCarousel
                        trialDisclosure
                        paywallButton
                        paywallLoadError()
                        featuresChart
                        additionalInfo
                        manageSubscriptionButton
                        restoreButton
                    }
                    .padding(.horizontal, 20)
                    .padding(.top, 8)
                    .padding(.bottom, 100)  // 預留底部空間避免被 Tab Bar 遮擋
                }
                .scrollIndicators(.hidden)
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

    // MARK: - 方案選擇 (Carousel 風格)
    private var tierCarousel: some View {
        VStack(spacing: 16) {
            // ⚠️ [2026-06-29] 統一門檻為 >= 8（與 iOS App ProfileView.swift:575 顯示文字及 push_service.CONFIDENCE_THRESHOLD 一致）。之前用 > 8 會漏推 confidence = 8 的賽事，造成 App 顯示「高信心度」但收不到通知的混淆。
            TabView(selection: $selectedTier) {
                ForEach(ProductTier.allCases, id: \.self) { tier in
                    TierCard(
                        tier: tier,
                        isSelected: selectedTier == tier,
                        isAnnual: isAnnual,
                        annualDiscount: annualDiscount
                    )
                    .padding(.horizontal, 20)
                    .frame(maxWidth: .infinity)
                    .tag(tier)
                    .disabled(tier == .free) // Free 方案不可選
                }
            }
            .tabViewStyle(.page(indexDisplayMode: .always))
            .frame(height: 280) // 固定高度
            .animation(.spring(), value: selectedTier)
        }
    }

    // MARK: - 月/年費切換器 (膠囊狀 Segmented Control)
    private var billingToggle: some View {
        Picker("", selection: $isAnnual) {
            Text("Monthly")
                .tag(false)
            Text("Yearly")
                .tag(true)
        }
        .pickerStyle(.segmented)
        .padding(.horizontal, 4)
    }

    // MARK: - 試用/取消說明 + 法律連結 (在購買按鈕上方)
    private var trialDisclosure: some View {
        VStack(spacing: 12) {
            Text("訂閱可隨時在「設定 > Apple ID > 訂閱」中取消")
                .font(.callout)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)

            // 法律連結 (符合 Apple Guideline 3.1.2c)
            VStack(spacing: 8) {
                Text("購買即代表您同意")
                    .font(.callout)
                    .foregroundColor(.secondary)

                HStack(spacing: 4) {
                    Link("《使用條款 (EULA)》", destination: URL(string: "https://www.apple.com/legal/internet-services/itunes/dev/stdeula/")!)
                    Text("與")
                        .foregroundColor(.secondary)
                    Link("《隱私權政策》", destination: privacyPolicyURL)
                }
                .font(.callout)
                .foregroundColor(.blue)
            }
        }
        .padding(.horizontal, 20)
        .padding(.bottom, 4)
    }

    private var paywallButton: some View {
        Button(action: { Task { await purchase() } }) {
            HStack(spacing: 8) {
                if subscriptionManager.isProcessing {
                    ProgressView().tint(.white)
                } else {
                    Image(systemName: "crown.fill")
                    VStack(spacing: 2) {
                        Text(buttonMainText)
                            .font(.title3.bold())
                        if !subscriptionManager.trialExpired {
                            Text(buttonSubText)
                                .font(.caption2)
                                .opacity(0.85)
                        }
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

    // MARK: - 按鈕文字
    private var buttonMainText: String {
        // 主文字：明確顯示訂購金額（讓使用者知道按下去會扣多少）
        let price = selectedTier.currentPriceTWD(isAnnual: isAnnual)
        let unit = isAnnual ? "/年" : "/月"
        return "NT$ \(price) \(unit)"
    }

    private var buttonSubText: String {
        // 副文字：點按鈕後的行為說明
        return "按下按鈕後將進入訂閱流程"
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

    // MARK: - 管理訂閱按鈕
    private var manageSubscriptionButton: some View {
        Button(action: {
            if let url = URL(string: "https://apps.apple.com/account/subscriptions") {
                UIApplication.shared.open(url)
            }
        }) {
            HStack {
                Image(systemName: "gear")
                Text("管理訂閱")
            }
            .font(.callout.bold())
            .foregroundColor(.blue)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(Color.blue.opacity(0.15))
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
        .padding(.horizontal, 20)
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
                FeatureRow(label: NSLocalizedString("feature.history", comment: "歷史賽事比分與分析"),
                           free: "✓", basic: "✓", standard: "✓", premium: "✓")
                Divider().background(Color(.separator))
                FeatureRow(label: NSLocalizedString("feature.favorites", comment: "收藏賽事分析"),
                           free: "—", basic: "✓", standard: "✓", premium: "✓")
                Divider().background(Color(.separator))
                FeatureRow(label: NSLocalizedString("feature.watch_ads", comment: "每日觀看廣告上限三則"),
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
        .padding(.horizontal, 20)
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
        ZStack(alignment: .topTrailing) {
            VStack(spacing: 0) {
                // MARK: - 上半部：圖示 + 標題 + 標籤
                HStack(alignment: .center, spacing: 14) {
                    ZStack {
                        Circle()
                            .fill(tier.tint.opacity(0.18))
                            .frame(width: 56, height: 56)
                        Image(systemName: tier.icon)
                            .font(.title2)
                            .foregroundColor(tier.tint)
                    }

                    VStack(alignment: .leading, spacing: 4) {
                        Text("PredictX Sports \(tier.displayName) \(isAnnual ? "年訂" : "月訂")")
                            .font(.title3.bold())
                            .foregroundColor(.white)
                            .lineLimit(nil)

                        Text(tier.tagline)
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .lineLimit(2)
                            .multilineTextAlignment(.leading)
                            .fixedSize(horizontal: false, vertical: true)
                    }

                    Spacer(minLength: 4)
                }
                .padding(.bottom, 12)

                Divider()
                    .background(Color.white.opacity(0.1))
                    .padding(.bottom, 10)

                // MARK: - 中間：價格
                HStack(alignment: .firstTextBaseline, spacing: 4) {
                    Text("NT$ \(tier.currentPriceTWD(isAnnual: isAnnual))")
                        .font(.system(size: 32, weight: .heavy))
                        .foregroundColor(tier.tint)
                    Text(isAnnual ? "/ 年" : "/ 月")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.bottom, 10)

                // MARK: - 下半部：權益清單
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(tier.benefits.prefix(5), id: \.self) { benefit in
                        HStack(alignment: .top, spacing: 6) {
                            Image(systemName: "checkmark.circle.fill")
                                .font(.system(size: 11))
                                .foregroundColor(tier.tint)
                                .padding(.top, 1)
                            Text(benefit)
                                .font(.caption)
                                .foregroundColor(.white.opacity(0.85))
                                .lineLimit(1)
                                .fixedSize(horizontal: false, vertical: true)
                            Spacer(minLength: 0)
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)

                Spacer(minLength: 0)
                }
                .padding(12)
                .background(
                RoundedRectangle(cornerRadius: 18)
                    .fill(Color.cardBackground)
                    .overlay(
                        RoundedRectangle(cornerRadius: 18)
                            .stroke(isSelected ? tier.tint : Color.white.opacity(0.05),
                                    lineWidth: isSelected ? 2 : 1)
                    )
            )
            .shadow(color: tier.tint.opacity(isSelected ? 0.35 : 0.08),
                    radius: isSelected ? 14 : 6, x: 0, y: 6)

            // MARK: - Best Offer 角標（浮在卡片右上角）
            if tier == .standard {
                HStack(spacing: 3) {
                    Image(systemName: "star.fill")
                        .font(.system(size: 9))
                    Text("Best Offer")
                        .font(.system(size: 10, weight: .heavy))
                }
                .foregroundColor(.white)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(
                    LinearGradient(
                        colors: [Color.orange, Color.red],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                )
                .clipShape(Capsule())
                .shadow(color: .orange.opacity(0.5), radius: 4, y: 2)
                .offset(x: -8, y: 8)
            }
        }
    }

    private var unitLabel: String { isAnnual ? "年" : "月" }
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
    case free
    case basic
    case standard
    case premium

    var displayName: String {
        switch self {
        case .free: return "Free"
        case .basic: return "Basic"
        case .standard: return "Standard"
        case .premium: return "Premium"
        }
    }

    var tagline: String {
        switch self {
        case .free: return "前 30 天每日 60 點，期滿後可看廣告獲點"
        case .basic: return "每日 120 分析點數（可累積・無上限）"
        case .standard: return "無限點數・含驗證率儀表板"
        case .premium: return "無限點數+驗證率儀表板+重點觀察賽事推播通知"
        }
    }

    var icon: String {
        switch self {
        case .free: return "circle"
        case .basic: return "leaf.fill"
        case .standard: return "star.fill"
        case .premium: return "crown.fill"
        }
    }

    var tint: Color {
        switch self {
        case .free: return .gray
        case .basic: return .green
        case .standard: return .blue
        case .premium: return .purple
        }
    }

    var benefits: [String] {
        switch self {
        case .free:
            return [
                "前 30 天每日 60 分析點數",
                "期滿後可觀看廣告獲得點數",
                "基礎賽事資訊"
            ]
        case .basic:
            return [
                "每日 120 分析點數",
                "點數可累積・無上限",
                "基礎賽事分析"
            ]
        case .standard:
            return [
                "無限分析點數",
                "模型驗證率儀表板",
                "收藏賽事分析",
                "觀看廣告獲點數"
            ]
        case .premium:
            return [
                "無限分析點數",
                "完整驗證率儀表板",
                "收藏賽事無限制",
                "推播通知",
                "優先客服支援"
            ]
        }
    }

    var monthlyPriceTWD: Int {
        switch self {
        case .free: return 0
        case .basic: return 100
        case .standard: return 290
        case .premium: return 390
        }
    }

    var yearlyPriceTWD: Int {
        switch self {
        case .free: return 0
        case .basic: return 990
        case .standard: return 2990
        case .premium: return 3850
        }
    }

    /// 依月/年返回當前顯示的價格
    func currentPriceTWD(isAnnual: Bool) -> Int {
        return isAnnual ? yearlyPriceTWD : monthlyPriceTWD
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
        case .free: return "free"
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
