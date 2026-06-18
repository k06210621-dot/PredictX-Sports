import Foundation
import SwiftUI
import StoreKit
import Combine

enum MembershipTier: String, Codable {
    case free = "Free Trial"
    case basic = "Basic"
    case standard = "Standard"
    case premium = "Premium"
}

@MainActor
class SubscriptionManager: ObservableObject {
    @Published var tier: MembershipTier = .free
    @Published var diamonds: Int = 0
    @Published var diamondDailyCap: Int = 100
    @Published var unlockedAnalysisIds: Set<String> = []
    @Published var isProcessing = false
    @Published var showSubscribeView = false
    @Published var showDiamondsInfo = false
    @Published var lastPurchaseError: String?
    @Published var lastPurchaseSucceeded: Bool = false

    // 試用期
    @Published var trialStartDate: Date?
    @Published var trialDaysRemaining: Int = 7

    private let defaults = UserDefaults.standard
    private var updates: Task<Void, Never>?

    // MARK: - Product IDs

    /// 月訂方案 product ID（已在 App Store Connect 建立完成後啟用）
    let monthlyProductIDs: [String] = [
        "com.predictxsports.basic.monthly",
        "com.predictxsports.standard.monthly",
        "com.predictxsports.premium.monthly"
    ]

    /// 年訂方案 product ID（已在 App Store Connect 建立完成後啟用）
    let yearlyProductIDs: [String] = [
        "com.predictxsports.basic.yearly",
        "com.predictxsports.standard.yearly",
        "com.predictxsports.premium.yearly"
    ]

    /// 全部 product ID（月+年），啟動時一次拉回
    var allProductIDs: [String] { monthlyProductIDs + yearlyProductIDs }

    /// 月訂方案對照 key（前向相容）
    var productIDs: [String] { monthlyProductIDs }

    var diamondCostPerAnalysis: Int { 20 }

    init() {
        loadFromUserDefaults()
        // 每天重置鑽石配額（如果沒訂閱）
        checkDailyReset()
        // 監聽 StoreKit 交易
        updates = observeTransactions()
    }

    deinit {
        updates?.cancel()
    }

    // MARK: - 儲存 / 讀取

    private func loadFromUserDefaults() {
        if let raw = defaults.string(forKey: "membership_tier"),
           let t = MembershipTier(rawValue: raw) {
            tier = t
        }
        diamonds = defaults.integer(forKey: "diamonds")
        diamondDailyCap = defaults.integer(forKey: "diamond_cap")
        if diamondDailyCap == 0 { diamondDailyCap = tier == .free ? 100 : Int.max }

        if let ids = defaults.array(forKey: "unlocked_analyses") as? [String] {
            unlockedAnalysisIds = Set(ids)
        }
        trialStartDate = defaults.object(forKey: "trial_start") as? Date
        if let start = trialStartDate {
            let elapsed = Calendar.current.dateComponents([.day], from: start, to: Date()).day ?? 0
            trialDaysRemaining = max(0, 7 - elapsed)
        } else {
            trialDaysRemaining = 7
        }
    }

    private func save() {
        defaults.set(tier.rawValue, forKey: "membership_tier")
        defaults.set(diamonds, forKey: "diamonds")
        defaults.set(diamondDailyCap, forKey: "diamond_cap")
        defaults.set(Array(unlockedAnalysisIds), forKey: "unlocked_analyses")
        if let d = trialStartDate {
            defaults.set(d, forKey: "trial_start")
        }
    }

    // MARK: - 每日鑽石重置

    private func checkDailyReset() {
        let today = Calendar.current.startOfDay(for: Date())
        let lastReset = defaults.object(forKey: "last_diamond_reset") as? Date ?? .distantPast
        if tier == .free && Calendar.current.startOfDay(for: lastReset) != today {
            diamonds = 60
            defaults.set(today, forKey: "last_diamond_reset")
            save()
        }
    }

    // MARK: - 鑽石管理

    func canWatchAnalysis() -> Bool {
        switch tier {
        case .standard, .premium:
            return true
        case .basic:
            return diamonds >= diamondCostPerAnalysis
        case .free:
            return diamonds >= diamondCostPerAnalysis
        }
    }

