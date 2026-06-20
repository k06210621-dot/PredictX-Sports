import SwiftUI

/// 歷史賽事搜尋 + 篩選工具列
/// - 搜尋框：以球隊英文 / 中文暱稱過濾
/// - 聯賽 chips：「全部」+ 五大聯賽
/// - 日期區段：近 7 天 / 近 30 天 / 全部
struct HistoryFilterBar: View {
    @Binding var searchText: String
    @Binding var selectedLeague: LeagueFilter
    @Binding var dateRange: DateRangeFilter

    var body: some View {
        VStack(spacing: 10) {
            // 1. 搜尋框
            HStack(spacing: 8) {
                Image(systemName: "magnifyingglass")
                    .foregroundColor(.secondary)
                TextField("搜尋球隊（中文／英文）", text: $searchText)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .foregroundColor(.primary)
                if !searchText.isEmpty {
                    Button {
                        searchText = ""
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundColor(.secondary)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 12)
            .background(Color.cardBackground.opacity(0.7))
            .cornerRadius(16)

            // 2. 聯賽 chips
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 10) {
                    ForEach(LeagueType.allCases) { lg in
                        LeagueChip(label: leagueShortName(lg),
                                  icon: leagueIcon(lg),
                                  isSelected: selectedLeague == .specific(lg)) {
                            selectedLeague = .specific(lg)
                        }
                    }
                }
            }

            // 3. 日期區段
            HStack(spacing: 8) {
                ForEach(DateRangeFilter.allCases) { range in
                    DateChip(label: range.label,
                             isSelected: dateRange == range) {
                        dateRange = range
                    }
                }
            }
        }
        .padding(.horizontal)
        .padding(.top, 4)
        .padding(.bottom, 8)
    }

    private func leagueShortName(_ lg: LeagueType) -> String {
        switch lg {
        case .mlb: return "MLB"
        case .npb: return "NPB"
        case .cpbl: return "CPBL"
        case .nba: return "NBA"
        }
    }

    private func leagueIcon(_ lg: LeagueType) -> String {
        switch lg {
        case .mlb: return "⚾️"
        case .npb: return "⚾️"
        case .cpbl: return "⚾️"
        case .nba: return "🏀"
        }
    }
}

enum LeagueFilter: Equatable {
    case all
    case specific(LeagueType)

    var isAll: Bool { self == .all }

    static func == (lhs: LeagueFilter, rhs: LeagueFilter) -> Bool {
        switch (lhs, rhs) {
        case (.all, .all): return true
        case (.specific(let a), .specific(let b)): return a == b
        default: return false
        }
    }

    func unwrap() -> LeagueType? {
        if case .specific(let lg) = self { return lg }
        return nil
    }
}

enum DateRangeFilter: String, CaseIterable, Identifiable {
    case last7 = "7d"
    case last30 = "30d"
    case all = "all"

    var id: String { rawValue }

    var label: String {
        switch self {
        case .last7: return "近 7 天"
        case .last30: return "近 30 天"
        case .all: return "全部"
        }
    }

    var days: Int? {
        switch self {
        case .last7: return 7
        case .last30: return 30
        case .all: return nil
        }
    }
}

struct LeagueChip: View {
    let label: String
    let icon: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 6) {
                Text(icon)
                    .font(.system(size: 16))
                Text(label)
                    .font(.system(size: 16, weight: .semibold))
            }
            .padding(.horizontal, 18)
            .padding(.vertical, 12)
            .background(isSelected ? Color.accentColor : Color.cardBackground.opacity(0.6))
            .foregroundColor(isSelected ? .white : .primary)
            .cornerRadius(16)
            .overlay(
                RoundedRectangle(cornerRadius: 20)
                    .stroke(isSelected ? Color.accentColor : Color.gray.opacity(0.3), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }
}

struct DateChip: View {
    let label: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(label)
                .font(.caption2)
                .fontWeight(.semibold)
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(isSelected ? Color.accentColor.opacity(0.85) : Color.cardBackground.opacity(0.5))
                .foregroundColor(isSelected ? .white : .secondary)
                .cornerRadius(16)
        }
        .buttonStyle(.plain)
    }
}