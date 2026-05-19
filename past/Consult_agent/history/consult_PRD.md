# PRD

Owner: shane@cathayholdings.com.tw
Status: Planning
Parent-Task: BRD Agent Suite
Sibling-Doc: `../Diff_agent/PRD.md` (v0.1, owned by Shane)
Completion: 0

# Consult_agent — 產品需求文件

> 版本：v0.6 (Draft)
> 撰寫日期：2026-05-03（v0.1）；修訂：2026-05-04（v0.2 → v0.6）
> 作者：victorchen@cathayholdings.com.tw
> 狀態：待審閱
>
> **v0.2 修訂重點**：
> - 加入「功能分層 (Tier 1 / 2 / 3)」總覽（§3.7）
> - 加入 **觸發詞 routing**（F-1.4）：raw 輸入關鍵詞自動載入 sub-template，與 dropdown 並存
> - 加入 **結構化 JSON 摘要輸出**（F-4.5）：給 PM / RD 快速 onboard，不必讀整份 BRD
> - 加入 **「待 AI 科 / CD 科補充」自動 placeholder**（F-2.5）：BU 不負責填初步技術評估 / API 格式
> - 將 PM / RD 列入下游讀者 persona（§3.1）
> - Goals 加上 G6（雙輸出）；data model 加上 `summary_json`
>
> **v0.3 修訂重點**（2026-05-04 進一步釐清）：
> - 重新校正 target users：依 task brief，**目標使用者僅為 BU 與 PM / RD**；BA 與 AI 科 / CD 科改列為「次要參與者」
> - §3 整節重組為「3.1 目標使用者 / 3.2 Agent 服務目標 / 3.3 BU 端 / 3.4 PM/RD 端 / 3.5 次要參與者 / 3.6 BRD 文件規範 / 3.7 功能分層」
> - User Stories 分軸重寫：US-1~3（BU 端）、US-4~5（PM/RD 端）、US-6~8（次要參與者）
>
> **v0.4 修訂重點**（2026-05-04 全文一致性校正）：
> - **角色一致性**：§1 / §2 / §4 / §5 / §7 全文「BA」主語替換為「BU」；BA 限定於 §3.5 US-6 品質審核
> - **Placeholder 章節範圍 canonical 化**：3 個 H1 全章（修訂記錄 / 初步技術評估 / 時程規劃）+ 「執行方式」H1 之下「API 格式」H2 sub-section；BU 訪談 5 個 H1
> - **修訂記錄矛盾解除**：agent 自動產 v1.0 第一列；v1.1+ 由 BA 維護
> - **架構圖修正**：`keyword_route` 移到 `collect_metadata` 之前；node 計數改為「8 個 main node + 1 sub-loop」
> - **刪除時長 / PoC 承諾**：移除 G1（90 分鐘 / 核心 4 章）、§10.1 Go/No-Go Gates、§11 PoC 樣本依賴 metric、§9 §10 中「PoC / BA 試用」字眼
> - **§3.6 自我封閉**：貼 H2 清單副本，不再純粹外部引用 Diff_agent
> - Q1-5 假設答案校正（主 BU、次 BA）；§12.2 版本字串 v0.1 → v0.3
>
> **v0.5 修訂重點**（2026-05-04 補章節 transition 邏輯）：
> - 補 **F-2.2.1 Transition 觸發條件**：明確定義「題目 N → N+1」「最後一題 → Draft」「章節 N → N+1」三種推進規則
> - 補 **F-2.2.2 答覆品質守門**：每題 ≥ 5 字 / Refine ≤ 3 輪 / 連續 3 Skip 主動建議離線 / 「我不知道」自動 flag
> - 補 **F-2.2.3 提問順序策略**：MVP 嚴守 linear；LLM-aware skip 列為 V2 升級點
> - data model `section_responses` 加 `flag_for_ba_review` 欄位
>
> **v0.6 修訂重點**（2026-05-04 補 pre-flight 兩層架構）：
> - 重寫 **F-1.2** 為 Layer 1（Core 寫死 5 欄）+ Layer 2（BU-specific YAML 控制 3 欄）兩層架構
> - 加 Appendix B-1 `template_configs/<bu>/preflight.yaml` 範例
> - 釐清 `keyword_routing.yaml` 與 `preflight.yaml` 共生長關係；新 BU onboard 不改 graph code
>
> **設計前提（已對齊）**：
> - Consult_agent 與 Diff_agent 為兩個獨立 agent（共用 Slack bot 帳號 / BRD schema / 技術棧）
> - BRD 載體為 Google Docs；最終交付支援匯出 docx，並另產出結構化 JSON 摘要供下游 PM / RD 使用
> - 對話介面為 Slack
> - 跨 BU 通用（產險 / 壽險 / 銀行 / 證券）
> - 技術選型與 Diff_agent 完全一致

---

## 1. 背景與動機 (Background)

各 BU 向金控 Data AI BA 團隊提出 AI 工具需求時，通常需要產出一份符合「金控 Data AI BA 團隊 BRD 標準模板」的 BRD，以利後續移交給 AI 科 / CD 科進行技術評估與開發。目前此流程存在三個痛點：

1. **0 → 1 起手難**：BU SME 雖熟悉業務邏輯，但不熟悉 BRD 模板，常見現象是模板拉出來後章節大量留白（參見 `BRD_Agent/BRD_案件流程評估_20260113_V1.1.docx` —— 此份 BRD 大部分 heading 為空、IO 欄位表僅填零散值）。
2. **章節間一致性差**：「業務邏輯」中描述的失敗情境，常未對應到「例外處理」章節；「IO 欄位表」中的欄位名稱，常未在「業務邏輯」中被引用。BA 後續需花大量時間補洞。
3. **跨 BU 知識不流通**：產險已寫過的相似 BRD（如 NL01008 產品責任險的合理性檢核、照片辨識），其結構與規則設計手法無法被壽險 / 銀行 / 證券 BU 直接借鏡。

姊妹專案 **Diff_agent** 已處理「BRD 已存在 → 會議錄音 → Suggestion 增量更新」的 update 生命週期；本專案 **Consult_agent** 補齊「BRD 從 0 → 1」的 creation 生命週期。

本專案目標是建立一個 Slack-觸發的 conversational agent，**透過結構化訪談把 BU SME 腦中的業務需求逐章寫入符合 Cathay BRD 標準模板的 Google Doc**；BU 在 Slack 端逐章 Accept / Refine / Skip，半自動產出可交付給下游 PM / RD（結構化 summary.json）與 AI 科 / CD 科（完整 BRD doc）的初稿。BA 為次要參與者，於 BU 完成後 spot-check 品質。

---

## 2. 目標 (Goals & Non-Goals)

### 2.1 Goals

- **G1**：BRD 採 **Google Docs** 為協作載體（與 Diff_agent 共用），完成後可一鍵匯出為符合 Cathay 命名慣例的 docx (`BRD_<主題>_<YYYYMMDD>_V1.0.docx`)。
- **G2**：Agent 跨 BU 通用 —— BU 別在 pre-flight 階段選擇，graph 動態載入該 BU 的詞彙表、險種代碼表、模板變體。
- **G3**：每個章節的草稿文字皆**可追溯**到 BU 在 Slack 對話中的具體回答（source quote + Slack ts）。
- **G4**：產出的 BRD 立即可被 Diff_agent 接手 —— 後續會議錄音可直接增量更新本 BRD。
- **G5**：**雙重受眾、雙重輸出** —— 對話對象為 BU（非技術背景），但同時產出 (a) 完整 BRD Google Doc（給 BA / AI 科 / CD 科）與 (b) 結構化 JSON 摘要（給下游 PM / RD 快速 onboard，不需閱讀整份 BRD）。

### 2.2 Non-Goals

- ❌ 不訪談 BU 寫「初步技術評估」「時程規劃」「執行方式 → API 格式」章節 —— 依 Cathay 慣例由 AI 科 / CD 科填寫；Consult_agent 僅自動填入 placeholder 與 BU 提供之 hint（詳 F-2.5）。
- ❌ 不生成流程圖（`<w:drawing>` 圖片）—— 與 Diff_agent 一致延後處理。
- ❌ **不自動維護 v1.1+ 後續修訂記錄** —— agent 僅自動產生 v1.0 第一列（草稿日期 / 作者）；後續版本軌跡由 BA / Diff_agent 維護。
- ❌ 不替代 **BU** 的最終決定權 —— Agent 永遠是「擬稿者」，章節內容須經 BU 在 Slack Accept 後才寫入 Doc。
- ❌ 不做即時多人協作（單一 BU 對單一 thread）。
- ❌ 不跨諮詢 transfer learning（每場諮詢獨立，不從歷史對話自動學習偏好）。

---

## 3. 使用者與情境 (Users & Use Cases)

### 3.1 目標使用者 (Target Users)

