import SwiftUI

/// 單一球隊的雷達圖（用於 FIFA 世界盃分析）
struct SingleRadarChartView: View {
    let categories: [String]
    let values: [Double]
    let teamColor: Color
    let teamName: String
    
    var body: some View {
        VStack(spacing: 6) {
            // 圖例
            HStack(spacing: 6) {
                Circle().fill(teamColor).frame(width: 10, height: 10)
                Text(teamName).font(.caption).fontWeight(.bold)
            }
            
            GeometryReader { geo in
                let center = CGPoint(x: geo.size.width / 2, y: geo.size.height / 2)
                let radius = min(geo.size.width, geo.size.height) / 2 * 0.6
                
                Canvas { context, _ in
                    // 網格
                    for level in stride(from: 0.25, through: 1.0, by: 0.25) {
                        context.stroke(radarPath(values: [10, 10, 10, 10, 10, 10, 10, 10], center: center, radius: radius * CGFloat(level)),
                                       with: .color(.gray.opacity(0.15)), lineWidth: 1)
                    }
                    
                    // 軸線
                    for i in 0..<categories.count {
                        let angle = angle(for: i, count: categories.count)
                        var p = Path()
                        p.move(to: center)
                        p.addLine(to: CGPoint(x: center.x + cos(angle) * radius, y: center.y + sin(angle) * radius))
                        context.stroke(p, with: .color(.gray.opacity(0.25)), lineWidth: 1)
                    }
                    
                    // 數據區域
                    let dataPath = radarPath(values: values, center: center, radius: radius)
                    context.fill(dataPath, with: .color(teamColor.opacity(0.2)))
                    context.stroke(dataPath, with: .color(teamColor), lineWidth: 2.5)
                    
                    // 數據點與標籤
                    for i in 0..<categories.count {
                        let angle = angle(for: i, count: categories.count)
                        let labelPt = CGPoint(x: center.x + cos(angle) * (radius + 28), y: center.y + sin(angle) * (radius + 28))
                        context.draw(Text(categories[i]).font(.system(size: 9)), at: labelPt, anchor: .center)
                        
                        let pt = CGPoint(x: center.x + cos(angle) * (radius * CGFloat(values[i]/10)), y: center.y + sin(angle) * (radius * CGFloat(values[i]/10)))
                        context.fill(Path(ellipseIn: CGRect(x: pt.x-3, y: pt.y-3, width: 6, height: 6)), with: .color(teamColor))
                        context.draw(Text(String(format: "%.1f", values[i])).font(.system(size: 8, weight: .black)).foregroundColor(teamColor), at: CGPoint(x: pt.x, y: pt.y - 10))
                    }
                }
            }
            .aspectRatio(1, contentMode: .fit)
            .padding(8)
        }
    }
    
    private func angle(for index: Int, count: Int) -> CGFloat {
        .pi * 2 / CGFloat(count) * CGFloat(index) - .pi / 2
    }
    
    private func radarPath(values: [Double], center: CGPoint, radius: CGFloat) -> Path {
        var path = Path()
        for i in 0..<values.count {
            let angle = CGFloat.pi * 2 / CGFloat(values.count) * CGFloat(i) - .pi / 2
            let r = radius * CGFloat(values[i] / 10.0)
            let pt = CGPoint(x: center.x + cos(angle) * r, y: center.y + sin(angle) * r)
            if i == 0 { path.move(to: pt) } else { path.addLine(to: pt) }
        }
        path.closeSubpath()
        return path
    }
}

// MARK: - FIFA 世界盃預測主視圖
struct FIFAWorldCupPredictionView: View {
    @Environment(\.dismiss) private var dismiss
    
    let categories = ["進攻能力", "防守能力", "控球能力", "反擊能力", "定位球能力", "球星影響力", "近期狀態", "健康程度"]
    