    func spendDiamond() -> Bool {
        guard canWatchAnalysis() else { return false }
        switch tier {
        case .standard, .premium:
            return true
        case .basic, .free:
            diamonds -= diamondCostPerAnalysis
            save()
            return true
        }
    }

    func unlockAnalysis(_ gameId: String) {
        unlockedAnalysisIds.insert(gameId)
        save()
    }

    func isUnlocked(_ gameId: String) -> Bool {
        switch tier {
        case .standard, .premium:
            return true
        case .basic, .free:
            return unlockedAnalysisIds.contains(gameId)
        }
    }

    func canUseFavorites() -> Bool {
        tier != .free
    }

    func canSeeHighConfidence() -> Bool {
        tier == .premium
    }

    func canReceivePush() -> Bool {
        tier == .premium
    }

    // MARK: - 訂閱流程

    /// 呼叫 StoreKit 2 來購買指定 product ID
    func purchase(_ productID: String) async {
        isProcessing = true
        lastPurchaseError = nil
        lastPurchaseSucceeded = false
        defer { isProcessing = false }

        do {
            // 1. 從 StoreKit 取得 product 物件（包含價格、顯示名稱）
            let products = try await Product.products(for: [productID])
            guard let product = products.first else {
                lastPurchaseError = "找不到此訂閱方案 (\(productID))"
                return
            }

            // 2. 觸發購買 UI
            let result = try await product.purchase()

            switch result {
            case .success(let verification):
                switch verification {
                case .verified(let transaction):
                    await applyTier(for: transaction.productID)
                    await transaction.finish()
                    lastPurchaseSucceeded = true
                case .unverified:
                    lastPurchaseError = "交易驗證失敗，請聯絡客服"
                }
            case .userCancelled:
                lastPurchaseError = nil  // 使用者主動取消，不算錯誤
                break
            case .pending:
                lastPurchaseError = "購買正在等待核准（例如家庭共享需家長同意）"
            @unknown default:
                lastPurchaseError = "未知的購買結果"
            }
        } catch {
            lastPurchaseError = "購買失敗：\(error.localizedDescription)"
        }
    }

    func restorePurchases() async {
        isProcessing = true
        defer { isProcessing = false }
        do {
            try await AppStore.sync()
            for await result in StoreKit.Transaction.currentEntitlements {
                if case .verified(let transaction) = result {
                    await applyTier(for: transaction.productID)
                    await transaction.finish()
                }
            }
            lastPurchaseSucceeded = true
        } catch {
            lastPurchaseError = "恢復購買失敗：\(error.localizedDescription)"
        }
    }

    /// 把 product ID 對應到 MembershipTier（同時處理月訂與年訂）
    private func applyTier(for productID: String) async {
        // 月／年訂同 key，去掉 yearly / monthly 後綴
        let baseID = productID
            .replacingOccurrences(of: ".monthly", with: "")
            .replacingOccurrences(of: ".yearly", with: "")

        switch baseID {
        case "com.predictxsports.basic":
            tier = .basic; diamondDailyCap = 120
        case "com.predictxsports.standard":
            tier = .standard; diamondDailyCap = Int.max
            diamonds = Int.max
        case "com.predictxsports.premium":
            tier = .premium; diamondDailyCap = Int.max
            diamonds = Int.max
        default:
            // 對舊版的直接 monthly key 也保留支援
            switch productID {
            case "com.predictxsports.basic.monthly":
                tier = .basic; diamondDailyCap = 120
            case "com.predictxsports.standard.monthly", "com.predictxsports.standard.yearly":
                tier = .standard; diamondDailyCap = Int.max
                diamonds = Int.max
            case "com.predictxsports.premium.monthly", "com.predictxsports.premium.yearly":
                tier = .premium; diamondDailyCap = Int.max
                diamonds = Int.max
            default:
                return
            }
        }
        save()
    }

    // MARK: - 試用期開始

    func startTrial() {
        if trialStartDate == nil {
            trialStartDate = Date()
            diamonds = 60
            diamondDailyCap = 100
            tier = .free
            save()
        }
    }

    // MARK: - StoreKit 交易監聽（含背景更新）

    private func observeTransactions() -> Task<Void, Never> {
        Task { [weak self] in
            for await result in StoreKit.Transaction.updates {
                if case .verified(let transaction) = result {
                    await self?.applyTier(for: transaction.productID)
                    await transaction.finish()
                }
            }
        }
    }
}