依 task brief，本 agent 服務「**BU → PM / RD**」單向需求 pipeline：**對話對象為 BU、結構化輸出消費者為 PM / RD**。其他 stakeholder（BA、AI 科、CD 科）為次要參與者，不主導本 agent 的功能設計。

| 角色 | 類別 | 與 agent 的互動模式 | 主要訴求 |
| --- | --- | --- | --- |
| **BU（業務單位 SME）** | **🎯 主要使用者（輸入端）** | Slack 自然語言對話 | 用日常語言把腦中需求講出來，由 agent 整理成結構化內容 |
| **PM** | **🎯 主要使用者（輸出端）** | 讀取 `summary.json` + Doc 連結 | 不必細讀整份 BRD 即可掌握需求要點，據以開立技術 epic、安排規劃會議 |
| **RD** | **🎯 主要使用者（輸出端）** | 讀取 `summary.json` 中的 IO schema / 業務規則 | 直接拿到可開發的結構化欄位定義與業務規則，不必逐輪追問 BU |
| BA（金控 Data AI BA） | 次要 / 監督者 | 收到 BU 完成通知後 review、處理異常 | 確保品質、處理 BU 答不出來的情境；由原先「主寫手」轉為「品質審核者」 |
| AI 科 / CD 科 | 次要 / 下游 | 接收 BRD doc + summary.json | 進行技術評估與開發；負責填寫被 placeholder 的「初步技術評估」「API 格式」 |

### 3.2 Agent 服務目標 (Agent Mission)

> **單句目標（直接引用 task brief）**：
> 讓 BU 可以透過對話釐清需求，並自動整理成 PM / RD 可用於後續開發的結構化內容。

由此目標推導出兩條設計準則：

1. **對 BU 友善到「沒有 BA 居中翻譯也能 work」**
   → 引導題庫必須口語、few-shot 必要、絕不假設 BU 懂 BRD 模板；錯誤回答允許 Skip 與容錯；長段對話可隨時暫停續寫。
2. **對 PM / RD 友善到「不必閱讀完整 BRD 即可開始規劃 / 開發」**
   → JSON summary 是首要輸出（機器可讀、欄位齊全），完整 BRD Doc 是輔助文件（給 BA / AI 科 / CD 科）。

### 3.3 BU 端使用情境 (Conversation-side User Stories)

> 此節 stories 的主角皆為 BU SME，描述 agent 如何降低「BU 寫 BRD 的門檻」。

**US-1（BU 主導 + 觸發詞快速啟動）—— F-1.4 + F-2.1**

產險 BU SME 接到上級指示「想做 NL01008 店面照片風險評估的 AI 工具」。BU 雖熟悉業務、但完全不熟 BRD 標準模板。BU 在 Slack 輸入：
```
/brd-new 想做產險 NL01008 店面照片風險評估的 AI 工具
```
Agent 從 raw input 偵測候選分類「產險 / 風險評估 / NL01008 / 圖片」，跳出 pre-flight modal **已預先勾選**對應選項，BU 一眼確認、按提交（**不必自己思考該分哪一類**）。Agent 載入「產險 / 風險評估」template + NL01008 照片辨識 BRD 作 few-shot，建立空 BRD Doc。BU 用日常語言依章節引導逐項回答，每題附 few-shot 範例答案，依序完成 5 個 H1 訪談章節。

**US-2（BU 跨 session 續寫，無需重複作答）—— F-5.4 + PostgresSaver**

BU SME 寫到第 3 章「業務邏輯」第 4 題時，遇到下班 / 開會 / 需要回辦公室查資料，直接關閉 Slack thread。隔天上午回到工位，輸入：
```
/brd-resume cn_01HW...
```
Agent 從 PostgresSaver 還原 state，從**第 3 章第 4 題未答完處接續**，全程不需重複前面 2 章已答內容。BU 完成全部章節後 agent 自動 @ BA 進 thread 通知 review，並產出 summary.json。

**US-3（壽險 BU 借鏡產險、跨 BU few-shot）—— F-2.1 + R-3 mitigation**

壽險 BU SME 第一次寫 BRD，本 BU 尚無 reference。Agent pre-flight 偵測「壽險 + 文件辨識」組合，自動載入**產險 NL01008 照片辨識 BRD** 作 few-shot 參考，在每題下方展示產險的範例答案協助壽險 BU 借鏡規則樹設計手法。同時 agent 在 thread 旗標 R-3：「本份為壽險首件 BRD，模板結構是否完全沿用產險待 W3 試行後校準」並 @ BA 進入監督；BU 可選擇繼續使用產險模板或 Pause 等候 BA 對齊。

### 3.4 PM / RD 端使用情境 (Consumption-side User Stories)

> 此節 stories 的主角皆為 PM / RD，描述 agent 輸出如何被「機器可讀地、不必看 BRD 全文地」消費。

**US-4（PM 用 summary.json 直接推進規劃）—— F-4.5**

金控 PM 收到 BA 的 handoff ticket，內含 BRD doc 連結與一份 `summary.json`。PM **不開啟 doc**，直接讀 JSON 即掌握：
- `one_line_goal`：業務目標一句話
- `key_business_rules`：核心規則 3 條
- `io_fields`：完整 IO schema（input / output 欄位）
- `exception_cases`：失敗 / 例外情境
- `open_for_ai_team`：留給 AI 科的議題清單

PM 將 `key_business_rules` 與 `io_fields` 直接複製到 RD 的 epic ticket，並依 `open_for_ai_team` 開出技術評估會議邀請。**原本 PM 需 30+ 分鐘逐字讀完一份 BRD 才能開規劃會議，現在 < 5 分鐘即可完成 onboarding**。

**US-5（RD 用 IO schema + 業務規則直接開工）—— F-4.5**

RD 收到 PM 開的 epic ticket，內含 summary.json 的 `io_fields` 與 `key_business_rules`。RD 直接：
- 根據 `io_fields.input` 寫 input DTO / pydantic schema
- 根據 `io_fields.output` 寫 output type 與序列化
- 根據 `key_business_rules` 條條對應寫單元測試 case
- 根據 `exception_cases` 寫錯誤處理 / fallback

整個過程**不需與 BU 來回追問細節**；遇到 ambiguity 時可循 `consultation_id` 反查完整 BRD Doc 取得章節脈絡，但日常開發以 JSON 為主。`open_for_ai_team` 列出的議題（VLM 選型、guardrail）由 AI 科平行推進、不阻塞 RD。

### 3.5 次要參與者情境 (Secondary-participant Stories)

> 此節 stories 描述 BA / AI 科 / CD 科 / Diff_agent 與本 agent 的搭配方式；皆非主流程，但需在內測階段驗證。

**US-6（BA 從主寫手轉為品質審核者）**

BU 完成所有章節 + summary.json 產出後，agent @ BA 進 thread。BA 快速 spot-check：
- 草稿與原始回答的 source quote 是否對得上（避免 LLM 幻覺）
- summary.json 與 BRD Doc 內容是否一致
- 模糊或敏感欄位（個資、guardrail 規格）是否需要補充

若發現問題 BA 可：(a) 在對應章節點 Refine 要求 agent 重寫；(b) 直接編輯 Google Doc；(c) 旗標諮詢「待修」狀態，要求 BU 重答特定題目。**BA 不再從零訪談 BU、不再從頭整理需求**——角色從「需求收集者」轉為「品質審核者」。

**US-7（AI 科利用 placeholder 直接接續）—— F-2.5**

BRD v1.0 抵達 AI 科時，「初步技術評估」「API 格式」兩節為自動 placeholder，內含 BU 已提供之 hint：
```
> 本章節由 AI 科 / CD 科於後續技術討論階段補充。
> BU 提供之 hint：
>   - execution_mode: near_realtime (< 5 分鐘)
>   - integration_systems: Smartbiz / 核保平台
>   - process_target: 圖片
```
AI 科工程師直接在 Doc 對應段落填入技術選型（VLM 模型、guardrail、API 格式），**不需再向 BU 詢問執行頻率 / 介接系統等已被 pre-flight 收集的資訊**。修訂記錄第一列亦已自動帶入 v1.0 草稿日期 / 作者，AI 科僅需新增 v1.1 列。

**US-8（接續 Diff_agent，零摩擦 hand-off）—— 共用 section ID + F-5.2 共用 OAuth**

Consult_agent 產出 BRD v1.0 後，BA 預約一場 BU 需求對焦會議，會後將錄音檔餵給 Diff_agent。Diff_agent 透過**與 Consult 共用之 `oauth_tokens`** 直接讀取同一份 Google Doc，採用 Consult 寫入時的 section ID 規則（`<doc_id>:<heading_text>`）正確定位章節，寫入 Suggesting-mode edits。BA 在 Docs 端逐項 Accept / Reject，將 BRD 推進至 v1.1。**整個 Consult → Diff hand-off 不需任何手動格式轉換、不需重新授權**。

### 3.6 BRD 文件規範

