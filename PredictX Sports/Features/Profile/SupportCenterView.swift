import SwiftUI
import MessageUI

// MARK: - 客服中心
struct SupportCenterView: View {
    @State private var showMailComposer = false
    @State private var showMailAlert = false
    
    private let supportEmail = "k06210621+PredictXSports@gmail.com"
    
    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                // MARK: ① 常見問題 FAQ
                FAQSection()
                
                // MARK: ② 聯絡客服（含意見回饋功能）
                ContactSection(
                    showMailComposer: $showMailComposer,
                    showMailAlert: $showMailAlert,
                    supportEmail: supportEmail
                )
            }
            .padding()
        }
        .background(Color(.systemGroupedBackground).ignoresSafeArea())
        .navigationTitle("客服中心")
        .navigationBarTitleDisplayMode(.large)
        .sheet(isPresented: $showMailComposer) {
            MailComposerView(
                to: supportEmail,
                subject: "PredictX Sports 問題回報",
                body: "\n\n---\nApp 版本：1.0.0\niOS 版本：\(UIDevice.current.systemVersion)"
            )
        }
        .alert("無法寄送郵件", isPresented: $showMailAlert) {
            Button("複製 Email", role: .none) {
                UIPasteboard.general.string = supportEmail
            }
            Button("確定", role: .cancel) {}
        } message: {
            Text("請將您的問題寄送至：\n\(supportEmail)")
        }
    }
}

// MARK: - 常見問題
struct FAQSection: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader(title: "常見問題 FAQ", icon: "questionmark.circle.fill")
                .padding(.bottom, 4)
            
            // AI 分析相關
            FAQCategory(title: "AI 分析相關", icon: "cpu.fill", iconColor: .blue) {
                FAQItem(question: "AI 推論機率是如何計算的？") {
                    Text("AI 推論機率是根據即時數據（球隊近況、對戰紀錄、投手/打擊數據、天氣等 50+ 項特徵）輸入語言模型後，經由 Prompt 推論得出的分析結果。系統會持續與實際比賽結果比對，計算長期驗證率。")
                }
                FAQItem(question: "AI 信心值代表什麼？") {
                    Text("信心值為 1-10 的整數評分，代表 AI 模型對該場推論的確信程度。信心值越高（≥8），表示模型掌握的數據越充分、勝負傾向越明確。僅信心值 ≥9 的推論才會顯示於「AI 重點觀察賽事」焦點區。")
                }
                FAQItem(question: "為什麼推論結果會改變？") {
                    Text("賽前數據會持續更新（例如先發投手變動、最新傷兵消息、天氣變化等），AI 模型會根據最新的即時數據重新分析，因此推論結果可能隨時間微調。")
                }
                FAQItem(question: "為什麼實際比賽結果和推論不同？") {
                    Text("運動比賽本身存在不可預測性（運氣、裁判判決、突發傷病等）。AI 推論是基於統計與數據模型的觀察，並非保證結果。本平台的目標是提供長期高於隨機基準的模型驗證率，而非每場 100% 準確。")
                }
            }
            
            // 會員相關
            FAQCategory(title: "會員相關", icon: "crown.fill", iconColor: .yellow) {
                FAQItem(question: "Premium 會員有哪些功能？") {
                    Text("Premium 會員可享有：① AI 賽事分析可全部查看 ② AI 重點觀察賽事查看 ④ 歷史驗證率圖表 ⑤ 無廣告體驗。更多功能將陸續推出。")
                }
                FAQItem(question: "訂閱後多久生效？") {
                    Text("訂閱完成後立即生效，不需等待。您可在「個人資訊」頁面查看會員卡片上的有效期限。")
                }
                FAQItem(question: "如何取消訂閱？") {
                    Text("請至 iPhone「設定」> 點擊您的 Apple ID >「訂閱項目」，選擇 PredictX Sports 後點擊「取消訂閱」即可。取消後仍可使用剩餘的訂閱期間。")
                }
                FAQItem(question: "如何恢復購買？") {
                    Text("若已付費但未解鎖 Premium，請點擊「訂閱中心」>「恢復購買」，系統會自動驗證您的 Apple ID 歷史交易記錄。")
                }
            }
            
            // 資料相關
            FAQCategory(title: "資料相關", icon: "doc.text.fill", iconColor: .orange) {
                FAQItem(question: "賽事多久更新一次？") {
                    Text("賽事前 24 小時即會載入排程。通常每 日更新兩次，實際頻率依各聯賽 API 而定。")
                }
                FAQItem(question: "支援哪些聯賽？") {
                    Text("目前支援：MLB（美國職棒）、NPB（日本職棒）、CPBL（中華職棒）、NBA（美國職籃）四大聯賽。更多聯賽將陸續新增。")
                }
                FAQItem(question: "為什麼某些比賽沒有 AI 分析？") {
                    Text("原因可能為：① 比賽尚未進入可分析的時間窗口（通常賽前 24 小時內）② 該場資料不足（例如新成立的隊伍尚無歷史數據）③ 該聯賽 API 暫時無法取得所需數據。")
                }
            }
        }
    }
}

