//
//  TeamRosterView.swift
//  PredictX Sports
//
//  球隊球員名單頁
//  - 從賽事卡片可進入（透過球隊頭像）
//  - 顯示球隊 10 位球員（含頭像、位置、國籍）
//  - 點擊球員 → 開啟 PlayerProfileSheet
//
//  Created: 2026-06-20
//

import SwiftUI

struct TeamRosterView: View {
    let teamId: String
    let teamName: String
    @Environment(\.dismiss) private var dismiss

    @State private var roster: TeamRosterResponse? = nil
    @State private var selectedPlayer: PlayerBasic? = nil
    @State private var isLoading = true
    @State private var errorMessage: String? = nil

    var body: some View {
        NavigationStack {
            ZStack {
                Color(UIColor.systemBackground).ignoresSafeArea()

                if isLoading {
                    ProgressView("載入球員名單中...")
                        .progressViewStyle(CircularProgressViewStyle(tint: .blue))
                } else if let error = errorMessage {
                    VStack(spacing: 16) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .font(.system(size: 48))
                            .foregroundColor(.orange)
                        Text(error)
                            .multilineTextAlignment(.center)
                            .foregroundColor(.secondary)
                            .padding(.horizontal, 32)
                        Button("重試") {
                            Task { await loadRoster() }
                        }
                        .buttonStyle(.borderedProminent)
                    }
                } else if let roster = roster, !roster.players.isEmpty {
                    ScrollView {
                        VStack(spacing: 12) {
                            HStack {
                                Image(systemName: "person.2.fill")
                                    .foregroundColor(.blue)
                                Text("球員名單（\(roster.count) 位）")
                                    .font(.headline)
                                Spacer()
                            }
                            .padding(.horizontal, 4)

                            ForEach(roster.players) { player in
                                Button {
                                    selectedPlayer = player
                                } label: {
                                    PlayerRowCard(player: player)
                                }
                                .buttonStyle(.plain)
                            }

                            if roster.count < 5 {
                                footerCard
                            }
                        }
                        .padding()
                    }
                } else {
                    VStack(spacing: 12) {
                        Image(systemName: "person.crop.circle.badge.questionmark")
                            .font(.system(size: 56))
                            .foregroundColor(.gray)
                        Text("暫無球員資料")
                            .font(.headline)
                            .foregroundColor(.secondary)
                        Text("TheSportsDB 對此球隊資料不完整")
                            .font(.caption)
                            .foregroundColor(Color(.tertiaryLabel))
                    }
                }
            }
            .navigationTitle(teamName)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("關閉") { dismiss() }
                }
            }
            .task {
                await loadRoster()
            }
            .sheet(item: $selectedPlayer) { player in
                PlayerProfileSheet(player: player)
            }
        }
    }

    private func loadRoster() async {
        isLoading = true
        errorMessage = nil
        do {
            let result = try await APIService.shared.fetchTeamRoster(teamId: teamId)
            self.roster = result
            self.isLoading = false
        } catch {
            self.errorMessage = "無法載入：\(error.localizedDescription)"
            self.isLoading = false
        }
    }

    private var footerCard: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Image(systemName: "info.circle.fill")
                    .foregroundColor(.blue)
                Text("資料說明")
                    .font(.caption.bold())
                    .foregroundColor(.blue)
            }
            Text("TheSportsDB 免費版每隊最多回傳 10 位球員。如需完整名單，可升級至付費版。")
                .font(.caption2)
                .foregroundColor(.secondary)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.blue.opacity(0.08))
        .cornerRadius(12)
    }
}

// MARK: - 球員卡片

private struct PlayerRowCard: View {
    let player: PlayerBasic

    var body: some View {
        HStack(spacing: 12) {
            // 頭像
            ZStack {
                Circle()
                    .fill(LinearGradient(
                        colors: [Color.blue.opacity(0.2), Color.purple.opacity(0.2)],
                        startPoint: .topLeading, endPoint: .bottomTrailing
                    ))
                    .frame(width: 50, height: 50)

                if let cutout = player.cutout_url, let url = URL(string: cutout) {
                    AsyncImage(url: url) { phase in
                        switch phase {
                        case .success(let image):
                            image.resizable().scaledToFit().frame(width: 42, height: 42)
                        default:
                            Text(player.name.prefix(1))
                                .font(.system(size: 18, weight: .heavy))
                                .foregroundColor(.blue)
                        }
                    }
                } else {
                    Text(String(player.name.prefix(1)))
                        .font(.system(size: 18, weight: .heavy))
                        .foregroundColor(.blue)
                }
            }
            .frame(width: 50, height: 50)

            // 球員資訊
            VStack(alignment: .leading, spacing: 3) {
                Text(player.name)
                    .font(.subheadline.bold())
                    .foregroundColor(.primary)
                    .lineLimit(1)
                HStack(spacing: 6) {
                    if let pos = player.position, !pos.isEmpty {
                        Tag(text: pos, color: .blue)
                    }
                    if let nat = player.nationality, !nat.isEmpty {
                        Text(nat)
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                }
            }

            Spacer()

            // 箭頭
            Image(systemName: "chevron.right")
                .font(.system(size: 12))
                .foregroundColor(Color(.tertiaryLabel))
        }
        .padding(10)
        .background(Color.cardBackground)
        .cornerRadius(12)
    }
}

// 小標籤元件
private struct Tag: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(.system(size: 9, weight: .bold))
            .foregroundColor(color)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(color.opacity(0.15))
            .cornerRadius(4)
    }
}