**沿用 Diff_agent PRD §3.3 定義之 Cathay 「金控 Data AI BA 團隊 BRD 標準模板」**（以下為本 doc 內貼之副本，便於獨立 review；與 Diff_agent §3.3 保持一致）：

- **Title**：`<BU 別> ACT - <主題> AI 工具 BRD`（產險 / 壽險 / 銀行 / 證券，依 pre-flight 答案填入）
- **Subtitle**：`金控 Data AI BA 團隊`

**章節結構（固定 8 個 H1，依此順序）：**

| # | H1 章節 | 主要 H2 (本 PRD 採用之子節) | BU 訪談？ |
| --- | --- | --- | --- |
| 1 | 修訂記錄 | （表格：版本 / 日期 / 修訂者 / 修訂內容） | ❌ agent 自動填 v1.0 列 |
| 2 | 需求背景 | （單一段落為主） | ✅ |
| 3 | 需求分析 | 業務流程 / 流程圖、業務邏輯、輸入內容規則、`<X>判斷規則`、輸出內容說明 / 輸出結果 | ✅ |
| 4 | 執行方式 | 執行時機 / 頻率 / 時間、系統 / 欄位 / 資料格式、**API 格式** | ✅（除 API 格式 H2 外） |
| 5 | User Cases | （列表 / 場景描述） | ✅ |
| 6 | 例外處理 | （列表式失敗情境與處置） | ✅ |
| 7 | 初步技術評估 | （AI 科填技術選型 / guardrail / 模型） | ❌ agent 填 placeholder + BU hint |
| 8 | 時程規劃 | （AI 科 / CD 科主導） | ❌ agent 填 placeholder |

**Placeholder 章節 canonical list（B-1 決策）**：

- **3 個 H1 全章 placeholder**：修訂記錄、初步技術評估、時程規劃
- **1 個 H2 sub-section placeholder**：執行方式 → API 格式
- **BU 訪談範圍**：5 個 H1（需求背景 / 需求分析 / 執行方式（不含 API 格式）/ User Cases / 例外處理）

**其他規則**：

- **僅使用 H1 + H2 兩層**
- **不使用 Google Docs Tabs**
- **Consult_agent 本期僅生成段落（paragraph body）內容與部分結構化表格（IO 欄位表、規則對照表）**；流程圖以 placeholder 段落標註 "[流程圖待補]"，由 BA 手動補圖

> **Consult_agent 與 Diff_agent 共用 section ID 規則**（`<doc_id>:<heading_text>`），確保 Diff_agent 後續可無縫接手 update。

### 3.7 功能分層 (Feature Tiering)

依「對 BU 痛點的直接貢獻度」與「跨 agent 整合必要性」分三層；MVP 範圍 = Tier 1 + Tier 2 hook。

| Tier | 類別 | 功能 | 對應 FR | MVP？ |
| --- | --- | --- | --- | --- |
| **1** | 對話訪談核心 | Slack 結構化訪談（thread / HITL `interrupt()` / 跨 session resume） | F-2.2, F-3.1, F-5.4 | ✅ |
| **1** | 訪談入口 | **觸發詞 routing + BU/專案分流**（raw input 關鍵詞自動載入 sub-template） | F-1.4, F-2.1 | ✅ |
| **1** | 引導品質 | **Few-shot 範例引導**（從 sample BRD 抓相似段落） | F-2.1, F-3.1 | ✅ |
| **1** | 引導品質 | **欄位完整性 quality check + 主動反問**（空欄位 / 模糊敘述偵測） | F-2.3 | ✅ |
| **1** | 雙輸出 | **Google Doc + 結構化 JSON 摘要** | F-2.4, F-4.5 | ✅ |
| **1** | 範圍守門 | **「待 AI 科 / CD 科補充」自動 placeholder** | F-2.5 | ✅ |
| **2** | 整合 hook | 與 Diff_agent 共用 OAuth / section ID 命名規範 | F-5.2, §5.1 | ✅（hook 預留） |
| **2** | 整合 hook | Template YAML 版控（各 BU 模板獨立版本管理） | §5.1 / §6 | 部分 |
| **3** | 治理 | 使用 dashboard / audit log / 跨 BU 模板對齊建議 | — | ❌ Post-MVP |
| **3** | 進階輸入 | 上傳既有需求草稿 → 預填 | F-1.3 | ❌ P2+ |

**容易被忽略但關鍵的兩點（v0.2 新增的設計抉擇）**：

1. **觸發詞 routing 比 dropdown 更關鍵**：BU 自己常常無法事前歸類專案類型（連保險險種代碼 NL01008 都常是事後才補標）；agent 需從 raw input 偵測關鍵詞（「合理性」「店面照片」「風險評估」）自動載入 sub-template，並在 pre-flight 表單預先勾選對應選項供 BU 確認 / 修改。
2. **JSON 結構化摘要不是錦上添花**：BRD 全文太長，PM / RD handoff 看摘要比看 doc 快十倍；這直接對應 task brief「整理成可用於後續開發的結構化內容」的核心目標。

---

## 4. 功能需求 (Functional Requirements)

### 4.1 輸入 (Input)

- **F-1.1 Slash command**：`/brd-new` 啟動新諮詢；可選參數 `--resume <consultation_id>` 接續中斷的諮詢。
- **F-1.2 Pre-flight metadata 收集**（**兩層架構**）：

    透過 Slack Block Kit modal **一次性**呈現所有欄位（不是逐項問答）。欄位分兩層：

    **Layer 1：Core（寫死、跨 BU 強制統一）—— 5 欄**

    這 5 欄是 `ConsultAgentState` TypedDict 與 `summary.json` 共同的合約欄位，任何 BU 都必填、選項固定。

    | # | 欄位 | 型別 | 選項 | 為什麼必須寫死 |
    | --- | --- | --- | --- | --- |
    | 1 | `bu` | enum | 產險 / 壽險 / 銀行 / 證券 | routing 第一層；決定載入哪份 BU YAML |
    | 2 | `process_target` | enum | 文字 / 圖片 / 結構化資料 / 多模態 | 影響 LLM prompt + few-shot 取材策略 |
    | 3 | `execution_mode` | enum | 即時 < 30 秒 / 準即時 < 5 分鐘 / 批次 < 1 小時 | F-2.5 AI 科 placeholder hint 必填欄位 |
    | 4 | `result_type` | enum | Pass/Fail/Reminder / 分數 / 自然語言說明 / 多項組合 | 影響 `summary.json.io_fields.output` 萃取 schema |
    | 5 | `one_line_goal` | free text（≤ 200 字） | — | summary.json 必出欄位，PM/RD 跨 BU 標準化讀取 |

    **Layer 2：BU-specific（YAML 控制 options，欄位本身存在但可為空）—— 3 欄**

    options 隨 BU 換、欄位本身存在於所有 BU 的 modal（值可為 null / 空陣列）；新 BU onboard 不改 graph code，只加 YAML。

    | # | 欄位 | 型別 | YAML key | 範例（產險） | 範例（銀行） |
    | --- | --- | --- | --- | --- | --- |
    | 6 | `policy_code` | enum or null | `template_configs/<bu>/preflight.yaml#policy_codes` | NL01008 / NL01009... | （壽險可能整欄不存在 → null） |
    | 7 | `project_type` | enum | 同上 `#project_types` | 合理性檢核 / 風險評估 / 流程評估 / 文件辨識 | 授信評估 / 信用卡風控 / 反詐... |
    | 8 | `integration_systems` | enum array (multi-select) | 同上 `#integration_systems` | Smartbiz / 核保平台 / postgreSQL | 放款系統 / 風控引擎 |

    **設計理由與約束：**

    - **Core 必須寫死**：跨 BU 統一這 5 欄才能保證 `summary.json` schema 對 PM / RD 穩定；ConsultAgentState typed schema 也倚賴它做 graph routing。
    - **BU-specific 必須 YAML 化**：強迫壽險填「產險險種代碼」、強迫銀行填「Smartbiz」會產生 garbage data。
    - **`keyword_routing.yaml` 與 `preflight.yaml` 共生長**：F-1.4 觸發詞偵測結果必須能 map 回 modal options，所以兩份 YAML 必須同步維護（建議 import 同一份 BU 詞彙字典）。
    - **新 BU onboard 流程**：(1) 建立 `template_configs/<新 BU>/preflight.yaml` 列出該 BU 的 policy_codes / project_types / integration_systems；(2) 在 `keyword_routing.yaml` 加該 BU 的關鍵詞表；(3) 至少準備 1 份 reference BRD 給 few-shot retrieval。**完全不改 graph code**。
    - **UI 副作用（Tradeoff）**：因 Layer 2 動態化，不同 BU 的 modal 欄位數可能略不一致（壽險可能少 1 欄 `policy_code`）；可接受。
