import Foundation

/// ⚾ CPBL 中華職棒專屬 AI 預測進階特徵因子
struct CPBLSpecificTags: Codable, Hashable {
    // 投手端核心指標
    var localPitcherFIP: Double?    // 本土投手獨立防禦率 (FIP，排除中職守備干擾)
    var foreignPitcherFIP: Double?  // 外籍洋投獨立防禦率 (FIP)
    var bullpenWHIP: Double?        // 牛棚後援投手每局被上壘率 (中職勝負隱形關鍵)
    
    // 打擊與球場端核心指標
    var homeRunDerbyRate: Double?   // 預估全壘打產出率變量 (HR/9)
    var isDomeStadium: Bool        // 是否為巨蛋室內賽事 (影響風向與濕度因子)
    var localizedHumidity: Double?  // 台灣南部夏日高濕度修正係數
}
