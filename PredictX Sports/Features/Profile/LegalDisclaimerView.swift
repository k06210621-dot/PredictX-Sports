import SwiftUI

// MARK: — PredictX Sports 法律聲明頁面
struct LegalDisclaimerView: View {
    @State private var expandedSection: String? = "section1"
    
    private let appVersion = "1.0.0"
    
    var body: some View {
        ScrollView(.vertical, showsIndicators: false) {
            LazyVStack(spacing: 14) {
                // MARK: 標題區域
                headerSection
                
                // MARK: 可展開的章節區塊
                ForEach(sections) { section in
                    DisclosureGroup(
                        isExpanded: Binding(
                            get: { expandedSection == section.id },
                            set: { isExpanded in
                                withAnimation(.spring(response: 0.35, dampingFraction: 0.85)) {
                                    expandedSection = isExpanded ? section.id : nil
                                }
                            }
                        ),
                        content: {
                            VStack(alignment: .leading, spacing: 12) {
                                ForEach(section.paragraphs.indices, id: \.self) { index in
                                    let paragraph = section.paragraphs[index]
                                    
                                    if paragraph.isBullet {
                                        bulletRow(icon: paragraph.icon ?? "circle.fill",
                                                  text: paragraph.text,
                                                  iconColor: paragraph.iconColor ?? .blue)
                                    } else if paragraph.isButton {
                                        buttonRow(title: paragraph.text, action: paragraph.action)
                                    } else if paragraph.isLink {
                                        linkRow(text: paragraph.text, url: paragraph.linkURL)
                                    } else {
                                        bodyText(paragraph.text)
                                    }
                                }
                            }
                            .padding(.top, 8)
                        },
                        label: {
                            sectionLabel(icon: section.icon,
                                         title: section.title,
                                         color: section.color)
                        }
                    )
                    .padding()
                    .background(Color(.secondarySystemGroupedBackground))
                    .cornerRadius(16)
                    .shadow(color: Color.black.opacity(0.03), radius: 4, x: 0, y: 2)
                }
                
                // MARK: 底部版權資訊
                footerSection
            }
            .padding()
        }
        .background(Color(.systemGroupedBackground).ignoresSafeArea())
        .navigationTitle("法律聲明")
        .navigationBarTitleDisplayMode(.inline)
    }
    
    // MARK: - 標題
    private var headerSection: some View {
        VStack(spacing: 6) {
            Text("法律聲明")
                .font(.largeTitle.bold())
                .foregroundColor(.primary)
            
            Text("PredictX Sports Legal Disclaimer")
                .font(.subheadline)
                .foregroundColor(.secondary)
            
            Rectangle()
                .fill(Color.blue.opacity(0.3))
                .frame(height: 3)
                .frame(width: 60)
                .cornerRadius(1.5)
                .padding(.top, 4)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
    }
    
    // MARK: - 章節標籤
    private func sectionLabel(icon: String, title: String, color: Color) -> some View {
        HStack(spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: 10)
                    .fill(color.opacity(0.12))
                    .frame(width: 36, height: 36)
                Image(systemName: icon)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(color)
            }
            
            Text(title)
                .font(.headline.bold())
                .foregroundColor(.primary)
        }
    }
    
    // MARK: - 內文
    private func bodyText(_ text: String) -> some View {
        Text(text)
            .font(.subheadline)
            .foregroundColor(.secondary)
            .lineSpacing(4)
            .fixedSize(horizontal: false, vertical: true)
    }
    
    // MARK: - 項目符號行
    private func bulletRow(icon: String, text: String, iconColor: Color) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: icon)
                .font(.system(size: 8))
                .foregroundColor(iconColor)
                .padding(.top, 6)
            Text(text)
                .font(.subheadline)
                .foregroundColor(.secondary)
                .lineSpacing(3)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
    
    // MARK: - 按鈕行
    private func buttonRow(title: String, action: (() -> Void)?) -> some View {
        Button(action: { action?() }) {
            HStack {
                Image(systemName: "shield.checkered")
                    .font(.caption)
                    .foregroundColor(.blue)
                Text(title)
                    .font(.subheadline.bold())
                    .foregroundColor(.blue)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption2)
                    .foregroundColor(.blue.opacity(0.5))
            }
            .padding(.vertical, 12)
            .padding(.horizontal, 16)
            .background(Color.blue.opacity(0.06))
            .cornerRadius(16)
        }
    }
    
    // MARK: - 連結行
    private func linkRow(text: String, url: String?) -> some View {
        HStack(spacing: 8) {
            Image(systemName: "envelope.fill")
                .font(.caption)
                .foregroundColor(.blue)
            Text(text)
                .font(.subheadline)
                .foregroundColor(.blue)
                .underline()
        }
        .padding(.vertical, 4)
    }
    
    // MARK: - 底部版權
    private var footerSection: some View {
        VStack(spacing: 6) {
            Text("© 2026 PredictX Sports")
                .font(.caption.bold())
                .foregroundColor(.primary)
            Text("All Rights Reserved.")
                .font(.caption2)
                .foregroundColor(.secondary)
            Text("Version \(appVersion)")
                .font(.caption2)
                .foregroundColor(.secondary.opacity(0.7))
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 20)
    }
}