- **F-1.3 可選輸入**：BU 上傳既有需求草稿（docx / pdf / txt）→ agent 萃取後預填章節初版（後續 P2+ 支援）。
- **F-1.4 觸發詞 routing**（**Tier 1 / 新增**）：
    - 啟動 `/brd-new <一句話描述>`（command 後可附帶 raw 自然語言）；若無描述則退回純 modal pre-flight
    - Agent 對 raw input 執行關鍵詞偵測（規則式 + LLM fallback），輸出候選分類：BU / 專案類型 / 處理對象 / 險種代碼
    - 偵測結果**預先勾選**進 pre-flight modal 選項，BU 可一鍵確認或手動修改（不強制 dropdown 唯一入口）
    - 詞彙表來源：`template_configs/keyword_routing.yaml`（與 BU 詞彙表共生長）
    - **設計理由**：BU 自己常無法事前歸類，dropdown 把分類負擔轉嫁給最不擅長分類的 persona

### 4.2 處理 Pipeline

- **F-2.1 Template 動態載入**
    - 依 BU 別 + 專案類型載入對應的 **章節引導問題庫**（YAML 設定檔，每章節 5–10 個引導問題）
    - 載入 **BU 詞彙表**（險種代碼、欄位常用英文名、guardrail 名稱）
    - 載入 1–2 份 **few-shot reference BRD**（從歷史已完成 BRD 中匹配相似度最高者）
- **F-2.2 章節訪談（章節 loop 主流程）**

    對 BU 訪談範圍依序執行（**5 個 H1**：需求背景 / 需求分析 / 執行方式（不含 API 格式 H2）/ User Cases / 例外處理；其餘章節由 F-2.5 fill_placeholders 處理）：

    1. **Interview node**：用該章節引導問題逐題詢問 BU（一次一題，避免一次問太多）
    2. **Draft node**：以累積的回答 + few-shot reference 餵 LLM 產出該章節段落草稿（structured output：標題 + 段落 list + 表格資料）
    3. **Review-in-Slack node**：將草稿以 Slack message + 「Accept / Refine / Skip」按鈕呈現給 BU
    4. **Refine loop**：若 BU 點 Refine，agent 詢問修改方向，重新生成；最多 3 輪
    5. **Apply-to-Doc node**：Accept 後寫入 Google Doc 對應章節（Docs API `batchUpdate`，**直接寫入 final 內容，非 Suggesting mode**，與 Diff_agent 不同）

    **F-2.2.1 Transition 觸發條件（章節 loop 推進規則）**

    section_loop 推進有三種 transition；每種有明確觸發條件，避免「agent 何時進下一項」的歧義：

    | Transition | 觸發條件 | 機制 |
    | --- | --- | --- |
    | **題目 N → N+1**（章節內） | BU 在 thread 回覆任意文字 **或** 按 `Skip` 按鈕 | 收到 reply / click 後，state 累加 `current_section_responses`、`question_idx++`，發下一題；用 `interrupt()` 等下個 input |
    | **最後一題答完 → Draft node** | `question_idx >= len(template_questions[current_section])` | 自動 transition（不需 BU 觸發）；agent 把累積回答餵 LLM 產 draft、發 review message |
    | **章節 N → N+1**（章節間） | BU 點 review message 上 `Accept` 或 `Skip Section` | 寫入 Doc → `current_section = next_h1` → 進下一章節 `interview` |

    **F-2.2.2 答覆品質守門**（避免「BU 一字過關」進下題）

    - **每題最小門檻**：reply ≥ 5 字 **或** 顯式按 Skip。空 reply / 單一 emoji / 純標點 不視為 answered；agent 重發該題並提示「再多寫一點，或按 Skip」。
    - **章節 Refine 上限**：≤ 3 輪；超過強制進下章節（避免卡死）。
    - **連續 3 題 Skip**：agent 主動發訊建議「先離線整理需求再回來」（呼應 §12 R-2 mitigation）。
    - **「我不知道」偵測**：LLM 在 interview node 偵測到 BU 顯式表達不確定（「不確定 / 不知道 / 還沒想好」等 pattern），自動建議 Skip，並在 `section_responses.skipped=true` 同時標 `flag_for_ba_review=true`，由 `quality_gate` 統一回報給 BA。

    **F-2.2.3 提問順序策略（MVP linear，V2 升級點）**

    - **MVP**：嚴守 linear —— 按 `template_questions[section]` 順序逐題問。BU 若提早提到後面題目的內容，agent 把 reply 全文存進「當題」 `answer_text`；到後面題目時呈現「你前面提過：『…』，要沿用 / 補充 / 重答？」三選一。簡單、可預測、好除錯。
    - **V2 升級點（不在 MVP）**：LLM-aware skip —— LLM 偵測 BU 已答某題的內容，自動 skip 該題並把已答內容歸檔到對應 question_idx。彈性高但實作複雜，待 MVP 跑過後評估。
- **F-2.3 跨章節一致性檢查 (Quality Gate)**

    所有章節寫入後執行：

    - 檢查「業務邏輯」中提到的所有失敗情境是否在「例外處理」中有對應條目
    - 檢查「IO 欄位表」中的欄位是否都在「業務邏輯」或「判斷規則」中被引用
    - 檢查「執行方式」的「執行頻率」與「業務邏輯」中描述的觸發條件是否一致
    - 不一致時在 Slack 提示 BU，提供「Auto-fix」「Manual-fix」「Ignore」三選項
- **F-2.4 匯出 docx**
    - 透過 Google Docs API `documents.export` 直接匯出
    - 檔名約定：`BRD_<主題>_<YYYYMMDD>_V1.0.docx`（與 Cathay 既有命名一致）
    - 匯出後在 Slack 提供下載連結
- **F-2.5 自動 placeholder（fill_placeholders node）**（**Tier 1**）：

    依 §3.6 Placeholder canonical list 處理 4 個非 BU 訪談區塊：

    | 區塊 | 處理方式 |
    | --- | --- |
    | 初步技術評估（H1 全章） | 寫入 placeholder + BU hint（見下） |
    | 時程規劃（H1 全章） | 寫入 placeholder（待 AI 科 / CD 科補充） |
    | 執行方式 → API 格式（H2 sub-section） | 寫入 placeholder + BU hint |
    | 修訂記錄（H1 全章） | **自動生成 v1.0 第一列**（版本：v1.0 草稿、日期：諮詢完成日、作者：BU + agent name） |

    **「初步技術評估」「API 格式」placeholder 範本**：
    ```
    > 本章節由 AI 科 / CD 科於後續技術討論階段補充。
    > BU 提供之 hint：<從 pre-flight metadata 自動填入：execution_mode / integration_systems / process_target>
    ```

    **「時程規劃」placeholder 範本**：
    ```
    > 本章節由 AI 科 / CD 科於後續技術討論階段補充。
    ```

    **設計理由**：避免逼 BU 填不該填的章節；同時讓 BRD 結構完整，下游 AI 科 / CD 科可直接接續編輯。修訂記錄 v1.0 第一列自動填入是「Non-Goal 例外」（Non-Goal 規定 v1.1+ 不維護，但 v1.0 第一列為合理初值）。

### 4.3 對話呈現 (Conversation Presentation)

> Consult_agent 與 Diff_agent 的根本差異：**Slack 是 Consult_agent 的主要 review surface**（訪談 + 草稿 review 都在 Slack），Doc 是輸出目標；Diff_agent 反之。

- **F-3.1 訪談訊息格式**：每題引導問題以 Slack thread 內 message 呈現，包含：
    - 章節名稱與題號（例：`[需求分析 / 業務邏輯] 3 / 7`）
    - 問題本身
    - 範例回答（取自 few-shot reference BRD 的對應段落）
    - 「Skip」按鈕（跳過此題，回到 graph 後仍可從累積資訊推斷）
- **F-3.2 草稿 review 訊息**：章節草稿以 Slack `mrkdwn` block 呈現，附三顆按鈕：
    - **Accept**：寫入 Doc，進入下一章節
    - **Refine**：彈出 modal 收集修改方向，重新 draft
    - **Skip section**：本章節留空，繼續下一章節
- **F-3.3 進度條**：每個章節完成後在 thread 回覆進度（e.g. "✅ 4/8 章節完成"）

### 4.4 Doc 寫入 (Google Docs Integration)