// MARK: - 聯絡客服（含意見回饋功能）
struct ContactSection: View {
    @Binding var showMailComposer: Bool
    @Binding var showMailAlert: Bool
    let supportEmail: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader(title: "聯絡客服", icon: "headphones")
                .padding(.bottom, 4)
            
            VStack(spacing: 12) {
                // 寄送郵件按鈕
                Button(action: {
                    if MFMailComposeViewController.canSendMail() {
                        showMailComposer = true
                    } else {
                        showMailAlert = true
                    }
                }) {
                    HStack(spacing: 14) {
                        ZStack {
                            RoundedRectangle(cornerRadius: 12)
                                .fill(Color.blue.opacity(0.12))
                                .frame(width: 44, height: 44)
                            Image(systemName: "envelope.fill")
                                .font(.body)
                                .foregroundColor(.blue)
                        }
                        
                        VStack(alignment: .leading, spacing: 2) {
                            Text("寄送郵件")
                                .font(.subheadline)
                                .fontWeight(.semibold)
                                .foregroundColor(.primary)
                            Text(supportEmail)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        
                        Spacer()
                        
                        Image(systemName: "chevron.right")
                            .font(.caption)
                            .foregroundColor(.secondary.opacity(0.5))
                    }
                    .padding()
                    .background(Color(.systemBackground))
                    .cornerRadius(16)
                }
                .buttonStyle(PlainButtonStyle())
                
                // 回應時間提示
                HStack(spacing: 12) {
                    Image(systemName: "clock.fill")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text("我們通常會在 24-48 小時內回覆您的來信")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .padding(.horizontal, 4)
            }
        }
    }
}

// MARK: - 子元件

struct SectionHeader: View {
    let title: String
    let icon: String
    
    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
                .font(.subheadline)
                .foregroundColor(.blue)
            Text(title)
                .font(.headline)
                .fontWeight(.bold)
        }
    }
}

struct FAQCategory<Content: View>: View {
    let title: String
    let icon: String
    let iconColor: Color
    @ViewBuilder let content: Content
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.caption)
                    .foregroundColor(iconColor)
                Text(title)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(.secondary)
            }
            .padding(.horizontal, 4)
            
            VStack(spacing: 8) {
                content
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: Color.black.opacity(0.03), radius: 4, x: 0, y: 2)
    }
}

struct FAQItem<Content: View>: View {
    let question: String
    @ViewBuilder let answer: Content
    @State private var isExpanded = false
    
    var body: some View {
        VStack(spacing: 0) {
            Button(action: {
                withAnimation(.easeInOut(duration: 0.2)) {
                    isExpanded.toggle()
                }
            }) {
                HStack(spacing: 12) {
                    Text(question)
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(.primary)
                        .multilineTextAlignment(.leading)
                    
                    Spacer()
                    
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .font(.caption2)
                        .foregroundColor(.secondary.opacity(0.6))
                }
                .padding(.vertical, 12)
                .padding(.horizontal, 4)
            }
            
            if isExpanded {
                answer
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .padding(.horizontal, 4)
                    .padding(.bottom, 12)
                    .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .background(Color(.systemBackground))
    }
}

// MARK: - Mail Compose View (僅模擬器需 fallback)
struct MailComposerView: UIViewControllerRepresentable {
    let to: String
    let subject: String
    let body: String
    
    func makeUIViewController(context: Context) -> MFMailComposeViewController {
        let vc = MFMailComposeViewController()
        vc.setToRecipients([to])
        vc.setSubject(subject)
        vc.setMessageBody(body, isHTML: false)
        vc.mailComposeDelegate = context.coordinator
        return vc
    }
    
    func updateUIViewController(_ uiViewController: MFMailComposeViewController, context: Context) {}
    
    func makeCoordinator() -> Coordinator {
        Coordinator()
    }
    
    class Coordinator: NSObject, MFMailComposeViewControllerDelegate {
        func mailComposeController(_ controller: MFMailComposeViewController, didFinishWith result: MFMailComposeResult, error: Error?) {
            controller.dismiss(animated: true)
        }
    }
}

#Preview {
    NavigationStack {
        SupportCenterView()
    }
}
