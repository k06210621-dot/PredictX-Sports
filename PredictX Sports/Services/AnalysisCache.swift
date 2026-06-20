import Foundation

/// AI 分析結果快取（避免重複 API 請求 + 返回時保留）
/// 規則：
/// - 已開啟的賽事分析結果存於此 cache
/// - 進入分析頁面時優先用 cache，否則從 API 抓
/// - 透過 gameId 索引
final class AnalysisCache {
    static let shared = AnalysisCache()
    private var cache: [String: AIAnalysisModel] = [:]
    private let lock = NSLock()

    private init() {}

    func get(gameId: String) -> AIAnalysisModel? {
        lock.lock()
        defer { lock.unlock() }
        return cache[gameId]
    }

    func set(_ analysis: AIAnalysisModel, gameId: String) {
        lock.lock()
        defer { lock.unlock() }
        cache[gameId] = analysis
    }

    func clear(gameId: String? = nil) {
        lock.lock()
        defer { lock.unlock() }
        if let gameId = gameId {
            cache.removeValue(forKey: gameId)
        } else {
            cache.removeAll()
        }
    }
}