- **F-4.1 建立空 BRD**：Pre-flight 完成後，agent 在預設（依 BU 別配置）的 Google Drive 資料夾建立新 Doc，套用 Title / Subtitle / 8 個 H1 空章節，回 Slack 顯示 Doc 連結。
- **F-4.2 章節寫入**：每章節 Accept 後立即寫入（增量寫入，不等全部完成）—— 好處是 BU 可隨時切到 Doc 查看當前進度。
- **F-4.3 表格寫入**：IO 欄位表、判斷規則表透過 Docs API `InsertTable` + cell 級 update 寫入；表格 schema 由 template 設定檔定義（每 BU + 專案類型可配置不同欄位數）。
- **F-4.4 Audit trail**：與 Diff_agent 一致 —— 倚賴 Google Docs Revision History；agent 端自管 `consultations` / `section_responses` 表記錄訪談軌跡。
- **F-4.5 結構化 JSON 摘要輸出**（**Tier 1 / 新增**）：
    - Quality Gate 通過後，agent 額外產出一份 `consultation_summary.json`，與 Doc / docx 並列輸出
    - 內容（給 PM / RD 不必讀完整 BRD 即可 onboard）：
        ```json
        {
          "consultation_id": "cn_01HW...",
          "brd_doc_url": "https://docs.google.com/...",
          "bu": "產險",
          "policy_code": "NL01008",
          "project_type": "風險評估",
          "one_line_goal": "...",
          "execution_mode": "near_realtime",
          "result_type": "score_plus_nl",
          "integration_systems": ["Smartbiz", "核保平台"],
          "key_business_rules": ["規則 1...", "規則 2..."],
          "io_fields": {
            "input": [{"name_zh": "...", "name_en": "...", "format": "...", "example": "..."}],
            "output": [...]
          },
          "exception_cases": ["失敗情境 1...", "失敗情境 2..."],
          "open_for_ai_team": ["技術選型", "API 格式", "guardrail 規格"],
          "generated_at": "2026-05-24T10:30:00+08:00"
        }
        ```
    - 透過 LLM `with_structured_output` 從 BRD 草稿萃取（不另外問 BU）
    - 在 Slack 提供「📋 Copy summary JSON」與「⬇ Download summary.json」按鈕；亦寫入 `consultations.summary_json` 欄位供 API 取用
    - **設計理由**：BRD 全文長、章節多，PM / RD 看摘要比看 doc 快十倍；亦為未來「需求看板 / 自動派工」留接口

### 4.5 Slack Bot 互動

- **F-5.1 Slash Command**：
    - `/brd-new` → 啟動新諮詢
    - `/brd-resume <consultation_id>` → 接續未完成諮詢（諮詢可能跨多日 / 多 session）
    - `/brd-list` → 列出當前使用者進行中 / 已完成的諮詢
- **F-5.2 OAuth**：與 Diff_agent 共用同一份 OAuth token（`oauth_tokens` 表共用）—— 使用者授權一次，兩個 agent 都可用。
- **F-5.3 互動 UI**：使用 Slack Block Kit 提供：
    - Pre-flight 表單（modal）
    - 章節草稿 review 按鈕（Accept / Refine / Skip）
    - 「Open in Google Docs」按鈕
    - 「Export as docx」按鈕
- **F-5.4 中斷 / 續寫**：使用者隨時可關閉 thread；下次用 `/brd-resume` 接續。State 由 PostgresSaver 保存。

---

## 5. 系統架構 (Architecture)

- 整體採 **LangGraph state-machine** 模型；HITL 透過 LangGraph `interrupt()` 在 Slack 端等待 BU 回應（與 Diff_agent 倚賴 Docs Suggesting mode 不同）。
- 每場諮詢 = 一個 graph run（thread_id = consultation_id），state 由 PostgresSaver 持久化以利長時間中斷後續寫。

```
                      ┌─────────────┐
   Slack User ──────▶ │  Slack Bot  │ ←─── 共用 bot 帳號 + OAuth tokens
                      │ (slack-bolt)│      （與 Diff_agent 共用）
                      └──────┬──────┘
                             │ /brd-new (with pre-flight metadata)
                             ▼
   ╔═════════════════ LangGraph App (Consult) ══════════════════╗
   ║                                                            ║
   ║   ┌─────────────────┐                                      ║
   ║   │keyword_route    │ (raw input 觸發詞偵測 → 候選分類；      ║
   ║   └────┬────────────┘  modal 預先勾選用)                    ║
   ║        ▼                                                   ║
   ║   ┌─────────────────┐                                      ║
   ║   │collect_metadata │ (Slack modal pre-flight 8 題；         ║
   ║   └────┬────────────┘  含 keyword_route 預先勾選)            ║
   ║        ▼                                                   ║
   ║   ┌─────────────────┐                                      ║
   ║   │load_template    │ (依 BU + 專案類型載入引導題庫          ║
   ║   └────┬────────────┘  + few-shot BRD)                     ║
   ║        ▼                                                   ║
   ║   ┌─────────────────┐                                      ║
   ║   │create_doc       │ (Docs API 建立空 BRD + Title/H1)      ║
   ║   └────┬────────────┘                                      ║
   ║        ▼                                                   ║
   ║   ┌──────────────────────────────────────┐                 ║
   ║   │ section_loop (對每個 H1 章節)        │                  ║
   ║   │   ┌──────────┐                       │                 ║
   ║   │   │interview │ ← interrupt() 等 BU   │                 ║
   ║   │   └────┬─────┘   在 Slack 回答        │                ║
   ║   │        ▼                              │                ║
   ║   │   ┌──────────┐                       │                 ║
   ║   │   │draft     │ (Gemini structured)   │                 ║
   ║   │   └────┬─────┘                       │                 ║
   ║   │        ▼                              │                ║
   ║   │   ┌──────────┐                       │                 ║
   ║   │   │review    │ ← interrupt() 等 BU   │                 ║
   ║   │   └────┬─────┘   Accept/Refine/Skip  │                 ║
   ║   │        ▼                              │                ║
   ║   │   ┌──────────┐                       │                 ║
   ║   │   │apply     │ (Docs API batchUpdate)│                 ║
   ║   │   └──────────┘                       │                 ║
   ║   └──────────────────────────────────────┘                 ║
   ║        ▼                                                   ║
   ║   ┌─────────────────┐                                      ║
   ║   │fill_placeholders│ (初步技術評估/API 格式/修訂記錄        ║
   ║   └────┬────────────┘  自動 placeholder)                   ║
   ║        ▼                                                   ║
   ║   ┌─────────────────┐                                      ║
   ║   │quality_gate     │ (跨章節一致性檢查)                     ║
   ║   └────┬────────────┘                                      ║
   ║        ▼                                                   ║
   ║   ┌─────────────────┐                                      ║
   ║   │summary_export   │ (LLM structured → JSON 摘要)          ║
   ║   └────┬────────────┘                                      ║
   ║        ▼                                                   ║
   ║   ┌─────────────────┐                                      ║
   ║   │export (optional)│ (Docs API export → docx)             ║
   ║   └────┬────────────┘                                      ║
   ║        ▼                                                   ║
   ║      END → notify Slack with Doc 連結 + docx + JSON 摘要    ║
   ║                                                            ║
   ║   checkpointer = PostgresSaver (HITL resume + audit)       ║
   ╚════════════════════════════════════════════════════════════╝
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
  ┌──────────┐      ┌──────────────┐    ┌──────────────┐
  │Template  │      │Postgres      │    │Google        │
  │Configs   │      │(consultations│    │Workspace     │
  │(YAML/    │      │ + brd_drafts │    │(Docs API +   │
  │ JSON)    │      │ + section_   │    │ Drive API)   │
  │          │      │   responses  │    └──────────────┘
  │          │      │ + oauth_     │
  │          │      │   tokens *)  │
  └──────────┘      └──────────────┘
                          * 共用 Diff_agent 之 oauth_tokens
```

### 5.1 Components

- **Slack Bot (`slack-bolt`)**：與 Diff_agent **共用同一個 bot 帳號**；slash command 路由到不同 graph entry point。
- **LangGraph App (Consult)**：核心 pipeline，由 **8 個 main node + 1 個 sub-loop（內含 4 sub-nodes）** 組成：
    1. `keyword_route` —— 從 `/brd-new <raw text>` 偵測候選 BU / 專案類型 / 險種代碼；無 raw text 則 no-op；結果用於 modal 預先勾選
    2. `collect_metadata` —— Slack modal pre-flight，8 題收集（modal 預先填入 keyword_route 結果）
    3. `load_template` —— 從 `template_configs/<bu>/<project_type>.yaml` 載入引導題庫；從 `references/<bu>/` 撈 few-shot BRD
    4. `create_doc` —— Docs API 建立空 BRD（Title / Subtitle / 8 個 H1 空段落）
    5. **section_loop（sub-loop）** —— 對 BU 訪談 5 個 H1（不含 API 格式 H2）執行 `interview → draft → review → apply` 子流程；每個 sub-node 之間以 `interrupt()` 等待 Slack 端 BU 回應
    6. `fill_placeholders` —— 對 3 個 H1（修訂記錄 / 初步技術評估 / 時程規劃）+ 1 個 H2（API 格式）自動寫入 placeholder；修訂記錄自動填 v1.0 第一列
    7. `quality_gate` —— 跨章節一致性檢查
    8. `summary_export` —— 用 LLM `with_structured_output` 從 BRD 萃取 JSON 摘要、寫入 `consultations.summary_json`
    9. `export` —— 可選步驟，呼叫 Docs API 匯出 docx