    var body: some View {
        NavigationStack {
            ScrollView(.vertical, showsIndicators: false) {
                VStack(spacing: 20) {
                    // 標題區
                    headerSection
                    
                    // 四強球隊分析卡片
                    spainSection
                    franceSection
                    argentinaSection
                    englandSection
                    
                    // 奪冠機率表
                    probabilitySection
                    
                    // 決賽預測
                    finalPredictionSection
                    
                    // AI 信心值
                    confidenceSection
                }
                .padding()
            }
            .background(Color(.systemGroupedBackground).ignoresSafeArea())
            .navigationTitle("世界盃冠軍預測")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button(action: { dismiss() }) {
                        Text("關閉")
                    }
                }
            }
        }
    }
    
    // MARK: - 標題
    private var headerSection: some View {
        VStack(spacing: 8) {
            Image(systemName: "trophy.fill")
                .font(.system(size: 40))
                .foregroundColor(.yellow)
            Text("FIFA 世界盃冠軍預測")
                .font(.title2).bold()
            Text("AI 深度分析 · 基於歷史數據與進階模型")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
    }
    
    // MARK: - 西班牙
    private var spainSection: some View {
        teamSection(
            rank: 1,
            flag: "🇪🇸",
            name: "Spain national football team",
            color: .red,
            players: ["Lamine Yamal", "Pedri", "Rodri", "Nico Williams"],
            values: [9.5, 9.0, 10, 8.8, 8.5, 9.3, 9.4, 9.0],
            advantages: ["世界最佳中場控制力", "新世代黃金陣容", "年齡結構最佳", "高壓逼搶體系成熟"],
            risks: ["年輕球員首次世界盃主導淘汰賽"]
        )
    }
    
    // MARK: - 法國
    private var franceSection: some View {
        teamSection(
            rank: 2,
            flag: "🇫🇷",
            name: "France national football team",
            color: Color(red: 0.0, green: 0.3, blue: 0.6),
            players: ["Kylian Mbappé", "Aurélien Tchouaméni", "William Saliba"],
            values: [9.7, 9.3, 8.8, 10, 9.0, 10, 9.0, 8.8],
            advantages: ["世界最強反擊體系", "淘汰賽經驗豐富", "陣容深度最強"],
            risks: ["中場組織能力略低於西班牙"]
        )
    }
    
    // MARK: - 阿根廷
    private var argentinaSection: some View {
        teamSection(
            rank: 3,
            flag: "🇦🇷",
            name: "Argentina national football team",
            color: Color(red: 0.3, green: 0.6, blue: 1.0),
            players: [],
            values: [8.8, 9.1, 8.7, 9.0, 8.9, 9.0, 9.2, 8.5],
            advantages: ["衛冕冠軍", "團隊默契佳", "美洲作戰環境熟悉"],
            risks: ["核心陣容年齡偏高"]
        )
    }
    
    // MARK: - 英格蘭
    private var englandSection: some View {
        teamSection(
            rank: 4,
            flag: "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
            name: "England national football team",
            color: Color(red: 0.0, green: 0.2, blue: 0.6),
            players: [],
            values: [9.2, 8.7, 8.9, 8.9, 9.5, 9.4, 8.8, 9.1],
            advantages: [],
            risks: [],
            note: "關鍵淘汰賽心理壓力"
        )
    }
    
    // MARK: - 通用球隊卡片
    private func teamSection(rank: Int, flag: String, name: String, color: Color, players: [String], values: [Double], advantages: [String], risks: [String], note: String? = nil) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            // 標題
            HStack {
                Text("冠軍候選分析")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Spacer()
                Text("#\(rank)")
                    .font(.caption.bold())
                    .foregroundColor(.white)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 4)
                    .background(color)
                    .cornerRadius(10)
            }
            
            HStack {
                Text(flag)
                    .font(.system(size: 36))
                Text(name)
                    .font(.headline).bold()
                Spacer()
            }
            
            // 核心球員
            if !players.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    Text("核心球員").font(.caption).foregroundColor(.secondary)
                    HStack(spacing: 8) {
                        ForEach(players, id: \.self) { player in
                            Text(player)
                                .font(.system(size: 11))
                                .padding(.horizontal, 10)
                                .padding(.vertical, 4)
                                .background(color.opacity(0.12))
                                .foregroundColor(color)
                                .cornerRadius(8)
                        }
                    }
                }
            }
            
            // 雷達圖
            SingleRadarChartView(
                categories: categories,
                values: values,
                teamColor: color,
                teamName: name
            )
            .frame(height: 220)
            
            // 綜合評價
            VStack(alignment: .leading, spacing: 6) {
                Text("綜合評價").font(.caption).foregroundColor(.secondary)
                
                if !advantages.isEmpty {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("優勢：").font(.system(size: 11, weight: .bold)).foregroundColor(.green)
                        ForEach(advantages, id: \.self) { adv in
                            Label(adv, systemImage: "plus.circle.fill")
                                .font(.system(size: 10))
                                .foregroundColor(.green)
                        }
                    }
                }
                
                if !risks.isEmpty {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("風險：").font(.system(size: 11, weight: .bold)).foregroundColor(.orange)
                        ForEach(risks, id: \.self) { risk in
                            Label(risk, systemImage: "exclamationmark.triangle.fill")
                                .font(.system(size: 10))
                                .foregroundColor(.orange)
                        }
                    }
                }
                
                if let note = note {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("最大問題：").font(.system(size: 11, weight: .bold)).foregroundColor(.red)
                        Label(note, systemImage: "xmark.octagon.fill")
                            .font(.system(size: 10))
                            .foregroundColor(.red)
                    }
                }
            }
        }
        .padding()
        .background(Color(.secondarySystemGroupedBackground))
        .cornerRadius(16)
    }
    
    // MARK: - 奪冠機率表
    private var probabilitySection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("AI 綜合冠軍機率", systemImage: "chart.bar.fill")
                .font(.headline).bold()
            
            VStack(spacing: 0) {
                probabilityRow(rank: 1, flag: "🇪🇸", name: "西班牙", prob: 19.4, color: .red, barWidth: 0.97)
                probabilityRow(rank: 2, flag: "🇫🇷", name: "法國", prob: 17.2, color: Color(red: 0.0, green: 0.3, blue: 0.6), barWidth: 0.86)
                probabilityRow(rank: 3, flag: "🇦🇷", name: "阿根廷", prob: 12.8, color: Color(red: 0.3, green: 0.6, blue: 1.0), barWidth: 0.64)
                probabilityRow(rank: 4, flag: "🏴󠁧󠁢󠁥󠁮󠁧󠁿", name: "英格蘭", prob: 11.6, color: Color(red: 0.0, green: 0.2, blue: 0.6), barWidth: 0.58)
                probabilityRow(rank: 5, flag: "🇧🇷", name: "巴西", prob: 9.7, color: .yellow, barWidth: 0.49)
                probabilityRow(rank: 6, flag: "🇵🇹", name: "葡萄牙", prob: 7.9, color: .green, barWidth: 0.40)
                probabilityRow(rank: 7, flag: "🇩🇪", name: "德國", prob: 6.2, color: Color(red: 0.8, green: 0.7, blue: 0.0), barWidth: 0.31)
            }
        }
        .padding()
        .background(Color(.secondarySystemGroupedBackground))
        .cornerRadius(16)
    }
    
    private func probabilityRow(rank: Int, flag: String, name: String, prob: Double, color: Color, barWidth: CGFloat) -> some View {
        HStack(spacing: 8) {
            Text("#\(rank)").font(.system(size: 10, design: .monospaced)).frame(width: 20)
            Text(flag).font(.system(size: 16))
            Text(name).font(.system(size: 12, weight: .medium)).frame(width: 50, alignment: .leading)
            
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(Color(.tertiarySystemFill))
                    Capsule().fill(color.gradient)
                        .frame(width: geo.size.width * (prob / 20))
                }
            }
            .frame(height: 14)
            
            Text(String(format: "%.1f%%", prob))
                .font(.system(size: 11, design: .monospaced))
                .bold()
                .frame(width: 44, alignment: .trailing)
        }
        .padding(.vertical, 4)
    }
    
    // MARK: - 決賽預測
    private var finalPredictionSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("AI 預測世界盃決賽", systemImage: "trophy.fill")
                .font(.headline).bold()
            
            VStack(spacing: 16) {
                // 對戰組合
                HStack(spacing: 20) {
                    TeamPredictionCard(flag: "🇪🇸", name: "西班牙")
                    Text("VS")
                        .font(.title2.bold())
                        .foregroundColor(.secondary)
                    TeamPredictionCard(flag: "🇫🇷", name: "法國")
                }
                
                Divider()
                
                // 預測比分
                VStack(spacing: 4) {
                    Text("預測比分")
                        .font(.caption).foregroundColor(.secondary)
                    HStack(spacing: 16) {
                        Text("西班牙").font(.headline).foregroundColor(.red)
                        Text("2").font(.system(size: 36, weight: .black))
                            .foregroundColor(.primary)
                        Text(":").font(.title).bold().foregroundColor(.secondary)
                        Text("1").font(.system(size: 36, weight: .black))
                            .foregroundColor(.primary)
                        Text("法國").font(.headline).foregroundColor(Color(red: 0.0, green: 0.3, blue: 0.6))
                    }
                }
                
                // 進球模擬
                VStack(alignment: .leading, spacing: 4) {
                    Text("進球模擬：").font(.caption).foregroundColor(.secondary)
                    HStack(spacing: 8) {
                        Text("🇪🇸 Yamal ⚽").font(.system(size: 11))
                            .padding(.horizontal, 8).padding(.vertical, 4)
                            .background(Color.red.opacity(0.1)).cornerRadius(6)
                        Text("🇪🇸 Pedri ⚽").font(.system(size: 11))
                            .padding(.horizontal, 8).padding(.vertical, 4)
                            .background(Color.red.opacity(0.1)).cornerRadius(6)
                        Text("🇫🇷 Mbappé ⚽").font(.system(size: 11))
                            .padding(.horizontal, 8).padding(.vertical, 4)
                            .background(Color.blue.opacity(0.1)).cornerRadius(6)
                    }
                }
                
                Divider()
                
                // 最終輸出
                VStack(spacing: 8) {
                    Label("AI 最終輸出", systemImage: "cpu.fill")
                        .font(.subheadline).foregroundColor(.secondary)
                    
                    HStack {
                        Text("🏆").font(.title)
                        Text("Spain national football team")
                            .font(.headline).bold()
                        Spacer()
                    }
                    .padding()
                    .background(Color.yellow.opacity(0.1))
                    .cornerRadius(12)
                    .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.yellow.opacity(0.3), lineWidth: 1))
                    
                    HStack {
                        Text("🥈").font(.title)
                        Text("France national football team")
                            .font(.headline)
                        Spacer()
                    }
                    .padding()
                    .background(Color.gray.opacity(0.1))
                    .cornerRadius(12)
                    .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.gray.opacity(0.3), lineWidth: 1))
                }
                
                // 晉級決賽機率
                VStack(alignment: .leading, spacing: 6) {
                    Text("晉級決賽機率").font(.caption).foregroundColor(.secondary)
                    HStack {
                        Text("🇪🇸 西班牙")
                            .font(.system(size: 12)).bold()
                        Spacer()
                        Text("42%")
                            .font(.system(size: 12, design: .monospaced)).bold()
                            .foregroundColor(.red)
                    }
                    .padding(.horizontal, 8).padding(.vertical, 4)
                    .background(Color.red.opacity(0.06)).cornerRadius(8)
                    
                    HStack {
                        Text("🇫🇷 法國")
                            .font(.system(size: 12)).bold()
                        Spacer()
                        Text("38%")
                            .font(.system(size: 12, design: .monospaced)).bold()
                            .foregroundColor(Color(red: 0.0, green: 0.3, blue: 0.6))
                    }
                    .padding(.horizontal, 8).padding(.vertical, 4)
                    .background(Color.blue.opacity(0.06)).cornerRadius(8)
                    
                    HStack {
                        Text("🇦🇷 阿根廷")
                            .font(.system(size: 12)).bold()
                        Spacer()
                        Text("28%")
                            .font(.system(size: 12, design: .monospaced)).bold()
                            .foregroundColor(Color(red: 0.3, green: 0.6, blue: 1.0))
                    }
                    .padding(.horizontal, 8).padding(.vertical, 4)
                    .background(Color.blue.opacity(0.06)).cornerRadius(8)
                    
                    HStack {
                        Text("🏴󠁧󠁢󠁥󠁮󠁧󠁿 英格蘭")
                            .font(.system(size: 12)).bold()
                        Spacer()
                        Text("25%")
                            .font(.system(size: 12, design: .monospaced)).bold()
                            .foregroundColor(Color(red: 0.0, green: 0.2, blue: 0.6))
                    }
                    .padding(.horizontal, 8).padding(.vertical, 4)
                    .background(Color.blue.opacity(0.06)).cornerRadius(8)
                }
            }
        }
        .padding()
        .background(Color(.secondarySystemGroupedBackground))
        .cornerRadius(16)
    }
    
    // MARK: - AI 信心值
    private var confidenceSection: some View {
        VStack(spacing: 8) {
            Text("AI 信心值")
                .font(.caption).foregroundColor(.secondary)
            HStack(spacing: 2) {
                ForEach(0..<8, id: \.self) { _ in
                    Image(systemName: "star.fill")
                        .font(.system(size: 14))
                        .foregroundColor(.yellow)
                }
                Image(systemName: "star.leadinghalf.filled")
                    .font(.system(size: 14))
                    .foregroundColor(.yellow)
                Text("8.4 / 10")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(.secondary)
                    .padding(.leading, 6)
            }
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(Color(.secondarySystemGroupedBackground))
        .cornerRadius(16)
    }
}

struct TeamPredictionCard: View {
    let flag: String
    let name: String
    
    var body: some View {
        VStack(spacing: 6) {
            Text(flag).font(.system(size: 48))
            Text(name).font(.caption).bold()
        }
        .frame(width: 100)
        .padding()
        .background(Color(.tertiarySystemFill))
        .cornerRadius(12)
    }
}

#Preview {
    FIFAWorldCupPredictionView()
}