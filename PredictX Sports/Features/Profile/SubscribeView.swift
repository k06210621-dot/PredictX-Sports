import SwiftUI
import StoreKit

// MARK: - 訂閱 Paywall 主頁（AI 額度儲值中心）
/// 點 ProfileView「升級 Premium」或「訂閱中心」後彈出
struct SubscribeView: View {
    @EnvironmentObject var subscriptionManager: SubscriptionManager
    @Environment(\.dismiss) private var dismiss
    @State private var selectedTier: ProductTier = .standard
    @State private var isAnnual: Bool = false
    @State private var products: [StoreKit.Product] = []
    @State private var loadError: String?

    // 月付／年付方案差價（年訂約等於 8 折）
    private let annualDiscount: Double = 0.2

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
                            Text("切換年訂以享有 8 折優惠・每方案每月最高省 NT$ \(Int(annuallySavedForSelectedTier()))")
                                .font(.caption2)
                                .foregroundColor(Color(.tertiaryLabel))
                                .multilineTextAlignment(.center)
                        }
                        paywallButton
                        paywallLoadError()
                        featuresChart
                        restoreButton
                        legalLinks
                    }
                    .padding(.horizontal, 20)
                    .padding(.bottom, 40)
                }
            }
            .navigationTitle("升級 Premium")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("關閉") { dismiss() }
                        .foregroundColor(.white)
                }
            }
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
            Label("7 天免費試用", systemImage: "gift.fill")
            Divider().frame(height: 14).background(Color(.separator))
            Label("隨時取消", systemImage: "xmark.circle")
            Divider().frame(height: 14).background(Color(.separator))
            Label("App Store 安全交易", systemImage: "lock.shield.fill")
        }
        .font(.system(size: 10, weight: .medium))
        .foregroundColor(.secondary)
        .padding(.vertical, 10)
        .padding(.horizontal, 12)
        .background(Color(.systemGray6))
        .clipShape(Capsule())
    }

    // MARK: - 方案選擇

    private var tierSelection: some View {
        VStack(spacing: 12) {
            // 月／年 切換
            HStack(spacing: 0) {
                billingToggle(title: "月訂", isSelected: !isAnnual) {
                    isAnnual = false
                }
                billingToggle(title: "年訂・省 20%", isSelected: isAnnual) {
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
                .font(.caption.bold())
                .padding(.vertical, 8)
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
                        .font(.headline)
                    if isAnnual {
                        Text("/ 年")
                            .font(.subheadline)
                            .opacity(0.85)
                    } else {
                        Text("/ 月")
                            .font(.subheadline)
                            .opacity(0.85)
                    }
                }
            }
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
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

    /// 訂閱方案載入失敗時於按鈕下方追加錯誤訊息
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
        let productID = selectedTier.productID(isAnnual: isAnnual)
        if let p = products.first(where: { $0.id == productID }) {
            return p.displayPrice
        }
        // 載入失敗時顯示 fallback 價格
        return selectedTier.fallbackPrice(isAnnual: isAnnual)
    }

    // MARK: - 功能對照表

    private var featuresChart: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("方案功能對照", systemImage: "list.bullet.rectangle")
                .font(.headline.bold())
                .foregroundColor(.white)

            VStack(spacing: 0) {
                FeatureRow(label: "每日 AI 分析點數", basic: "120 點", standard: "無限", premium: "無限")
                Divider().background(Color(.separator))
                FeatureRow(label: "球員資料庫", basic: "✓", standard: "✓", premium: "✓")
                Divider().background(Color(.separator))
                FeatureRow(label: "收藏賽事分析", basic: "✓", standard: "✓", premium: "✓")
                Divider().background(Color(.separator))
                FeatureRow(label: "模型驗證率儀表板", basic: "—", standard: "✓", premium: "✓")
                Divider().background(Color(.separator))
                FeatureRow(label: "推播通知", basic: "—", standard: "—", premium: "✓")
                Divider().background(Color(.separator))
                FeatureRow(label: "歷史賽事完整資料", basic: "近 7 日", standard: "近 30 日", premium: "完整")
            }
            .padding(8)
            .background(Color.black.opacity(0.2))
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
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
            .padding(.vertical, 10)
            .background(Color.blue.opacity(0.12))
            .clipShape(RoundedRectangle(cornerRadius: 10))
        }
    }

    // MARK: - 法律與條款連結

    private var legalLinks: some View {
        VStack(spacing: 6) {
            Text("點擊上方按鈕即代表同意 [服務條款] 與 [隱私權政策]")
                .font(.caption2)
                .foregroundColor(Color(.tertiaryLabel))
                .multilineTextAlignment(.center)

            Text("• 訂閱會自動續訂・可在 iPhone「設定」>「Apple ID」>「訂閱項目」中隨時取消")
                .font(.caption2)
                .foregroundColor(Color(.tertiaryLabel))
                .multilineTextAlignment(.center)

            Text("• 取消後仍可使用剩餘的訂閱期間・不會退還當期費用")
                .font(.caption2)
                .foregroundColor(Color(.tertiaryLabel))
                .multilineTextAlignment(.center)

            Text("• PredictX Sports 為運動數據分析工具・所有 AI 推論結果僅供參考・不構成任何投注建議")
                .font(.caption2)
                .foregroundColor(Color(.tertiaryLabel))
                .multilineTextAlignment(.center)
        }
    }

    // MARK: - StoreKit 載入

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
        // 成功後自動關閉（SubscriptionManager 內已驗證並 applyTier）
        if subscriptionManager.tier != .free && subscriptionManager.tier != .basic {
            // 注意：basic 不會 dismiss，讓使用者繼續選擇更高方案
            if selectedTier == .standard || selectedTier == .premium {
                try? await Task.sleep(nanoseconds: 600_000_000)
                dismiss()
            }
        }
    }

    private func annuallySavedForSelectedTier() -> Int {
        let monthly = selectedTier.monthlyPriceTWD
        return Int(Double(monthly) * 12 * annualDiscount)
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
            // icon
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
                        .font(.headline.bold())
                        .foregroundColor(.white)
                    if tier == .standard {
                        Text("推薦")
                            .font(.system(size: 9, weight: .black))
                            .foregroundColor(.white)
                            .padding(.horizontal, 6).padding(.vertical, 2)
                            .background(Color.orange)
                            .clipShape(Capsule())
                    }
                    if tier == .premium {
                        Text("最高性價比")
                            .font(.system(size: 9, weight: .black))
                            .foregroundColor(.white)
                            .padding(.horizontal, 6).padding(.vertical, 2)
                            .background(Color.purple)
                            .clipShape(Capsule())
                    }
                }

                Text(tier.tagline)
                    .font(.caption)
                    .foregroundColor(.secondary)

                Text(displayPrice)
                    .font(.subheadline.bold())
                    .foregroundColor(tier.tint)
            }

            Spacer()

            VStack {
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(.title3)
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
            let yearMonthly = Double(tier.monthlyPriceTWD * 12) * (1 - annualDiscount)
            return "NT$ \(Int(yearMonthly)) / 月 (年訂)"
        } else {
            return "NT$ \(tier.monthlyPriceTWD) / 月"
        }
    }
}

// MARK: - 功能對照表 row

private struct FeatureRow: View {
    let label: String
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
            .frame(width: 56)
            .padding(.vertical, 4)
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
        case .basic: return "每日 120 點數・最基礎"
        case .standard: return "無限點數・含驗證率儀表板"
        case .premium: return "無限 + 推播通知 + 完整歷史"
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

    /// 月付 TWD 標價（同步顯示用，實際下單以 StoreKit 為準）
    var monthlyPriceTWD: Int {
        switch self {
        case .basic: return 99
        case .standard: return 299
        case .premium: return 399
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

    /// 載入失敗時的 fallback 顯示（同步於 App Store Connect 價格）
    func fallbackPrice(isAnnual: Bool) -> String {
        if isAnnual {
            let year = Double(monthlyPriceTWD * 12) * 0.8
            return "NT$ \(Int(year))"
        }
        return "NT\(monthlyPriceTWD)"
    }
}