- **Template Configs**：YAML / JSON 設定檔，定義每個 BU + 專案類型的引導題庫、IO 欄位表 schema、few-shot reference BRD 路徑；**新增 BU 不需改 graph 程式碼**。
- **Checkpointer (PostgresSaver)**：因諮詢可能跨多日，HITL resume 是核心需求；checkpointer 必須持久化（不能用 MemorySaver 跨 session）。
- **Storage**：
    - Template configs：repo 內 `template_configs/`
    - LangGraph state + business 表（`consultations`, `brd_drafts`, `section_responses`）：Postgres，與 Diff_agent 同一 database 不同 schema
    - BRD 本體：**Google Workspace（Docs API）**

---

## 6. 技術選型 (Tech Stack)

| 層次 | 選項 | 與 Diff_agent 對齊 |
| --- | --- | --- |
| **Pipeline 框架** | LangGraph + `langchain-core`（state machine + PostgresSaver checkpointer；HITL 透過 `interrupt()`） | ✅ |
| **LLM** | Gemini 2.5 Pro（`langchain-google-genai`）；`with_structured_output` 用於章節草稿生成 | ✅ |
| **Checkpointer** | PostgresSaver（必須持久化；不像 Diff_agent P1 可用 MemorySaver） | 略異 |
| **Backend** | FastAPI + Postgres | ✅ |
| **Slack SDK** | `slack-bolt` (Python)；**與 Diff_agent 共用 bot 帳號** | ✅ |
| **Doc Ops** | `google-api-python-client`（Docs API + Drive API）；本期 Consult 直接寫 final 內容（非 Suggesting mode） | ✅ SDK / 略異模式 |
| **OAuth** | `google-auth` + `google-auth-oauthlib`；**與 Diff_agent 共用 `oauth_tokens` 表** | ✅ |
| **Doc → docx export** | Docs API `documents.export(mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document')` | 新增 |
| **Template 設定** | YAML（`template_configs/<bu>/<project_type>.yaml`） | 新增 |
| **Few-shot retrieval** | 直接讀整份歷史 BRD 餵 LLM context（倚賴 Gemini 1M context；不做 chunking / RAG） | ✅ 同策略 |
| **Observability** | stdout log（dev / 內測）→ structured log（V1） | ✅ |
| **Deploy** | 本機 dev（uvicorn + ngrok）→ Cathay 內網（V1） | ✅ |

---

## 7. 核心使用者流程 (User Flow)

```
1. BU 在 #brd-consultation channel 輸入：
   /brd-new 想做產險 NL01008 店面照片風險評估的 AI 工具
   (附 raw text 供 keyword_route 偵測)

2. (首次使用) Bot 回 OAuth consent URL；BU 點擊授權 → refresh token 存 Postgres
   (已授權者 / 已用過 Diff_agent 者跳過此步 ── 共用 oauth_tokens)

3. keyword_route 偵測 raw text → 候選分類「產險 / 風險評估 / NL01008 / 圖片」

4. Bot 跳 Slack modal (Pre-flight 表單，已預先勾選 keyword_route 結果):
   • BU 別          [產險 ▾]          ← 預勾
   • 險種代碼       [NL01008 ▾]      ← 預勾
   • 專案類型       [風險評估 ▾]      ← 預勾
   • 處理對象       [圖片 ▾]          ← 預勾
   • 執行模式       [準即時 < 5 分鐘 ▾]
   • 預期結果       [分數 + 自然語言說明 ▾]
   • 介接系統       [☑ Smartbiz ☑ 核保平台 ☐ postgreSQL]
   • 一句話業務目標 [____________]

5. BU 確認 / 微調後提交 → Agent 載入「產險 / 風險評估 / 圖片」對應 template；
   並從歷史撈出「產險 NL01008 照片辨識 BRD」作為 few-shot reference

6. Agent 在預設 Google Drive 資料夾建立新 Doc
   "產險 ACT - <主題> AI 工具 BRD"
   8 個 H1 空章節
   Bot 回 thread:
   ✅ 已建立 BRD: [📄 Open in Google Docs]
      將開始章節訪談 (5 / 8 章節需 BU 訪談；其餘
      3 H1 + 1 H2 由 agent 自動 placeholder)

7. Agent 進入 section_loop (對 5 個 H1 依序訪談):
   章節 1 / 5: 需求背景

   ┌─────────────────────────────────────────┐
   │ [需求背景] 1 / 5                         │
   │                                         │
   │ Q: 目前 BU 在這個業務環節遇到什麼          │
   │ 痛點？(請用 1-3 句話描述)                 │
   │                                         │
   │ 範例 (取自 NL01008 照片辨識 BRD):         │
   │ "目前核保人員在評估銷售案件時,             │
   │  面臨風險資料收集不一且缺乏規格化          │
   │  評估標準的挑戰..."                       │
   │                                         │
   │             [Skip this question]        │
   └─────────────────────────────────────────┘

   BU 回答 → Agent 累積回答 → 進下一題

8. 章節題目問完後, Agent 用 LLM 草擬該章節:

   ┌─────────────────────────────────────────┐
   │ [需求背景] 草稿                          │
   │                                         │
   │ "目前核保人員在評估 <X> 案件時,           │
   │  面臨..." (約 100-200 字)                │
   │                                         │
   │  [✅ Accept]  [✏️ Refine]  [⏭ Skip]   │
   └─────────────────────────────────────────┘

9. BU 點 Accept → Agent 寫入 Doc 該章節 → 進下一章節
   BU 點 Refine → Agent modal 問修改方向 → 重新生成
   BU 點 Skip   → 章節留空, 進下一章節

10. 5 個 H1 跑完後, Agent 執行 fill_placeholders:
    • 修訂記錄: 自動填 v1.0 第一列
    • 初步技術評估 / 時程規劃: 寫入 placeholder + BU hint
    • 執行方式 → API 格式 H2: 寫入 placeholder + BU hint

11. Agent 執行 Quality Gate:
    ✅ 業務邏輯失敗情境已對應到例外處理
    ⚠️ IO 欄位表第 3 欄 "process_score" 未在業務邏輯被引用
        [Auto-fix] [Manual-fix] [Ignore]

12. Agent 執行 summary_export → 產出 summary.json

13. Agent 在 thread 回最終訊息:
    ✅ BRD 初稿完成
       • 5 個 H1 BU 訪談章節已寫入 Doc
       • 3 個 H1 + 1 個 H2 由 agent 自動 placeholder (修訂記錄
         v1.0 / 初步技術評估 / 時程規劃 / 執行方式 → API 格式)
       [📄 Open in Google Docs]  [⬇ Export as docx]
       [📋 Copy summary JSON]    [⬇ Download summary.json]

14. (跨 session) BU 隔天想接續編修:
    /brd-resume cn_01HW...
    → 從 PostgresSaver 還原 state, 進入下一個章節 / 回到 quality gate
```

---

## 8. 資料模型 (Data Model)

兩層：**business 表**由我們設計、**LangGraph checkpoint 表**由 PostgresSaver 自動建立。

### 8.1 Business 表（自管）

```sql
consultations
  id (uuid)                -- 同時當作 LangGraph thread_id
  initiated_by (slack_user_id)
  bu                       -- 產險 / 壽險 / 銀行 / 證券
  project_type             -- 合理性檢核 / 風險評估 / ...
  policy_code              -- 險種或業務代碼 (e.g. NL01008)
  process_target           -- 文字 / 圖片 / 結構化 / 多模態
  execution_mode           -- realtime / near_realtime / batch
  result_type              -- pass_fail / score / nl_summary / combo
  integration_systems      -- jsonb array
  one_line_goal            -- 業務目標一句話
  brd_doc_id               -- Google Doc ID (建立後填入)
  brd_doc_url
  raw_input_text           -- /brd-new <raw text>，用於 keyword_route 偵測
  routed_keywords          -- jsonb；keyword_route 偵測到的候選分類
  summary_json             -- jsonb；F-4.5 結構化摘要 (給 PM/RD)
  status                   -- pre_flight | drafting | quality_gate | done | abandoned
  current_section          -- 當前進行中的 H1 章節
  created_at
  updated_at
  completed_at

brd_drafts
  consultation_id (FK)
  section_heading          -- H1 章節名稱
  draft_version            -- 該章節第幾版草稿 (Refine 累計)
  draft_content            -- 該版草稿 markdown 文字
  applied_to_doc_at        -- 寫入 Doc 的時間 (NULL = 未寫入)
  status                   -- pending | accepted | skipped | refined

section_responses
  id
  consultation_id (FK)
  section_heading
  question_idx             -- 該章節第幾題
  question_text
  answer_text              -- BU 在 Slack 的回答
  slack_ts                 -- Slack 訊息 timestamp (用於追溯)
  skipped (bool)
  flag_for_ba_review (bool) -- F-2.2.2「我不知道」偵測旗標
  answered_at

oauth_tokens               -- 與 Diff_agent 共用同一張表
  slack_user_id (PK)
  ...                      -- 詳見 Diff_agent PRD §8.1
```

