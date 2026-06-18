import SwiftUI
import Combine

// MARK: - 主題管理器（深色/淺色切換）
class ThemeManager: ObservableObject {
    @AppStorage("isDarkMode") var isDarkMode: Bool = true {
        didSet {
            objectWillChange.send()
        }
    }
    
    var colorScheme: ColorScheme? {
        isDarkMode ? .dark : .light
    }
}

// MARK: - 主題顏色擴展（自動適應深色/淺色）
extension Color {
    /// 主卡片背景色
    static let cardBackground = Color(.secondarySystemBackground)
    /// 輔助卡片背景色（比主卡片略淺/深）
    static let cardSecondaryBackground = Color(.tertiarySystemBackground)
    /// 主文字色
    static let primaryText = Color(.label)
    /// 次要文字色
    static let secondaryText = Color(.secondaryLabel)
    /// 第三級文字色
    static let tertiaryText = Color(.tertiaryLabel)
}
