import Foundation
import Combine
import SwiftUI

@MainActor
class PlayerStore: ObservableObject {
    @Published var selectedPlayer: Player?
    @Published var powerModifierText: String = "該球員狀態穩定，戰力加權維持常態。"
    @Published var powerModifierColor: Color = .green
    
    init() {}
    
    /// 💡 核心大招：動態基礎戰力修正模組 (Dynamic Power Index Modifier)
    /// 當偵測到球員傷病狀態變更為 OUT 時，全自動計算並修正球隊百回合淨效率與戰力警示
    func selectPlayerAndCalculateModifier(_ player: Player) {
        self.selectedPlayer = player
        
        switch player.injuryStatus {
        case .out:
            // 核心主力缺陣，動態計算對球隊邊際勝率與戰力的實質損耗
            let warImpact = player.baseballStats?.war ?? (player.nbaStats != nil ? 4.5 : 1.0)
            self.powerModifierText = "⚠️ 警示：核心主力因傷缺陣 (OUT)！系統自動調降所屬球隊基礎效率值，全盤戰力下滑 \(Int(warImpact * 3))%！"
            self.powerModifierColor = .red
        case .dayToDay:
            self.powerModifierText = "ℹ️ 提示：該球員目前處於每日觀察名單 (Day-to-Day)，出賽成疑，背靠背體力下滑係數修正中。"
            self.powerModifierColor = .orange
        case .active:
            self.powerModifierText = "✅ 狀態：球員生理機能處於巔峰成長曲線，戰力 100% 滿血釋放。"
            self.powerModifierColor = .green
        }
    }
    
    /// 💡 快速生成 Mock 測試數據 (包含籃球投籃座標與棒球九宮格)
    func generateMockPlayer(for league: LeagueType) -> Player {
        if league == .nba {
            let nodes = [
                HeatmapNode(x: 0, y: 0, frequency: 0.8, efficiency: 0.45), // 左側底角
                HeatmapNode(x: 1, y: 0, frequency: 0.2, efficiency: 0.33),
                HeatmapNode(x: 2, y: 0, frequency: 0.9, efficiency: 0.58), // 禁區得分率
                HeatmapNode(x: 0, y: 1, frequency: 0.4, efficiency: 0.38),
                HeatmapNode(x: 1, y: 1, frequency: 0.7, efficiency: 0.42), // 弧頂
                HeatmapNode(x: 2, y: 1, frequency: 0.3, efficiency: 0.35)
            ]
            return Player(
                id: "NBA-PLAYER-LBJ", name: "LeBron James", teamId: "LAL", jerseyNumber: "23", position: "Forward", age: 39, injuryStatus: .dayToDay,
                nbaStats: NBAPlayerStats(ppg: 25.7, rpg: 7.3, apg: 8.3, tsPercent: 0.612, usgPercent: 0.295, shotCoordinates: nodes)
            )
        } else {
            return Player(
                id: "MLB-PLAYER-OHTANI", name: "Shohei Ohtani", teamId: "LAD", jerseyNumber: "17", position: "DH/DH", age: 31, injuryStatus: .out, // 模擬主力受傷缺陣
                baseballStats: BaseballPlayerStats(war: 8.5, wrcPlus: 180, strikeZoneHotspots: [0.35, 0.42, 0.28, 0.55, 0.68, 0.41, 0.22, 0.31, 0.19]) // 投手九宮格進壘率
            )
        }
    }
}
