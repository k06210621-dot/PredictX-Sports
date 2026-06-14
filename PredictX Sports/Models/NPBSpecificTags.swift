import Foundation

/// ⚾ NPB 日本職棒專屬 AI 預測進階特徵因子
struct NPBSpecificTags: Codable, Hashable {
    // 投手與守備端核心指標
    var aceStarterWHIP: Double?     // 王牌先發投手每局被上壘率 (日職強投壓制力關鍵指標)
    var aceStarterERA: Double?      // 先發投手防禦率
    var teamFieldingPercentage: Double? // 球隊團隊守備率 (日職細膩防守變量)
    
    // 戰術與球場端核心指標
    var sacrificeAndSmallBallRate: Double? // 戰術推進率 (犧牲短打、戰術助攻成功因子)
    var npbParkFactor: Double?      // 日職專屬球場修正係數 (如：巨蛋與戶外球場得分落差)
    var travelFatigueIndex: Double? // 差旅疲勞指數 (新幹線/跨島移動跨度修正)
}