// MARK: - 章節資料模型
private struct DisclaimerSection: Identifiable {
    let id: String
    let icon: String
    let title: String
    let color: Color
    let paragraphs: [ParagraphItem]
}

private struct ParagraphItem {
    let text: String
    let isBullet: Bool
    let isButton: Bool
    let isLink: Bool
    let icon: String?
    let iconColor: Color?
    let linkURL: String?
    let action: (() -> Void)?
    
    init(text: String) {
        self.text = text
        self.isBullet = false
        self.isButton = false
        self.isLink = false
        self.icon = nil
        self.iconColor = nil
        self.linkURL = nil
        self.action = nil
    }
    
    init(bullet text: String, icon: String = "circle.fill", color: Color = .blue) {
        self.text = text
        self.isBullet = true
        self.isButton = false
        self.isLink = false
        self.icon = icon
        self.iconColor = color
        self.linkURL = nil
        self.action = nil
    }
    
    init(button title: String, action: (() -> Void)? = nil) {
        self.text = title
        self.isBullet = false
        self.isButton = true
        self.isLink = false
        self.icon = nil
        self.iconColor = nil
        self.linkURL = nil
        self.action = action
    }
    
    init(link text: String, url: String) {
        self.text = text
        self.isBullet = false
        self.isButton = false
        self.isLink = true
        self.icon = nil
        self.iconColor = nil
        self.linkURL = url
        self.action = nil
    }
}