### 8.2 LangGraph state schema（in-memory，TypedDict）

```python
class ConsultAgentState(TypedDict):
    consultation_id: str
    slack_user_id: str
    # Raw input + keyword routing (F-1.4)
    raw_input_text: str | None
    routed_keywords: dict[str, list[str]]      # candidate BU / project_type / policy_code
    # Pre-flight
    bu: Literal["產險", "壽險", "銀行", "證券"]
    project_type: str
    policy_code: str | None
    process_target: str
    execution_mode: Literal["realtime", "near_realtime", "batch"]
    result_type: str
    integration_systems: list[str]
    one_line_goal: str
    # Template
    template_questions: dict[str, list[str]]   # section_heading -> questions
    few_shot_brds: list[BRDSnapshot]            # 載入的 reference BRDs
    # Doc
    brd_doc_id: str | None
    brd_doc_url: str | None
    # Section loop state
    current_section: str
    completed_sections: list[str]
    current_section_responses: list[SectionResponse]   # 當前章節已收集回答
    current_draft: str | None                          # 當前章節草稿
    refine_count: int                                  # 該章節 refine 次數
    # Quality gate
    quality_issues: list[QualityIssue]
    # Output
    summary_json: dict | None                          # F-4.5 結構化摘要
    docx_export_url: str | None
```

### 8.3 LangGraph checkpoint 表

由 `PostgresSaver.create_tables(conn)` 自動建立（同 Diff_agent §8.3）。**Consult_agent 必須使用 PostgresSaver**（不能用 MemorySaver），因為諮詢可能跨多日中斷續寫。

---

## 9. 里程碑 (Milestones)

> **時程目標**：預計約 3 週交付一個可用的內部版本（比 Diff_agent 多 1 週，因 section_loop + interrupt() 比 Diff_agent 線性流程複雜）

| Phase | 內容 | 工時 |
| --- | --- | --- |
| **P1 — LangGraph 骨架 + Doc 建立 + 單章節打通** (W1) | LangGraph state + 4 個 node (`collect_metadata` / `load_template` / `create_doc` / 單章節 `interview→draft→review→apply` loop)、template YAML 結構定義、CLI 跑通單章節 | 5 個工作日 |
| **P2 — 多章節 + Section Loop + Quality Gate** (W2) | section_loop 多章節串接、interrupt() + PostgresSaver resume、quality gate 規則實作、跨章節一致性檢查、fill_placeholders、summary_export | 5 個工作日 |
| **P3 — Slack 整合 + 跨 BU 設定 + 內測** (W3) | Slack modal pre-flight、Block Kit review buttons、`/brd-resume` 接續、跨 BU template configs（產險 + 1 個其他 BU）、docx export、真實諮詢內測 | 5 個工作日 |

---

## 10. 開發時程規劃 (Development Timeline)

> • **Kickoff 日**：2026-05-06 (Tue)
> • **內部版本完成 / BU 試用**：2026-05-24 (Sun)
> • **總工時**：約 15 個工作日

### Week 1：LangGraph 骨架 + 單章節打通

| 任務 | 確認 |
| --- | --- |
| LangGraph 環境裝起來、定義 `ConsultAgentState`、Postgres 開好 | `graph.invoke()` 能跑通 dummy state |
| 寫 `collect_metadata` node（先 CLI 模擬，Slack 整合留 W3）+ `load_template` node | 給定 BU + 專案類型，能載入正確的 template YAML |
| 寫 `create_doc` node（Docs API 建立 BRD with Title/Subtitle/8 H1 空章節） | 真實 Google Drive 上看到新 Doc |
| 實作 **單一章節**的 `interview → draft → review → apply` loop（CLI 互動模擬 Slack） | 跑通「需求背景」單章節：CLI 問題 → 草稿 → Apply → Doc 上看到內容 |
| Refine loop（最多 3 輪） + draft 結構化輸出 (Gemini structured output) | Refine 一次後草稿確實改變 |

### Week 2：多章節 + Section Loop + Quality Gate

| 任務 | 確認 |
| --- | --- |
| 把單章節 loop 包裝成 `section_loop`，依 `template_questions` 順序跑 4 個核心章節 | 跑完 4 章節後 Doc 上有完整內容 |
| 實作 `interrupt()` HITL pattern + PostgresSaver；確認跨 process resume 可行 | Kill process → 重啟 → `graph.ainvoke()` from checkpoint 能續寫 |
| 寫 `quality_gate` node：3 條跨章節一致性規則（業務邏輯↔例外處理 / IO 欄位↔業務邏輯 / 執行頻率↔業務邏輯） | 給有意製造不一致的 state，能正確回報 issues |
| 寫 `fill_placeholders` node（初步技術評估 / API 格式 / 修訂記錄 自動填入） | Doc 上對應章節有 placeholder 文字，BU 不被問到 |
| 寫 `summary_export` node（LLM `with_structured_output` 萃取 JSON 摘要） + `consultations.summary_json` 欄位寫入 | 跑完一份 BRD 後 JSON 摘要欄位齊全、可被 PM/RD 讀取 |
| 寫 `export` node（Docs API 匯出 docx） + 檔名命名邏輯 | 匯出 docx 用 Word 開啟結構正確 |

### Week 3：Slack 整合 + 跨 BU + 內測

| 任務 | 確認 |
| --- | --- |
| Slack bot 骨架（與 Diff_agent 共用 bot 帳號 / OAuth tokens） + slash command (`/brd-new`, `/brd-resume`, `/brd-list`) | `/brd-new` 啟動真實 graph run |
| **`keyword_route` node + `keyword_routing.yaml`**：從 `/brd-new <raw text>` 偵測候選分類，預先勾選進 modal | 給定典型 raw input 能正確 pre-select BU / 專案類型 / 險種代碼 |
| Pre-flight Slack modal（8 題、預先勾選 keyword_route 結果） + Block Kit review buttons (Accept/Refine/Skip) | 整條 Slack flow 跑通；BU 一鍵確認分類 |
| 跨 BU template configs：完成產險 (NL01008 風險評估 / 合理性檢核) + 1 個其他 BU 試行（建議壽險 / 銀行任一） | 至少 2 個 BU 的 template YAML 能驅動完整 flow |
| docx export 整合至 Slack 「Export as docx」按鈕；JSON 摘要 「📋 Copy summary JSON」「⬇ Download summary.json」按鈕 | 點按鈕後在 Slack 收到 .docx 檔 + summary.json |
| 真實諮詢內測 + bug fix + README | **內測：BU 透過 Slack 完成一份產險 BRD，summary.json 欄位齊全** |

---

## 11. 成功指標 (Success Metrics)

| Metric | 目標 |
| --- | --- |
| 章節接受率（Accept count / total proposed） | ≥ 60% |
| Refine 平均次數（每章節） | ≤ 1.5 |
| 嚴重幻覺（編造業務邏輯）比率 | < 1% |
| 跨諮詢 resume 成功率 | ≥ 95% |
| **觸發詞 routing 命中率**（候選分類至少 1 項與 BU 最終確認一致） | ≥ 70% |
| **JSON summary 可用性**（PM / RD 盲讀後給 ≥ 4 / 5 分） | 至少 1 位 PM / RD 達標 |

---

## 12. 風險與待解問題 (Risks & Open Questions)

### 12.1 風險

- **R-1 LLM 幻覺**：可能編造 BU 沒講過的業務邏輯。**緩解：** 每個章節草稿強制標註 source（哪幾題回答衍生）；BU 在 review 時可看到引用對照。
- **R-2 BU 講不出來**：BU SME 對需求毫無概念，連引導題也答不出來。**緩解：** (a) 每題提供 few-shot 範例；(b) 「Skip」按鈕容錯；(c) 三題以上連續 Skip 時 agent 主動建議「先離線整理需求再回來」。
- **R-3 跨 BU 模板差異未知**：本 PRD 假設「金控 Data AI BA 團隊 BRD 標準模板」跨 BU 通用，但目前 3 份範例 BRD 全為產險，壽險 / 銀行 / 證券是否真用同一模板未驗證。**緩解：** W3 跨 BU 試行階段必須取得 1 份非產險 BU 的 BRD 範例做對照；若模板差異大，調整為 BU-specific template variant（YAML 設定檔已預留此擴展性）。
- **R-4 Section_loop + interrupt() 複雜度**：HITL 跨多次 Slack 訊息的 graph state 管理比 Diff_agent 線性流程複雜得多。**緩解：** P1 先用 CLI 模擬驗證 graph 邏輯，P3 才整合 Slack；PostgresSaver 從 P2 開始用（不走 P1 MemorySaver 路徑）。
- **R-5 章節間語境漂移**：在第 5 章節時，LLM 可能忘記第 1 章節定義的業務目標導致草稿不一致。**緩解：** 每次 draft 餵 LLM context 時包含「pre-flight metadata + 已 Accept 章節摘要」作為上下文。
- **R-6 與 Diff_agent 整合斷裂**：Consult 產出的 Doc 結構若與 Diff_agent §3.3 規範略有出入（e.g. heading 樣式套錯、表格 schema 不一致），Diff_agent 後續 update 時 section ID 對不上。**緩解：** 兩個 agent 共用同一個「Doc 結構驗證 helper module」（W2 開發 quality_gate 時順便抽出）。
- **R-7 docx 匯出格式損失**：Google Docs 匯出的 docx 樣式可能與 Cathay 內部 docx 模板不一致（字型 / 行距 / 表格邊框）。**緩解：** 初期以 Docs API 直接匯出為主；若 BU / BA 反映樣式問題，V1 改採 python-docx 自製 docx renderer（從 BRD state 直接渲染，不經 Docs export）。

