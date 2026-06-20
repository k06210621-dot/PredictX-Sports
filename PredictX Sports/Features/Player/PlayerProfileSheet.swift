//
//  PlayerProfileSheet.swift
//  PredictX Sports
//
//  球員資料 Sheet
//  - 顯示球員基本資料（頭像、位置、生日、身高體重）
//  - 顯示合約紀錄（NBA 完整）
//  - 顯示榮譽列表（獎項、明星賽）
//
//  從賽事詳情或球隊頁面點擊球員 → 開啟此 Sheet
//
//  Created: 2026-06-20
//

import SwiftUI

struct PlayerProfileSheet: View {
    let player: PlayerBasic
    @Environment(\.dismiss) private var dismiss

    @State private var detail: PlayerDetailResponse? = nil
    @State private var isLoading = true
    @State private var errorMessage: String? = nil

    var body: some View {
        NavigationStack {
            ZStack {
                Color(UIColor.systemBackground).ignoresSafeArea()

                if isLoading {
                    ProgressView("載入球員資料中...")
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
                    }
                } else if let detail = detail {
                    ScrollView {
                        VStack(spacing: 16) {
                            headerCard(player: detail.player)
                            basicInfoCard(player: detail.player)
                            if let contracts = detail.contracts, !contracts.isEmpty {
                                contractsCard(contracts: contracts)
                            }
                            if let honours = detail.honours, !honours.isEmpty {
                                honoursCard(honours: honours)
                            }
                            if let desc = detail.player.description, !desc.isEmpty {
                                descriptionCard(text: desc)
                            }
                        }
                        .padding()
                    }
                }
            }
            .navigationTitle(player.name)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("關閉") { dismiss() }
                }
            }
            .task {
                await loadDetail()
            }
        }
    }

    private func loadDetail() async {
        isLoading = true
        errorMessage = nil
        do {
            let result = try await APIService.shared.fetchPlayerDetail(playerId: player.id)
            self.detail = result
            self.isLoading = false
        } catch {
            self.errorMessage = "無法載入：\(error.localizedDescription)"
            self.isLoading = false
        }
    }

    // MARK: - 卡片

    private func headerCard(player: PlayerDetail) -> some View {
        VStack(spacing: 12) {
            // 球員頭像
            ZStack {
                Circle()
                    .fill(LinearGradient(
                        colors: [Color.blue.opacity(0.2), Color.purple.opacity(0.2)],
                        startPoint: .topLeading, endPoint: .bottomTrailing
                    ))
                    .frame(width: 110, height: 110)

                if let cutoutURL = player.cutout_url, let url = URL(string: cutoutURL) {
                    AsyncImage(url: url) { phase in
                        switch phase {
                        case .empty:
                            Text(player.name.prefix(1)).font(.system(size: 36, weight: .heavy)).foregroundColor(.blue)
                        case .success(let image):
                            image.resizable().scaledToFit().frame(width: 90, height: 90)
                        case .failure:
                            Text(player.name.prefix(1)).font(.system(size: 36, weight: .heavy)).foregroundColor(.blue)
                        @unknown default:
                            EmptyView()
                        }
                    }
                } else {
                    Text(String(player.name.prefix(1)))
                        .font(.system(size: 36, weight: .heavy))
                        .foregroundColor(.blue)
                }
            }
            .frame(width: 110, height: 110)

            VStack(spacing: 4) {
                Text(player.name)
                    .font(.title2.bold())
                    .foregroundColor(.primary)
                if let pos = player.position, !pos.isEmpty {
                    Text(pos)
                        .font(.subheadline)
                        .foregroundColor(.blue)
                }
                if let team = player.team, !team.isEmpty {
                    HStack(spacing: 4) {
                        Image(systemName: "shield.fill").font(.caption2)
                        Text(team).font(.caption)
                    }
                    .foregroundColor(.secondary)
                }
            }
        }
        .frame(maxWidth: .infinity)
        .padding()
        .background(Color.cardBackground)
        .cornerRadius(16)
    }

    private func basicInfoCard(player: PlayerDetail) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("基本資料", systemImage: "person.text.rectangle.fill")
                .font(.subheadline.bold())
                .foregroundColor(.blue)

            VStack(spacing: 6) {
                infoRow("國籍", value: player.nationality)
                infoRow("出生", value: player.birth_date)
                if let loc = player.birth_location {
                    infoRow("出生地", value: loc)
                }
                if let jersey = player.jersey_number {
                    infoRow("背號", value: "#\(jersey)")
                }
                if let height = player.height {
                    infoRow("身高", value: height)
                }
                if let weight = player.weight {
                    infoRow("體重", value: weight)
                }
            }
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.cardBackground)
        .cornerRadius(16)
    }

    private func infoRow(_ label: String, value: String?) -> some View {
        HStack(alignment: .top) {
            Text(label)
                .font(.caption)
                .foregroundColor(.secondary)
                .frame(width: 60, alignment: .leading)
            Text(value ?? "—")
                .font(.caption)
                .foregroundColor(.primary)
            Spacer()
        }
    }

    private func contractsCard(contracts: [PlayerContract]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("合約紀錄", systemImage: "doc.text.fill")
                .font(.subheadline.bold())
                .foregroundColor(.green)

            ForEach(Array(contracts.enumerated()), id: \.offset) { _, contract in
                HStack(spacing: 10) {
                    if let badge = contract.strBadge, let url = URL(string: badge) {
                        AsyncImage(url: url) { phase in
                            switch phase {
                            case .success(let image):
                                image.resizable().scaledToFit().frame(width: 24, height: 24)
                            default:
                                Image(systemName: "shield.fill").foregroundColor(.green)
                            }
                        }
                    }
                    VStack(alignment: .leading, spacing: 2) {
                        Text(contract.strTeam ?? "Unknown")
                            .font(.caption.bold())
                        if let start = contract.strYearStart, let end = contract.strYearEnd {
                            Text("\(start) - \(end)")
                                .font(.caption2)
                                .foregroundColor(.secondary)
                        }
                    }
                    Spacer()
                }
                .padding(.vertical, 4)
            }
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.cardBackground)
        .cornerRadius(16)
    }

    private func honoursCard(honours: [PlayerHonour]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("榮譽紀錄", systemImage: "trophy.fill")
                .font(.subheadline.bold())
                .foregroundColor(.yellow)

            VStack(alignment: .leading, spacing: 6) {
                ForEach(Array(honours.enumerated()), id: \.offset) { _, honour in
                    HStack(alignment: .top, spacing: 6) {
                        Image(systemName: "star.fill")
                            .font(.system(size: 10))
                            .foregroundColor(.yellow)
                            .padding(.top, 4)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(honour.strHonour ?? "Unknown")
                                .font(.caption)
                                .foregroundColor(.primary)
                            if let season = honour.strSeason {
                                Text(season)
                                    .font(.caption2)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                }
            }
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.cardBackground)
        .cornerRadius(16)
    }

    private func descriptionCard(text: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("球員簡介", systemImage: "book.fill")
                .font(.subheadline.bold())
                .foregroundColor(.indigo)

            Text(text)
                .font(.caption)
                .foregroundColor(.primary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.cardBackground)
        .cornerRadius(16)
    }
}
