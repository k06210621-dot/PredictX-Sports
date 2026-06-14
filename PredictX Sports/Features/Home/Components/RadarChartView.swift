import SwiftUI

/// 專業體育分析雷達圖組件 - 主隊藍色 / 客隊紅色（與勝率推論一致）
public struct RadarChartView: View {
    public let categories: [String]
    public let homeValues: [Double]
    public let awayValues: [Double]
    public let homeTeamName: String
    public let awayTeamName: String
    
    // 統一配色：主隊=藍色，客隊=紅色（與 AI 推論勝率一致）
    let homeColor = Color.blue
    let awayColor = Color.red
    
    public init(categories: [String], homeValues: [Double], awayValues: [Double], homeTeamName: String = "主隊", awayTeamName: String = "客隊") {
        self.categories = categories
        self.homeValues = homeValues
        self.awayValues = awayValues
        self.homeTeamName = homeTeamName
        self.awayTeamName = awayTeamName
    }

    public var body: some View {
        VStack(spacing: 8) {
            // 1. 圖例區 (Legend) — 主隊藍 / 客隊紅
            HStack(spacing: 25) {
                legendItem(color: homeColor, name: homeTeamName)
                legendItem(color: awayColor, name: awayTeamName)
            }
            
            GeometryReader { geo in
                let center = CGPoint(x: geo.size.width / 2, y: geo.size.height / 2)
                let radius = min(geo.size.width, geo.size.height) / 2 * 0.65
                
                Canvas { context, _ in
                    // 網格
                    for level in stride(from: 0.25, through: 1.0, by: 0.25) {
                        context.stroke(radarPath(values: [10, 10, 10, 10, 10, 10], center: center, radius: radius * CGFloat(level)),
                                       with: .color(.gray.opacity(0.2)), lineWidth: 1)
                    }
                    
                    // 軸線
                    for i in 0..<categories.count {
                        let angle = angle(for: i)
                        var p = Path()
                        p.move(to: center)
                        p.addLine(to: CGPoint(x: center.x + cos(angle) * radius, y: center.y + sin(angle) * radius))
                        context.stroke(p, with: .color(.gray.opacity(0.3)), lineWidth: 1)
                    }
                    
                    // 客隊資料（紅色）
                    let awayPath = radarPath(values: awayValues, center: center, radius: radius)
                    context.fill(awayPath, with: .color(awayColor.opacity(0.2)))
                    context.stroke(awayPath, with: .color(awayColor), lineWidth: 2)
                    
                    // 主隊資料（藍色）
                    let homePath = radarPath(values: homeValues, center: center, radius: radius)
                    context.fill(homePath, with: .color(homeColor.opacity(0.2)))
                    context.stroke(homePath, with: .color(homeColor), lineWidth: 2)
                    
                    // 數據點與標籤
                    for i in 0..<categories.count {
                        let angle = angle(for: i)
                        let labelPt = CGPoint(x: center.x + cos(angle) * (radius + 35), y: center.y + sin(angle) * (radius + 35))
                        context.draw(Text(categories[i]).font(.system(size: 12, weight: .bold)), at: labelPt, anchor: .center)
                        
                        let hPt = CGPoint(x: center.x + cos(angle) * (radius * CGFloat(homeValues[i]/10)), y: center.y + sin(angle) * (radius * CGFloat(homeValues[i]/10)))
                        context.fill(Path(ellipseIn: CGRect(x: hPt.x-4, y: hPt.y-4, width: 8, height: 8)), with: .color(homeColor))
                        context.draw(Text(String(format: "%.1f", homeValues[i])).font(.system(size: 10, weight: .black)).foregroundColor(homeColor), at: CGPoint(x: hPt.x, y: hPt.y - 12))
                        
                        let aPt = CGPoint(x: center.x + cos(angle) * (radius * CGFloat(awayValues[i]/10)), y: center.y + sin(angle) * (radius * CGFloat(awayValues[i]/10)))
                        context.fill(Path(ellipseIn: CGRect(x: aPt.x-4, y: aPt.y-4, width: 8, height: 8)), with: .color(awayColor))
                        context.draw(Text(String(format: "%.1f", awayValues[i])).font(.system(size: 10, weight: .black)).foregroundColor(awayColor), at: CGPoint(x: aPt.x, y: aPt.y + 12))
                    }
                }
            }
            .aspectRatio(1, contentMode: .fit)
            .padding(30)
        }
    }
    
    @ViewBuilder
    private func legendItem(color: Color, name: String) -> some View {
        HStack(spacing: 8) {
            Circle().fill(color).frame(width: 12, height: 12)
            Text(name).font(.system(size: 14, weight: .medium))
        }
    }
    
    private func angle(for index: Int) -> CGFloat {
        return .pi * 2 / CGFloat(categories.count) * CGFloat(index) - .pi / 2
    }
    
    private func radarPath(values: [Double], center: CGPoint, radius: CGFloat) -> Path {
        var path = Path()
        for i in 0..<values.count {
            let angle = CGFloat.pi * 2 / CGFloat(categories.count) * CGFloat(i) - .pi / 2
            let r = radius * CGFloat(values[i] / 10.0)
            let pt = CGPoint(x: center.x + cos(angle) * r, y: center.y + sin(angle) * r)
            if i == 0 { path.move(to: pt) } else { path.addLine(to: pt) }
        }
        path.closeSubpath()
        return path
    }
}