// MARK: - 章節定義
private var sections: [DisclaimerSection] {
    [
        // 1. 服務性質說明
        DisclaimerSection(
            id: "section1",
            icon: "info.circle.fill",
            title: "1. 服務性質說明",
            color: .blue,
            paragraphs: [
                ParagraphItem(text: "PredictX Sports 為 AI 運動數據分析平台，提供以下服務："),
                ParagraphItem(bullet: "運動賽事數據分析", icon: "chart.bar.fill", color: .blue),
                ParagraphItem(bullet: "歷史統計資料查詢", icon: "clock.arrow.circlepath", color: .blue),
                ParagraphItem(bullet: "AI 模型推論結果", icon: "brain.head.profile", color: .blue),
                ParagraphItem(bullet: "球隊與球員資訊", icon: "person.3.fill", color: .blue),
                ParagraphItem(text: "本平台所提供之所有資訊、數據、分析結果及 AI 推論內容，僅供使用者參考，不作為任何形式之決策依據。使用者應自行評估並承擔使用本平台服務所產生之所有風險。")
            ]
        ),
        
        // 2. AI 分析免責聲明
        DisclaimerSection(
            id: "section2",
            icon: "cpu.fill",
            title: "2. AI 分析免責聲明",
            color: .purple,
            paragraphs: [
                ParagraphItem(text: "AI 推論結果係依據以下資料產生："),
                ParagraphItem(bullet: "歷史賽事數據", icon: "list.clipboard", color: .purple),
                ParagraphItem(bullet: "球員與球隊資訊", icon: "person.text.rectangle", color: .purple),
                ParagraphItem(bullet: "過往賽事紀錄", icon: "trophy.fill", color: .purple),
                ParagraphItem(bullet: "統計數學模型", icon: "function", color: .purple),
                ParagraphItem(bullet: "機器學習演算法", icon: "gearshape.2.fill", color: .purple),
                ParagraphItem(text: "本平台不保證 AI 推論結果之："),
                ParagraphItem(bullet: "正確性（Accuracy）", icon: "exclamationmark.triangle", color: .orange),
                ParagraphItem(bullet: "完整性（Completeness）", icon: "exclamationmark.triangle", color: .orange),
                ParagraphItem(bullet: "即時性（Timeliness）", icon: "exclamationmark.triangle", color: .orange),
                ParagraphItem(bullet: "精準率（Precision）", icon: "exclamationmark.triangle", color: .orange),
                ParagraphItem(text: "任何 AI 分析結果均不構成對賽事結果之保證。實際賽事結果受多種不可預測因素影響，包括但不限於球員狀態、天氣條件、裁判判決及突發事件。")
            ]
        ),
        
        // 3. 非博彩工具聲明
        DisclaimerSection(
            id: "section3",
            icon: "hand.raised.fill",
            title: "3. 非博彩工具聲明",
            color: .red,
            paragraphs: [
                ParagraphItem(text: "PredictX Sports 明確聲明本平台："),
                ParagraphItem(bullet: "不提供任何投注功能", icon: "xmark.circle.fill", color: .red),
                ParagraphItem(bullet: "不提供任何下注服務", icon: "xmark.circle.fill", color: .red),
                ParagraphItem(bullet: "不提供任何資金交易", icon: "xmark.circle.fill", color: .red),
                ParagraphItem(bullet: "不提供任何賠率資訊", icon: "xmark.circle.fill", color: .red),
                ParagraphItem(text: "本平台之所有功能及內容，僅限於運動賽事數據分析與統計研究用途。使用者須自行了解並遵守所在地之相關法律規範。若使用者所在地法律禁止或限制運動數據分析工具之使用，使用者應立即停止使用本平台服務。"),
                ParagraphItem(text: "嚴禁未成年人使用本平台進行任何與博弈相關之行為。")
            ]
        ),
        
        // 4. 投資與決策風險聲明
        DisclaimerSection(
            id: "section4",
            icon: "exclamationmark.shield.fill",
            title: "4. 投資與決策風險聲明",
            color: .orange,
            paragraphs: [
                ParagraphItem(text: "使用者因依據本平台提供之以下內容所作出的任何決策："),
                ParagraphItem(bullet: "AI 分析結果", icon: "brain", color: .orange),
                ParagraphItem(bullet: "統計數據", icon: "chart.xyaxis.line", color: .orange),
                ParagraphItem(bullet: "AI 推論分析", icon: "forward.fill", color: .orange),
                ParagraphItem(bullet: "歷史資料", icon: "clock.fill", color: .orange),
                ParagraphItem(text: "包括但不限於以下行為所產生之任何損失："),
                ParagraphItem(bullet: "投資決策", icon: "dollarsign.circle", color: .red),
                ParagraphItem(bullet: "博彩行為", icon: "suit.spade.fill", color: .red),
                ParagraphItem(bullet: "商業決策", icon: "building.columns.fill", color: .red),
                ParagraphItem(bullet: "個人選擇", icon: "person.fill", color: .red),
                ParagraphItem(text: "PredictX Sports、其開發團隊、關聯公司及員工，均不負任何法律責任。使用者應對自身決策負完全責任。")
            ]
        ),
        
        // 5. 數據來源聲明
        DisclaimerSection(
            id: "section5",
            icon: "antenna.radiowaves.left.and.right",
            title: "5. 數據來源聲明",
            color: .green,
            paragraphs: [
                ParagraphItem(text: "本平台之資料可能來自以下來源："),
                ParagraphItem(bullet: "官方聯盟提供之數據", icon: "building.columns", color: .green),
                ParagraphItem(bullet: "公開資訊與統計資料", icon: "book.fill", color: .green),
                ParagraphItem(bullet: "合法授權之第三方 API", icon: "link.circle.fill", color: .green),
                ParagraphItem(bullet: "經授權之數據合作夥伴", icon: "handshake.fill", color: .green),
                ParagraphItem(text: "本平台提及之聯賽、球隊及組織包含但不限於："),
                ParagraphItem(bullet: "NBA（美國職業籃球協會）", icon: "basketball.fill", color: .orange),
                ParagraphItem(bullet: "MLB（美國職業棒球大聯盟）", icon: "baseball.fill", color: .blue),
                ParagraphItem(bullet: "NPB（日本職業棒球組織）", icon: "flag.fill", color: .yellow),
                ParagraphItem(bullet: "CPBL（中華職業棒球聯盟）", icon: "flag.fill", color: .green),
                ParagraphItem(text: "上述聯盟之名稱、商標、標誌、球隊名稱、隊徽、球員姓名及相關智慧財產權，均屬各權利人所有。本平台使用該等資訊僅基於數據分析與資訊呈現目的，不代表與各聯盟有任何合作或隸屬關係。")
            ]
        ),
        
        // 6. Premium 會員與虛擬商品條款
        DisclaimerSection(
            id: "section6",
            icon: "crown.fill",
            title: "6. Premium 會員與虛擬商品條款",
            color: .yellow,
            paragraphs: [
                ParagraphItem(text: "本平台提供以下付費服務與虛擬商品："),
                ParagraphItem(bullet: "Premium 會員訂閱服務", icon: "crown.fill", color: .yellow),
                ParagraphItem(bullet: "AI 額度儲值中心（虛擬點數）", icon: "bag.fill", color: .yellow),
                ParagraphItem(bullet: "AI 分析使用額度", icon: "cpu.fill", color: .yellow),
                ParagraphItem(bullet: "其他數位內容", icon: "square.grid.2x2.fill", color: .yellow),
                ParagraphItem(text: "數位商品與虛擬點數一經購買、開通或使用後，除法律另有規定外，不得要求退款、轉讓或兌換現金。"),
                ParagraphItem(text: "Premium 會員訂閱將依 Apple App Store 或 Google Play 之訂閱機制進行週期性扣款。使用者可隨時透過帳號設定管理或取消訂閱。取消訂閱後，已付費期間之會員權益仍持續至該期結束。"),
                ParagraphItem(text: "本平台保留調整商品價格、內容及權益之權利，變更時將依相關法規進行公告。")
            ]
        ),
        
        // 7. 系統可用性聲明
        DisclaimerSection(
            id: "section7",
            icon: "wifi.slash",
            title: "7. 系統可用性聲明",
            color: .gray,
            paragraphs: [
                ParagraphItem(text: "本平台之服務可能因以下因素而中斷、延遲或出現異常："),
                ParagraphItem(bullet: "網路連線異常", icon: "wifi.exclamationmark", color: .gray),
                ParagraphItem(bullet: "API 服務故障", icon: "exclamationmark.icloud", color: .gray),
                ParagraphItem(bullet: "系統定期維護", icon: "gear", color: .gray),
                ParagraphItem(bullet: "第三方服務中斷", icon: "link.circle.badge.plus", color: .gray),
                ParagraphItem(bullet: "資料傳輸延遲", icon: "clock.badge.exclamationmark", color: .gray),
                ParagraphItem(text: "上述因素可能導致："),
                ParagraphItem(bullet: "AI 分析失敗", icon: "xmark.octagon", color: .orange),
                ParagraphItem(bullet: "推論結果延遲", icon: "hourglass", color: .orange),
                ParagraphItem(bullet: "賽事資料缺漏", icon: "doc.text.magnifyingglass", color: .orange),
                ParagraphItem(bullet: "部分功能暫停", icon: "pause.circle", color: .orange),
                ParagraphItem(text: "PredictX Sports 不保證服務全年無中斷運行，亦不就因服務中斷所致之任何損失負賠償責任。本平台將盡合理努力維持服務穩定性，惟不構成保證義務。")
            ]
        ),
        
        // 8. 智慧財產權聲明
                DisclaimerSection(
                    id: "section8",
                    icon: "lock.fill",
                    title: "8. 智慧財產權聲明",
                    color: .indigo,
                    paragraphs: [
                        ParagraphItem(text: "PredictX Sports 應用程式內之所有內容，包括但不限於："),
                        ParagraphItem(bullet: "使用者介面設計與佈局", icon: "rectangle.3.group.fill", color: .indigo),
                        ParagraphItem(bullet: "AI 分析內容與演算法", icon: "brain.head.profile", color: .indigo),
                        ParagraphItem(bullet: "應用程式原始碼", icon: "curlybraces", color: .indigo),
                        ParagraphItem(bullet: "數據圖表與視覺化呈現", icon: "chart.pie.fill", color: .indigo),
                        ParagraphItem(bullet: "文字內容與編排", icon: "doc.text.fill", color: .indigo),
                        ParagraphItem(text: "均受著作權法、商標法及相關智慧財產權法律之保護。"),
                        ParagraphItem(text: "未經 PredictX Sports 明確書面授權，任何人不得："),
                        ParagraphItem(bullet: "重製、改作或翻譯本平台內容", icon: "doc.on.doc", color: .red),
                        ParagraphItem(bullet: "散布、公開傳輸或展示", icon: "square.and.arrow.up", color: .red),
                        ParagraphItem(bullet: "出租、租賃或為商業目的使用", icon: "bag.badge.plus", color: .red),
                        ParagraphItem(bullet: "逆向工程、解編譯或拆解", icon: "hammer.fill", color: .red),
                        ParagraphItem(text: "違反上述規定者，本平台將依法追究相關法律責任。")
                    ]
                ),
        
                // 9. 隱私權政策
                DisclaimerSection(
                    id: "section9",
                    icon: "hand.raised.fill",
                    title: "9. 隱私權政策",
                    color: .mint,
                    paragraphs: [
                        ParagraphItem(text: "PredictX Sports 重視您的隱私權。本節摘要說明我們如何收集、使用及保護您的資料。完整政策請參閱下方連結。"),
                        ParagraphItem(text: "我們收集的資料類型："),
                        ParagraphItem(bullet: "APNs 推播識別碼：您開啟推播時系統產生的 device token（用於發送高信心度賽事推播）", icon: "applelogo", color: .mint),
                        ParagraphItem(bullet: "訂閱資訊：透過 Apple StoreKit 處理的訂閱等級（Free / Basic / Standard / Premium）", icon: "creditcard.fill", color: .mint),
                        ParagraphItem(bullet: "推論觀看歷史：您查看過的 AI 推論結果（用於個人化驗證率統計）", icon: "chart.line.uptrend.xyaxis", color: .mint),
                        ParagraphItem(bullet: "廣告識別碼 (IDFA)：僅在您同意時用於 Google AdMob 個人化廣告", icon: "rectangle.advertised", color: .mint),
                        ParagraphItem(text: "我們不會收集的資料："),
                        ParagraphItem(bullet: "個人身分識別資訊（email、姓名、Apple ID 個資）", icon: "person.slash.fill", color: .green),
                        ParagraphItem(bullet: "地理位置資訊", icon: "location.slash.fill", color: .green),
                        ParagraphItem(bullet: "聯絡人、照片或裝置儲存內容", icon: "lock.shield.fill", color: .green),
                        ParagraphItem(bullet: "iOS 版本、機型等裝置資訊", icon: "iphone.slash", color: .green),
                        ParagraphItem(text: "本地儲存（僅存於您裝置）："),
                        ParagraphItem(bullet: "收藏的隊伍、深色模式偏好、解鎖的賽事（儲存於 iOS UserDefaults）", icon: "internaldrive.fill", color: .blue),
                        ParagraphItem(text: "資料保留期限："),
                        ParagraphItem(bullet: "APNs 推播 token：保留至您解除安裝 App 或手動關閉推播", icon: "clock.fill", color: .blue),
                        ParagraphItem(bullet: "推論觀看歷史：保留 90 天後自動刪除", icon: "calendar.badge.clock", color: .blue),
                        ParagraphItem(bullet: "本地偏好設定：隨時可透過解除安裝 App 清除", icon: "trash.fill", color: .blue),
                        ParagraphItem(text: "第三方服務："),
                        ParagraphItem(bullet: "Apple StoreKit：處理訂閱付款", icon: "applelogo", color: .gray),
                        ParagraphItem(bullet: "Google AdMob：顯示廣告（含 Google User Messaging Platform 處理同意聲明）", icon: "g.circle.fill", color: .gray),
                        ParagraphItem(bullet: "雲端後端 API：提供賽事資料與 AI 推論", icon: "cloud.fill", color: .gray),
                        ParagraphItem(text: "您的權利：您可隨時透過 iOS 設定 → Apple ID → 訂閱管理訂閱，或透過 iOS 設定 → 隱私權 → 追蹤關閉個人化廣告。如需查詢、修改或刪除您的資料，請聯繫客服。"),
                        ParagraphItem(link: "查看完整隱私權政策（外部連結）", url: "https://k06210621-dot.github.io/privacy/"),
                        ParagraphItem(link: "查看完整使用條款（Apple 標準 EULA）", url: "https://www.apple.com/legal/internet-services/itunes/dev/stdeula/")
                    ]
                ),
        
        // 10. 法律適用與管轄
        DisclaimerSection(
            id: "section10",
            icon: "building.columns.fill",
            title: "10. 法律適用與管轄",
            color: .indigo,
            paragraphs: [
                ParagraphItem(text: "本協議之解釋、效力及爭議解決，均適用中華民國（台灣）法律。"),
                ParagraphItem(text: "因本協議所生之任何爭議，雙方應先本於誠信原則協商解決。協商不成時，以台灣台北地方法院為第一審管轄法院。"),
                ParagraphItem(text: "若本協議之部分條款被認定為無效或無法執行，不影響其他條款之效力。"),
            ]
        ),
        
        // 11. 協議修改與不可抗力
        DisclaimerSection(
            id: "section11",
            icon: "doc.text.fill",
            title: "11. 協議修改與不可抗力",
            color: .gray,
            paragraphs: [
                ParagraphItem(text: "協議修改權："),
                ParagraphItem(text: "PredictX Sports 保留隨時修改本協議條款之權利。修改後之條款將於 App 更新時生效。使用者繼續使用本服務即視為同意修改後之條款。"),
                ParagraphItem(text: "不可抗力免責："),
                ParagraphItem(text: "因天災、戰爭、政府行為、疫情、第三方服務中斷、網路攻擊、系統異常等不可抗力因素，導致服務中斷、資料遺失或功能異常，PredictX Sports 不負賠償責任。"),
                ParagraphItem(text: "本平台將盡合理努力在不可抗力事件發生後儘速恢復服務，惟不構成保證義務。"),
            ]
        ),
        
    ]
}

// MARK: - Preview
#Preview {
    NavigationStack {
        LegalDisclaimerView()
    }
}