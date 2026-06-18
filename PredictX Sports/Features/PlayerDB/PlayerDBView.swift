import SwiftUI

struct PlayerDBView: View {
    @StateObject private var store = PlayerStore()
    
    // 定義棒球九宮格的標準佈局
    private let baseballGridColumns = Array(repeating: GridItem(.flexible(), spacing: 6), count: 3)
    // 定義籃球半場矩陣的標準佈局
    private let basketballGridColumns = Array(repeating: GridItem(.flexible(), spacing: 4), count: 3)
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    
                    // 頂部沙盒調測控制區
                    HStack(spacing: 16) {
                        Button("載入 NBA 巨星") {
                            store.selectPlayerAndCalculateModifier(store.generateMockPlayer(for: .nba))
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(.orange)
                        
                        Button("載入 MLB 巨星") {
                            store.selectPlayerAndCalculateModifier(store.generateMockPlayer(for: .mlb))
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(.blue)
                    }
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.top)
                    
                    if let player = store.selectedPlayer {
                        // 1. 球員基本頭銜勳章
                        VStack(spacing: 6) {
                            Text("\(player.position) #\(player.jerseyNumber)")
                                .font(.caption).bold().foregroundColor(.secondary)
                            Text(player.name)
                                .font(.title).bold()
                            Text("年齡: \(player.age) 歲 (生理成長曲線修正碼已掛載)")
                                .font(.caption).foregroundColor(.gray)
                        }
                        .frame(maxWidth: .infinity, alignment: .center)
                        .padding()
                        .background(Color(.secondarySystemGroupedBackground))
                        .cornerRadius(16)
                        
                        // 2. 靈魂核心：動態基礎戰力修正指示板
                        VStack(alignment: .leading, spacing: 8) {
                            Label("戰力修正加權模組", systemImage: "bolt.shield.fill")
                                .font(.headline).foregroundColor(store.powerModifierColor)
                            Text(store.powerModifierText)
                                .font(.subheadline)
                                .fontWeight(.medium)
                                .foregroundColor(store.powerModifierColor)
                                .lineSpacing(4)
                        }
                        .padding()
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(store.powerModifierColor.opacity(0.08))
                        .cornerRadius(12)
                        .overlay(RoundedRectangle(cornerRadius: 12).stroke(store.powerModifierColor.opacity(0.2), lineWidth: 1))
                        
                        // 3. 核心亮點：虛擬球場熱區分析儀 (Visual Heatmap Grid)
                        VStack(alignment: .leading, spacing: 14) {
                            Label("AI 核心進攻/防守熱區分析 (Heatmap)", systemImage: "point.topleft.down.to.point.bottomright.curvepath")
                                .font(.headline).foregroundColor(.purple)
                            
                            Divider()
                            
                            if let nba = player.nbaStats {
                                // 🏀 籃球熱區：半場投籃命中率矩陣
                                Text("籃球半場投籃出手期望值矩陣").font(.caption).foregroundColor(.secondary)
                                LazyVGrid(columns: basketballGridColumns, spacing: 6) {
                                    ForEach(nba.shotCoordinates) { node in
                                        VStack(spacing: 4) {
                                            Text("頻率: \(Int(node.frequency * 100))%")
                                            Text("命中: \(Int(node.efficiency * 100))%").bold()
                                        }
                                        .font(.system(size: 11, weight: .bold, design: .rounded))
                                        .foregroundColor(.primary)
                                        .frame(height: 70)
                                        .frame(maxWidth: .infinity)
                                        // 💡 熱區色彩演算法：頻率越高越趨近發光深紅，越低則偏向發光幽藍
                                        .background(
                                            LinearGradient(
                                                colors: [
                                                    Color.red.opacity(node.frequency),
                                                    Color.blue.opacity(1.0 - node.frequency)
                                                ],
                                                startPoint: .topLeading, endPoint: .bottomTrailing
                                            )
                                        )
                                        .cornerRadius(10)
                                        .shadow(color: Color.purple.opacity(0.15), radius: 4)
                                    }
                                }
                            } else if let baseball = player.baseballStats {
                                // ⚾ 棒球熱區：投手九宮格進壘率 / 打者攻擊熱區
                                Text("棒球好球帶虛擬九宮格進壘熱效應").font(.caption).foregroundColor(.secondary)
                                LazyVGrid(columns: baseballGridColumns, spacing: 8) {
                                    ForEach(0..<baseball.strikeZoneHotspots.count, id: \.self) { index in
                                        let density = baseball.strikeZoneHotspots[index]
                                        VStack {
                                            Text("區域 \(index + 1)")
                                                .font(.caption2).foregroundColor(.secondary)
                                            Text(String(format: "%.1f%%", density * 100))
                                                .font(.system(size: 14, weight: .black, design: .rounded))
                                                .foregroundColor(.primary)
                                        }
                                        .frame(height: 80)
                                        .frame(maxWidth: .infinity)
                                        // 九宮格發光熱度：密度越高，拋光白金與發光紅越強烈
                                        .background(
                                            Color.red.opacity(density)
                                                .overlay(Color.blue.opacity(1.0 - density))
                                        )
                                        .cornerRadius(8)
                                        .shadow(color: Color.black.opacity(0.1), radius: 3)
                                    }
                                }
                            }
                        }
                        .padding()
                        .background(Color(.secondarySystemGroupedBackground))
                        .cornerRadius(16)
                        
                    } else {
                        // 初始未加載狀態
                        ContentUnavailableView(
                            "請載入球員數據",
                            systemImage: "person.text.rectangle",
                            description: Text("點擊上方測試按鈕，即刻啟動跨球種萬能解碼特徵工程")
                        )
                        .padding(.top, 40)
                    }
                }
                .padding()
            }
            .background(Color(.systemGroupedBackground).ignoresSafeArea())
            .navigationTitle("球員分析資料庫")
        }
    }
}
