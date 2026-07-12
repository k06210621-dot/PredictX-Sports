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
    @Published var diamondDailyCap: Int = 60
    @Published var unlockedAnalysisIds: Set<String> = []
    @Published var isProcessing = false
    @Published var showSubscribeView = false
    @Published var showDiamondsInfo = false
    @Published var lastPurchaseError: String?
    @Published var lastPurchaseSucceeded: Bool = false

    // 試用期
    @Published var trialStartDate: Date?
    @Published var trialDaysRemaining: Int = 30
    @Published var trialExpired: Bool = false

    // 🆕 [2026-06-29] 已取消訂閱的 transaction ID，避免重複觸發降級
    private var processedExpiredTransactionIDs: Set<UInt64> = []

    // 廣告觀看機制
    @Published var adsWatchedToday: Int = 0
    @Published var lastAdWatchDate: Date? = nil
    let adRewardPoints: Int = 20
    let adDailyLimit: Int = 3

    // 扣點回饋（供 UI 顯示 toast）
    @Published var lastSpendFeedback: (cost: Int, remaining: Int)? = nil
    @Published var lastAdRewardFeedback: Int? = nil  // 觀看廣告回饋

    private let defaults = UserDefaults.standard
    private var updates: Task<Void, Never>?
    private var midnightTimer: Timer?

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
    let trialDurationDays: Int = 30

    init() {
        loadFromUserDefaults()
        // 首次啟動自動開始試用期
        if trialStartDate == nil {
            startTrial()
        }
        // 檢查試用是否過期
        checkTrialExpiry()
        // 每天重置分析點數
        checkDailyReset()
        // 監聽 StoreKit 交易
        updates = observeTransactions()
        // 跨午夜自動重置（監聽系統時間大幅變動）
        setupMidnightObserver()
    }

    deinit {
        updates?.cancel()
        midnightTimer?.invalidate()
    }

    // MARK: - 儲存 / 讀取

    private func loadFromUserDefaults() {
        if let raw = defaults.string(forKey: "membership_tier"),
           let t = MembershipTier(rawValue: raw) {
            tier = t
        }
        diamonds = defaults.integer(forKey: "diamonds")
        diamondDailyCap = defaults.integer(forKey: "diamond_cap")
        if diamondDailyCap == 0 {
            switch tier {
            case .free: diamondDailyCap = 60
            case .basic: diamondDailyCap = Int.max
            case .standard, .premium: diamondDailyCap = Int.max
            }
        }

        if let ids = defaults.array(forKey: "unlocked_analyses") as? [String] {
            unlockedAnalysisIds = Set(ids)
        }
        trialStartDate = defaults.object(forKey: "trial_start") as? Date
        if let start = trialStartDate {
            let elapsed = Calendar.current.dateComponents([.day], from: start, to: Date()).day ?? 0
            trialDaysRemaining = max(0, trialDurationDays - elapsed)
        } else {
            trialDaysRemaining = trialDurationDays
        }

        // 載入廣告觀看紀錄
        adsWatchedToday = defaults.integer(forKey: "ads_watched_today")
        lastAdWatchDate = defaults.object(forKey: "last_ad_watch_date") as? Date
    }

    private func save() {
        defaults.set(tier.rawValue, forKey: "membership_tier")
        defaults.set(diamonds, forKey: "diamonds")
        defaults.set(diamondDailyCap, forKey: "diamond_cap")
        defaults.set(Array(unlockedAnalysisIds), forKey: "unlocked_analyses")
        if let d = trialStartDate {
            defaults.set(d, forKey: "trial_start")
        }
        defaults.set(adsWatchedToday, forKey: "ads_watched_today")
        if let d = lastAdWatchDate {
            defaults.set(d, forKey: "last_ad_watch_date")
        }
    }

    // MARK: - 試用期管理

    func startTrial() {
        guard trialStartDate == nil else { return }
        trialStartDate = Date()
        diamonds = 60
        diamondDailyCap = 60
        tier = .free
        trialDaysRemaining = trialDurationDays
        trialExpired = false
        save()
    }

    /// 檢查試用期是否過期（每次 init + 每日重置時呼叫）
    private func checkTrialExpiry() {
        guard tier == .free, let start = trialStartDate else { return }
        let elapsed = Calendar.current.dateComponents([.day], from: start, to: Date()).day ?? 0
        trialDaysRemaining = max(0, trialDurationDays - elapsed)

        if elapsed >= trialDurationDays {
            trialExpired = true
            diamonds = 0
            save()
        }
    }

    // MARK: - 每日分析點數重置

    private func checkDailyReset() {
        let today = Calendar.current.startOfDay(for: Date())
        let lastReset = defaults.object(forKey: "last_diamond_reset") as? Date ?? .distantPast
        let isNewDay = Calendar.current.startOfDay(for: lastReset) != today

        guard isNewDay else { return }

        // 先檢查試用是否過期
        checkTrialExpiry()

        switch tier {
        case .free:
            if trialExpired {
                // 試用過期：點數歸零，不給新點數
                diamonds = 0
            } else {
                // 試用期內：每天 60 點，不可累計
                diamonds = 60
            }
        case .basic:
            // Basic 每天加 120 點，可累計無上限
            diamonds += 120
        case .standard, .premium:
            diamonds = Int.max
        }

        defaults.set(today, forKey: "last_diamond_reset")

        // 跨日重置：廣告觀看次數歸零
        if let lastAd = lastAdWatchDate,
           Calendar.current.startOfDay(for: lastAd) != today {
            adsWatchedToday = 0
        }

        save()
    }

    // MARK: - 廣告觀看機制

    /// 檢查今天是否還能看廣告（純讀取，不修改狀態）
    func canWatchAd() -> Bool {
        return adsWatchedToday < adDailyLimit
    }

    /// 跨日重置廣告次數（需在 view body 外呼叫，例如 onAppear）
    func resetAdCountIfNewDay() {
        if let lastAd = lastAdWatchDate,
           Calendar.current.startOfDay(for: lastAd) != Calendar.current.startOfDay(for: Date()) {
            adsWatchedToday = 0
            save()
        }
    }

    /// 觀看廣告獲得分析點數（成功回傳新點數，失敗回傳 nil）
    @discardableResult
    func watchAdForPoints() -> Int? {
        guard canWatchAd() else { return nil }
        diamonds += adRewardPoints
        adsWatchedToday += 1
        lastAdWatchDate = Date()
        lastAdRewardFeedback = adRewardPoints
        save()
        return adRewardPoints
    }

    /// 今日剩餘可觀看廣告次數
    var adsRemainingToday: Int {
        max(0, adDailyLimit - adsWatchedToday)
    }

    /// 跨午夜自動重置（監聽系統時間變動 + 定時器）
    private func setupMidnightObserver() {
        // 監聽系統時間大幅變動（跨日、時區切換）
        NotificationCenter.default.addObserver(
            forName: UIApplication.significantTimeChangeNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            guard let self else { return }
            Task { @MainActor in
                self.checkDailyReset()
            }
        }

        // 定時器：每 60 秒檢查一次是否跨日
        midnightTimer = Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { [weak self] _ in
            guard let self else { return }
            Task { @MainActor in
                self.checkDailyReset()
            }
        }
    }

    // MARK: - 分析點數管理

    func canWatchAnalysis() -> Bool {
        switch tier {
        case .standard, .premium:
            return true
        case .basic:
            return diamonds >= diamondCostPerAnalysis
        case .free:
            if trialExpired { return false }
            return diamonds >= diamondCostPerAnalysis
        }
    }

    func spendDiamond() -> Bool {
        guard canWatchAnalysis() else {
            // 試用過期 → 引導訂閱
            if tier == .free && trialExpired {
                showSubscribeView = true
            }
            return false
        }
        switch tier {
        case .standard, .premium:
            return true
        case .basic, .free:
            diamonds -= diamondCostPerAnalysis
            // 記錄扣點回饋（供 UI toast）
            lastSpendFeedback = (cost: diamondCostPerAnalysis, remaining: diamonds)
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
            let products = try await Product.products(for: [productID])
            guard let product = products.first else {
                lastPurchaseError = "找不到此訂閱方案 (\(productID))"
                return
            }

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
                lastPurchaseError = nil
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
            var foundValidTransaction = false
            for await result in StoreKit.Transaction.currentEntitlements {
                if case .verified(let transaction) = result {
                    // 檢查交易是否仍有效
                    if let expirationDate = transaction.expirationDate,
                       expirationDate <= Date() {
                        // 交易已過期 → 降級
                        await handleSubscriptionExpired(
                            productID: transaction.productID,
                            transactionID: transaction.id
                        )
                    } else {
                        // 交易有效 → 升級
                        await applyTier(for: transaction.productID)
                        foundValidTransaction = true
                    }
                    await transaction.finish()
                }
            }

            // 🆕 [2026-06-29] 如果目前是付費會員但找不到任何有效交易（刪除 App 重裝、跨 Apple ID 登入）
            // 主動降級到 free
            if !foundValidTransaction && tier != .free {
                #if DEBUG
                print("⚠️ No valid transactions found, but tier=\(tier). Downgrading to free.")
                #endif
                restoreFreeTier(reason: "restore_no_valid_transaction")
            }

            lastPurchaseSucceeded = true
        } catch {
            lastPurchaseError = "恢復購買失敗：\(error.localizedDescription)"
        }
    }

    /// 把 product ID 對應到 MembershipTier（同時處理月訂與年訂）
    private func applyTier(for productID: String) async {
        let baseID = productID
            .replacingOccurrences(of: ".monthly", with: "")
            .replacingOccurrences(of: ".yearly", with: "")

        switch baseID {
        case "com.predictxsports.basic":
            tier = .basic; diamondDailyCap = Int.max
            trialExpired = false  // 訂閱後清除試用過期標記
        case "com.predictxsports.standard":
            tier = .standard; diamondDailyCap = Int.max
            diamonds = Int.max; trialExpired = false
        case "com.predictxsports.premium":
            tier = .premium; diamondDailyCap = Int.max
            diamonds = Int.max; trialExpired = false
        default:
            switch productID {
            case "com.predictxsports.basic.monthly":
                tier = .basic; diamondDailyCap = Int.max; trialExpired = false
            case "com.predictxsports.standard.monthly", "com.predictxsports.standard.yearly":
                tier = .standard; diamondDailyCap = Int.max
                diamonds = Int.max; trialExpired = false
            case "com.predictxsports.premium.monthly", "com.predictxsports.premium.yearly":
                tier = .premium; diamondDailyCap = Int.max
                diamonds = Int.max; trialExpired = false
            default:
                return
            }
        }
        save()
    }

    // MARK: - 訂閱降級 / 取消處理

    /// 處理訂閱交易已過期（取消、退款、Apple 拒絕續訂）
    /// 🆕 [2026-06-29] 修正 bug：取消訂閱後 tier 卡在 .standard 不還原
    @MainActor
    private func handleSubscriptionExpired(productID: String, transactionID: UInt64) async {
        // 避免重複處理同一個 transaction
        guard !processedExpiredTransactionIDs.contains(transactionID) else { return }
        processedExpiredTransactionIDs.insert(transactionID)

        // 還原到 free 方案
        restoreFreeTier(reason: "subscription_expired:\(productID)")
    }

    /// 還原到 free 方案（取消訂閱、訂閱過期、退款時呼叫）
    /// 🆕 [2026-06-29] 新增：統一處理降級到 free 的邏輯
    @MainActor
    func restoreFreeTier(reason: String) {
        // 記錄降級原因（debug 用）
        #if DEBUG
        print("🔻 訂閱降級到 Free: \(reason)")
        #endif

        // 1. 還原 tier
        tier = .free

        // 2. 還原點數設定
        diamondDailyCap = 60

        // 3. 判斷試用期狀態
        if let start = trialStartDate {
            let elapsed = Calendar.current.dateComponents([.day], from: start, to: Date()).day ?? 0
            if elapsed >= trialDurationDays {
                // 試用期早已過期 → 維持 expired 狀態
                trialExpired = true
                trialDaysRemaining = 0
                diamonds = 0
            } else {
                // 試用期還沒過（理論上 Apple 不會讓你重複用）→ 仍可繼續
                trialExpired = false
                trialDaysRemaining = max(0, trialDurationDays - elapsed)
                diamonds = 60
            }
        } else {
            // 沒有 trialStartDate（不太可能）
            trialExpired = true
            trialDaysRemaining = 0
            diamonds = 0
        }

        // 4. 清空解鎖紀錄（保守做法：用戶降級後不應保留 Premium 解鎖）
        unlockedAnalysisIds = []

        // 5. 持久化
        save()

        // 6. 推播通知（todo）：通知 UI 顯示「訂閱已到期」
    }

    // MARK: - StoreKit 交易監聽（含背景更新）

    /// 🆕 [2026-06-29] 修正 bug：完整處理交易過期/取消事件
    /// - 偵測 transaction.expirationDate 已過期
    /// - 偵測 transaction.revocationDate（退款）
    /// - 偵測 .unverified 事件
    private func observeTransactions() -> Task<Void, Never> {
        Task { [weak self] in
            for await result in StoreKit.Transaction.updates {
                guard let self else { return }
                switch result {
                case .verified(let transaction):
                    // 判斷交易是否仍有效
                    if let expirationDate = transaction.expirationDate,
                       expirationDate <= Date() {
                        // 交易已過期（取消、拒絕續訂）
                        #if DEBUG
                        print("⚠️ Transaction expired: \(transaction.id) (product=\(transaction.productID))")
                        #endif
                        await self.handleSubscriptionExpired(
                            productID: transaction.productID,
                            transactionID: transaction.id
                        )
                    } else if transaction.revocationDate != nil {
                        // 退款導致撤銷
                        #if DEBUG
                        print("⚠️ Transaction revoked: \(transaction.id) (product=\(transaction.productID))")
                        #endif
                        await self.handleSubscriptionExpired(
                            productID: transaction.productID,
                            transactionID: transaction.id
                        )
                    } else {
                        // 交易有效（首次購買、續訂）
                        await self.applyTier(for: transaction.productID)
                    }
                    await transaction.finish()

                case .unverified(_, let error):
                    #if DEBUG
                    print("⚠️ Transaction unverified: \(error.localizedDescription)")
                    #endif
                    // 驗證失敗：保守做法不動作（讓 App 維持原狀）
                    break
                }
            }
        }
    }
}
