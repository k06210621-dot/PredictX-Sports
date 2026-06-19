import Foundation
import Combine

/// 比賽卡片解鎖管理器 — 記錄哪些賽事已用點數開啟 AI 分析
/// 規則：
/// - Free / Basic 會員：每次開啟扣 20 點，永久記錄為已解鎖
/// - Standard / Premium 會員：免費查看所有勝率條
@MainActor
final class UnlockManager: ObservableObject {
    static let shared = UnlockManager()

    /// 已解鎖的 gameId 集合（永久儲存於 UserDefaults）
    @Published private(set) var unlockedGameIds: Set<String>

    private let storageKey = "PredictX_unlockedGameIds"

    private init() {
        let array = UserDefaults.standard.stringArray(forKey: storageKey) ?? []
        self.unlockedGameIds = Set(array)
    }

    /// 判斷是否已解鎖
    func isUnlocked(gameId: String) -> Bool {
        unlockedGameIds.contains(gameId)
    }

    /// 加入解鎖（永久記錄）
    func unlock(gameId: String) {
        unlockedGameIds.insert(gameId)
        save()
    }

    /// 判斷是否需要付費點數才能解鎖
    /// - Parameter tier: 當前會員等級
    /// - Returns: true = 需要扣點數 / false = 已是付費會員可直接查看
    func requiresPayment(tier: MembershipTier) -> Bool {
        switch tier {
        case .premium, .standard:
            return false  // 進階會員免費查看
        case .free, .basic:
            return true   // 一般會員需付點數
        }
    }

    private func save() {
        UserDefaults.standard.set(Array(unlockedGameIds), forKey: storageKey)
    }
}