### 12.2 Open Questions

詳見同資料夾 `open_questions.md`。本 PRD v0.3 已假設下列答案：

- Q1-1（Consult vs Diff 關係）→ 兩個獨立 agent，共用 Slack bot + OAuth + BRD schema
- Q1-2（輸出格式）→ Google Docs 主，docx 為匯出選項，並另出 summary.json 給 PM / RD
- Q1-3（BU 進入路徑）→ 純 Slack 文字訪談 + `/brd-new <raw text>` 觸發詞 routing；上傳檔案預填留 P2+
- Q1-4（跨 BU 通用性）→ 設計上跨 BU；MVP 先做產險 + 1 個其他 BU 試行
- Q1-5（主操作者）→ **主 BU、次 BA**；BA 為品質審核者（§3.5 US-6），不在主流程中

未對齊的細項（仍待 Shane / 團隊確認）：

- **OQ-1**：跨 BU 的 BRD 模板是否真的一致？（高風險，見 R-3）
- **OQ-2**：BA 是否能接受 Google Docs 為主要載體（而非 docx）？
- **OQ-3**：agent 是否需要與 Cathay 內部 guardrail 整合（範例 BRD 提到的「產險內部 guardrail」）？
- **OQ-4**：Consult 與 Diff 的 hand-off 點 —— Consult 產出 v1.0 後應該如何「正式宣告完成」並通知 Diff 可以接手？

---

## 13. Appendix

### A. 範例 Pre-flight Metadata (JSON)

```json
{
  "consultation_id": "cn_01HW...",
  "initiated_by": "U03ABC...",
  "bu": "產險",
  "project_type": "風險評估",
  "policy_code": "NL01008",
  "process_target": "圖片",
  "execution_mode": "near_realtime",
  "result_type": "score_plus_nl",
  "integration_systems": ["Smartbiz", "核保平台"],
  "one_line_goal": "判斷店家照片屬於固定店面或攤販，提供風險評分供報價分流使用"
}
```

### B. 範例 Template YAML

#### B-1. `template_configs/產險/preflight.yaml`（Layer 2 BU-specific options）

```yaml
# F-1.2 Layer 2：BU-specific 欄位的 options 來源
bu: 產險
policy_codes:
  - code: NL01008
    label: 產品責任險（食品業）
  - code: NL01009
    label: 產品責任險（製造業）
project_types:
  - 合理性檢核
  - 風險評估
  - 流程評估
  - 文件辨識
integration_systems:
  - Smartbiz 商險銷售平台
  - 核保平台
  - postgreSQL
  - （自訂）
```

> 壽險 / 銀行 / 證券各自有獨立 `template_configs/<bu>/preflight.yaml`；options 不同但 schema 相同。新 BU onboard 只新增此檔，不改 graph code。

#### B-2. `template_configs/產險/風險評估.yaml`（章節引導題庫）

```yaml
project_type: 風險評估
title_template: "{bu} ACT - {topic} AI 工具 BRD"
sections:
  需求背景:
    questions:
      - "目前 BU 在這個業務環節遇到什麼痛點？"
      - "現行人工流程的瓶頸在哪？(時間 / 一致性 / 規模)"
      - "為什麼選擇 AI 解決而非其他方案？"
      - "預期帶來的業務價值是什麼？"
    few_shot_section_path: "references/產險/NL01008_照片辨識.docx#需求背景"
  業務邏輯:
    questions:
      - "AI 工具的處理對象是什麼？(具體描述輸入)"
      - "判斷規則的核心邏輯是什麼？(一句話)"
      - "判斷結果有哪幾種類型？分別代表什麼？"
      - "失敗或無法判斷的情境如何處理？"
    few_shot_section_path: "references/產險/NL01008_照片辨識.docx#業務邏輯"
io_table_schema:
  input:
    columns: ["欄位名稱", "欄位英文", "資料格式", "範例", "備註"]
  output:
    columns: ["欄位名稱", "欄位英文", "資料格式", "範例", "備註"]
```

### C. 範例 Slack 章節 Review 訊息

```
📝 [需求背景] 草稿（基於你的 5 個回答）

> 目前核保人員在評估產品責任險案件時，面臨店家風險資料收
> 集不一且缺乏規格化評估標準的挑戰。由於現行流程高度依賴
> 人工判斷，導致每次收集的資訊完整度不一，難以確保評估的
> 一致性與全面性。為提升核保品質與效率，本專案將採「自動
> 化分類，人工專注高風險」原則。

來源：Q1, Q2, Q3, Q4 (Q5 略過)

[ ✅ Accept ]   [ ✏️ Refine ]   [ ⏭ Skip Section ]
```

### D. 範例 Quality Gate 訊息

```
🔍 跨章節一致性檢查完成

✅ 業務邏輯失敗情境已對應到例外處理 (3/3)
⚠️ IO 欄位表第 3 欄「process_score」未在業務邏輯被引用
   建議修改：在業務邏輯中補充「最終輸出 process_score 評分」
   [ Auto-fix ]   [ Manual-fix in Doc ]   [ Ignore ]
✅ 執行頻率與業務邏輯觸發條件一致
```

### E. 範例 keyword_routing.yaml

`template_configs/keyword_routing.yaml`：

```yaml
bu_keywords:
  產險: ["產險", "產品責任險", "車險", "ACT", "核保", "Smartbiz"]
  壽險: ["壽險", "保單", "理賠", "新契約"]
  銀行: ["銀行", "授信", "信用卡", "存款"]
  證券: ["證券", "下單", "交易", "風控"]

project_type_keywords:
  合理性檢核: ["合理性", "檢核", "校驗", "稽核"]
  風險評估: ["風險", "評分", "分流", "高風險"]
  流程評估: ["流程", "案件流程", "工作流", "SLA"]
  文件辨識: ["照片", "OCR", "圖片", "文件辨識"]

policy_code_keywords:
  NL01008: ["產品責任險", "店面照片", "食品業"]
```

### F. 範例 summary.json（給 PM / RD）

```json
{
  "consultation_id": "cn_01HW...",
  "brd_doc_url": "https://docs.google.com/document/d/...",
  "bu": "產險",
  "policy_code": "NL01008",
  "project_type": "風險評估",
  "one_line_goal": "判斷店家照片屬於固定店面或攤販，提供風險評分供報價分流使用",
  "execution_mode": "near_realtime",
  "result_type": "score_plus_nl",
  "integration_systems": ["Smartbiz", "核保平台"],
  "key_business_rules": [
    "若照片中可見固定門牌與店招 → 歸類為固定店面",
    "若照片中無門牌、僅見攤車 → 歸類為攤販",
    "信心度 < 0.7 時退回人工複核"
  ],
  "io_fields": {
    "input": [
      {"name_zh": "店家照片", "name_en": "store_photo", "format": "JPG/PNG", "example": "store_001.jpg"}
    ],
    "output": [
      {"name_zh": "風險評分", "name_en": "risk_score", "format": "float [0,1]", "example": "0.83"},
      {"name_zh": "店家類型", "name_en": "store_type", "format": "enum", "example": "fixed_storefront"}
    ]
  },
  "exception_cases": [
    "照片模糊無法辨識 → 退回人工",
    "照片中無任何店面元素 → 標記為 invalid_input"
  ],
  "open_for_ai_team": ["技術選型（VLM 模型）", "API 格式", "guardrail 規格"],
  "generated_at": "2026-05-24T10:30:00+08:00"
}
```

### G. 範例 Slack 完成訊息（含 summary）

```
✅ BRD 初稿完成

📄 [Open in Google Docs]   ⬇ [Export as docx]

📋 PM / RD 用結構化摘要 (summary.json)
   • 業務目標：判斷店家照片屬於固定店面或攤販...
   • 核心規則：3 條
   • IO 欄位：1 input / 2 output
   • 留給 AI 科：技術選型、API 格式、guardrail
   [ 📋 Copy summary JSON ]   [ ⬇ Download summary.json ]

下一步建議：
  → 通知 BA review 完整 Doc
  → 將 summary.json 貼入 PM / RD handoff ticket
  → 排定 AI 科技術評估會議（預計補初步技術評估章節）
```

---

*— End of PRD v0.6 —*
