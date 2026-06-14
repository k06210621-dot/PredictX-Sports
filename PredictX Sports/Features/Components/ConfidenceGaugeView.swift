import SwiftUI

/// 🎯 專業級半圓形信心指數 Gauge 圖表
/// 用於提升卡片視覺高級感，取代純文字數字顯示
struct ConfidenceGaugeView: View {
    let confidence: Double // 0.0 ... 1.0
    let scorePrediction: String?
    let homeTeam: String
    let awayTeam: String
    
    // 根據信心指數動態變換色彩
    private var gaugeColor: Color {
        if confidence >= 0.85 {
            return Color(red: 0.12, green: 0.75, blue: 0.45) // 深綠色
        } else if confidence >= 0.70 {
            return .blue
        } else if confidence >= 0.55 {
            return .orange
        } else {
            return .red
        }
    }
    
    // 信心評級文字
    private var confidenceLabel: String {
        if confidence >= 0.85 { return "極高信心" }
        else if confidence >= 0.70 { return "中高信心" }
        else if confidence >= 0.55 { return "中等信心" }
        else { return "低信心" }
    }
    
    var body: some View {
        VStack(spacing: 12) {
            // 標題區
            HStack {
                Image(systemName: "cpu.fill")
                    .foregroundColor(gaugeColor)
                Text("AI 推論信心")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(.primary)
                Spacer()
                Text(confidenceLabel)
                    .font(.caption)
                    .foregroundColor(gaugeColor)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(gaugeColor.opacity(0.12))
                    .clipShape(Capsule())
            }
            
            // 半圓形 Gauge
            ZStack {
                // 背景弧（淺灰）
                GaugeTrackShape()
                    .stroke(Color(.systemGray5), lineWidth: 14)
                
                // 前景弧（會動的顏色）
                GaugeTrackShape(progress: confidence)
                    .stroke(
                        AngularGradient(
                            gradient: Gradient(colors: [.red, .orange, .yellow, .green]),
                            center: .center,
                            startAngle: .degrees(180),
                            endAngle: .degrees(0)
                        ).opacity(0.8),
                        lineWidth: 14
                    )
                
                // 中心數據面板
                VStack(spacing: 4) {
                    Text(String(format: "%.0f%%", confidence * 100))
                        .font(.system(size: 38, weight: .bold, design: .rounded))
                        .foregroundColor(gaugeColor)
                    
                    if let score = scorePrediction {
                        HStack(spacing: 6) {
                            Text("預測分數")
                                .font(.caption2)
                                .foregroundColor(.secondary)
                            Text(score)
                                .font(.system(size: 14, weight: .bold, design: .rounded))
                                .foregroundColor(.primary)
                        }
                    }
                }
                .offset(y: 16)
            }
            .frame(height: 150)
            .padding(.horizontal, 10)
            
            // 底部主客標籤對應
            HStack {
                HStack(spacing: 4) {
                    Circle().fill(Color.blue).frame(width: 8, height: 8)
                    Text(homeTeam)
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
                Spacer()
                HStack(spacing: 4) {
                    Circle().fill(Color.red).frame(width: 8, height: 8)
                    Text(awayTeam)
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
            }
            .padding(.horizontal, 4)
        }
        .padding()
        .background(Color(.secondarySystemGroupedBackground))
        .cornerRadius(16)
    }
}

// MARK: - 半圓形 Gauge 軌跡 Shape
struct GaugeTrackShape: Shape {
    var progress: Double = 0.0 // 0.0 ... 1.0
    
    func path(in rect: CGRect) -> Path {
        var path = Path()
        let width = rect.width
        let height = rect.height
        
        // 定義半圓曲線參數：從左側水平線（角度180度），到右側水平線（角度0度）
        let centerX = width / 2
        let centerY = height
        let radius = min(width / 2 - 16, height - 10)
        
        let startAngle = Angle.degrees(180)
        let endAngle: Angle
        if progress >= 1.0 {
            endAngle = Angle.degrees(0)
        } else {
            endAngle = Angle.degrees(180 - (progress * 180))
        }
        
        path.addArc(
            center: CGPoint(x: centerX, y: centerY),
            radius: radius,
            startAngle: startAngle,
            endAngle: endAngle,
            clockwise: false
        )
        
        return path
    }
}

#Preview {
    ConfidenceGaugeView(
        confidence: 0.72,
        scorePrediction: "4-2",
        homeTeam: "Yankees",
        awayTeam: "Red Sox"
    )
    .padding()
    .background(Color(.systemGray6))
}