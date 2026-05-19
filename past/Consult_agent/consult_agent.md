# consult_agent

## 1. 背景與動機 (Background)

各 BU 向金控 Data AI BA 團隊提出 AI 工具需求時，通常需要產出一份符合「金控 Data AI BA 團隊 BRD 標準模板」的 BRD，以利後續移交給 AI 科 / CD 科進行技術評估與開發。目前此流程存在三個痛點：

1. **0 → 1 起手難**：BU 雖熟悉業務邏輯，但不熟悉 BRD 模板，常見現象是模板拉出來後章節大量留白（參見 `BRD_Agent/BRD_案件流程評估_20260113_V1.1.docx` —— 此份 BRD 大部分 heading 為空、IO 欄位表僅填零散值）。
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

依 task brief，本 agent 服務「**BU → PM / RD**」單向需求 pipeline：**對話對象為 BU、結構化輸出消費者為 PM / RD**。其他 stakeholder（BA、其他參與討論的單位）為次要參與者。

| 角色 | 類別 | 與 agent 的互動模式 | 主要訴求 |
| --- | --- | --- | --- |
| **BU** | **主要使用者（輸入端）** | Slack 自然語言對話 | 用日常語言把腦中需求講出來，由 agent 整理成結構化內容 |
| **PM** | **主要使用者（輸出端）** | 讀取 `summary.json` + Doc 連結 | 不必細讀整份 BRD 即可掌握需求要點，據以開立技術 epic、安排規劃會議 |
| **RD** | **主要使用者（輸出端）** | 讀取 `summary.json` 中的 IO schema / 業務規則 | 直接拿到可開發的結構化欄位定義與業務規則，不必逐輪追問 BU |
| BA | 次要 / 監督者 | 收到 BU 完成通知後 review、處理異常 | 確保品質、處理 BU 答不出來的情境；由原先「撰稿者」轉為「品質審核者」 |

### 3.2 Agent 服務目標 (Agent Mission)

> **單句目標（直接引用從explore agent 來的 task brief）**：
讓 BU 可以透過對話釐清需求，並自動整理成 PM / RD 可用於後續開發的結構化內容。
> 

由此目標推導出兩條設計準則：

1. **對 BU 友善**
    1. 引導問題偏口語、長段對話可隨時暫停或續寫
2. **對 PM / RD 友善**
    1. JSON summary 輸出
        1. 讓PM可以先釐清 BRD 大致內容
    2. 完整 BRD Doc 是輔助文件（給 BA / RD）

### 3.3 BU 端使用情境 (Conversation-side User Stories)

> 此節 stories 的主角皆為 BU，描述 agent 如何降低 BRD 初稿撰寫的門檻。
> 

**US-1（BU 主導 + 觸發詞快速啟動）**

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
> 

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
> 

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

| # | H1 (Header 1) 章節 | 主要 H2  | BU 訪談？ |
| --- | --- | --- | --- |
| 1 | 修訂記錄 | （表格：版本 / 日期 / 修訂者 / 修訂內容） | ❌ agent 自動填 v1.0 列 |
| 2 | 需求背景 | （單一段落為主） | ✅ |
| 3 | 需求分析 | 業務流程 / 流程圖、業務邏輯、輸入內容規則、`<X>判斷規則`、輸出內容說明 / 輸出結果 | ✅ |
| 4 | 執行方式 | 執行時機 / 頻率 / 時間、系統 / 欄位 / 資料格式、**API 格式** | ✅（除 API 格式 H2 外） |
| 5 | User Cases | （列表 / 場景描述） | ✅ |
| 6 | 例外處理 | （列表式失敗情境與處置） | ✅ |
| 7 | 初步技術評估 | （RD 填技術選型 / guardrail / 模型） | ❌ agent 填 placeholder + BU hint |
| 8 | 時程規劃 | （?） | ❌ agent 填 placeholder |

**Placeholder 章節 canonical list（B-1 決策）**：

- **3 個 H1 全章 placeholder**：修訂記錄、初步技術評估、時程規劃
- **1 個 H2 sub-section placeholder**：執行方式 → API 格式
- **BU 訪談範圍**：5 個 H1（需求背景 / 需求分析 / 執行方式（不含 API 格式）/ User Cases / 例外處理）

**其他規則**：

- **僅使用 H1 + H2 兩層**
- **Consult_agent 本期僅生成段落（paragraph body）內容與部分結構化表格（IO 欄位表、規則對照表）**；流程圖以 placeholder 段落標註 “[流程圖待補]”，由 BA或RD 手動補圖 (?)

> **Consult_agent 與 Diff_agent 共用 section ID 規則**（`<doc_id>:<heading_text>`）， Diff_agent 後續可接手 update。
> 

### 3.7 功能分層 (Feature Tiering)

依「對 BU 痛點的直接貢獻度」與「跨 agent 整合必要性」分三層；MVP 範圍 = Tier 1 + Tier 2 hook。

| 類別 | 功能 |
| --- | --- |
| 對話訪談核心 | Slack 結構化訪談（thread / HITL `interrupt()` / 跨 session resume） |
| 訪談入口 | **觸發詞 routing + BU/專案分流**（raw input 關鍵詞自動載入 sub-template） |
| 引導品質 | **Few-shot 範例引導**（從 sample BRD 抓相似段落） |
| 引導品質 | **欄位完整性 quality check + 主動反問**（空欄位 / 模糊敘述偵測） |
| 雙輸出 | **Google Doc + 結構化 JSON 摘要** |
| 範圍守門 | **待補充的部分自動填 placeholder** |
| 整合 | 與 Diff_agent 共用 OAuth / section ID 命名規範 |
| 整合 | Template YAML 版控（各 BU 模板獨立版本管理） |
| **Session 管理** | **啟動位置守則 + 自動建 thread**（slash 限 channel 主層 / DM；每 session = 1 thread；F-5.1） |
| **Session 管理** | **Thread-aware auto-resume**（在原 thread 打字即接續，不需 slash；F-5.4 Layer 1） |
| **Session 管理** | **Interrupt message footer 提示**（暫存提示 + 「可平行開新 session」引導；F-3.1） |
| Session 管理（V2） | **App Home Dashboard**（Consult + Explore 統一視覺入口、quick-action 按鈕；F-5.5） |

---

## 4. 功能需求 (Functional Requirements)

### 4.1 輸入 (Input)

- **F-1.1 Slash command**：`/brd-new` 啟動新諮詢；可選參數 `-resume <consultation_id>` 接續中斷的諮詢。
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
    | 6 | `policy_code` | enum or null | `template_configs/<bu>/preflight.yaml#policy_codes` | NL01008 / NL01009… | （壽險可能整欄不存在 → null） |
    | 7 | `project_type` | enum | 同上 `#project_types` | 合理性檢核 / 風險評估 / 流程評估 / 文件辨識 | 授信評估 / 信用卡風控 / 反詐… |
    | 8 | `integration_systems` | enum array (multi-select) | 同上 `#integration_systems` | Smartbiz / 核保平台 / postgreSQL | 放款系統 / 風控引擎 |
    
    **設計理由與約束：**
    
    - **Core 預先寫定**：跨 BU 統一這 5 欄才能保證 `summary.json` schema 對 PM / RD 穩定；ConsultAgentState typed schema 也倚賴它做 graph routing。
    - **BU-specific  YAML 化**：強迫壽險填「產險險種代碼」、強迫銀行填「Smartbiz」會產生 garbage data。
    - **`keyword_routing.yaml` 與 `preflight.yaml` 共生長**：F-1.4 觸發詞偵測結果必須能 map 回 modal options，所以兩份 YAML 必須同步維護（建議 import 同一份 BU 詞彙字典）。
    - **新 BU onboard 流程**：(1) 建立 `template_configs/<新 BU>/preflight.yaml` 列出該 BU 的 policy_codes / project_types / integration_systems；(2) 在 `keyword_routing.yaml` 加該 BU 的關鍵詞表；(3) 至少準備 1 份 reference BRD 給 few-shot retrieval。**完全不改 graph code**。
    - **UI 副作用（Tradeoff）**：因 Layer 2 動態化，不同 BU 的 modal 欄位數可能略不一致（壽險可能少 1 欄 `policy_code`）；可接受。
- **F-1.4 觸發詞 routing**
    - 啟動 `/brd-new <一句話描述>`（command 後可附帶 raw 自然語言）；若無描述則退回純 modal pre-flight
    - Agent 對 raw input 執行關鍵詞偵測（規則式 + LLM fallback），輸出候選分類：BU / 專案類型 / 處理對象 / 險種代碼
    - 偵測結果**預先勾選**進 pre-flight modal 選項，BU 可一鍵確認或手動修改（不強制 dropdown 唯一入口）
    - 詞彙表來源：`template_configs/keyword_routing.yaml`（與 BU 詞彙表共生長）
    - **設計理由**：BU 自己常無法事前歸類，dropdown 把分類負擔轉嫁給最不擅長分類的 persona

### 4.2 處理 Pipeline

- **F-2.1 Template 動態載入**
    - 依 BU 別 + 專案類型載入對應的 **章節引導問題庫**（YAML 設定檔，每章節 5–10 個引導問題）
    - 載入 **BU 詞彙表**（險種代碼、欄位常用英文名、guardrail 名稱）
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

    **F-2.2.4 anchor_entities 抽取（防 LLM 幻覺）**

    - **執行時機**：在 section_loop 處理「需求背景」**第 2 題**（具體案例型 keystone；題庫見 Appendix H）BU 答完之後、進入下一題之前，interview node 透過 LLM 從答案中抽出 entities（人物 / 系統 / 數字 / 時間 / 案例代號），寫入 `state.anchor_entities`。
    - **下游使用**：後續所有章節的 `draft` node prompt 注入兩個 placeholder：
       - `{anchor_case}` = 該題完整答案
       - `{anchor_entities}` = 抽出的 entity list
       LLM 草擬章節時被要求「敘述須圍繞此案例展開、entities 須一致」，避免自編情境。
    - **Skip 處理**：若 BU 對該題按 Skip → `state.anchor_entities = []`、`flag_for_ba_review=true`；後續 draft prompt 改用 fallback（無 anchor 約束），BA spot-check 時優先檢查章節敘述是否有自編情境。
    - **設計理由**：這是把原 v0.7 Phase 1.5 GC-2 keystone case 的精神拆解進章節訪談的核心機制 —— 移除獨立 phase，但保留 anti-hallucination anchor。
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
    `> 本章節由 AI 科 / CD 科於後續技術討論階段補充。   > BU 提供之 hint：<從 pre-flight metadata 自動填入：execution_mode / integration_systems / process_target>`
    
    **「時程規劃」placeholder 範本**：
    `> 本章節由 AI 科 / CD 科於後續技術討論階段補充。`
    
    **設計理由**：避免逼 BU 填不該填的章節；同時讓 BRD 結構完整，下游 AI 科 / CD 科可直接接續編輯。修訂記錄 v1.0 第一列自動填入是「Non-Goal 例外」（Non-Goal 規定 v1.1+ 不維護，但 v1.0 第一列為合理初值）。
    

### 4.3 對話呈現 (Conversation Presentation)

> Consult_agent 與 Diff_agent 的根本差異：**Slack 是 Consult_agent 的主要 review surface**（訪談 + 草稿 review 都在 Slack），Doc 是輸出目標；Diff_agent 反之。
> 
- **F-3.1 訪談訊息格式**：每題引導問題以 Slack thread 內 message 呈現，包含：
    - 章節名稱與題號（例：`[需求分析 / 業務邏輯] 3 / 7`）
    - 問題本身
    - 範例回答（取自 few-shot reference BRD 的對應段落）
    - 「Skip」按鈕（跳過此題，回到 graph 後仍可從累積資訊推斷）
    - **底部 footer（每則 interrupt 訊息固定）**：
        - 「💾 進度已自動暫存 · session: `<slug>`」（提示 BU 不必擔心丟失進度）
        - 「想開另一個 session？到 `#brd-consultation` 主層打 `/brd-new` 或 `/brd-explore`」（給 BU 心理上「可以平行開新 session」許可，避免誤以為要先收尾才能開新的）
- **F-3.2 草稿 review 訊息**：章節草稿以 Slack `mrkdwn` block 呈現，附三顆按鈕：
    - **Accept**：寫入 Doc，進入下一章節
    - **Refine**：彈出 modal 收集修改方向，重新 draft
    - **Skip section**：本章節留空，繼續下一章節
- **F-3.3 進度條**：每個章節完成後在 thread 回覆進度（e.g. “✅ 4/8 章節完成”）

### 4.4 Doc 寫入 (Google Docs Integration)

- **F-4.1 建立空 BRD**：Pre-flight 完成後，agent 在預設（依 BU 別配置）的 Google Drive 資料夾建立新 Doc，套用 Title / Subtitle / 8 個 H1 空章節，回 Slack 顯示 Doc 連結。
- **F-4.2 章節寫入**：每章節 Accept 後立即寫入（增量寫入，不等全部完成）—— 好處是 BU 可隨時切到 Doc 查看當前進度。
- **F-4.3 表格寫入**：IO 欄位表、判斷規則表透過 Docs API `InsertTable` + cell 級 update 寫入；表格 schema 由 template 設定檔定義（每 BU + 專案類型可配置不同欄位數）。
- **F-4.4 Audit trail**：與 Diff_agent 一致 —— 倚賴 Google Docs Revision History；agent 端自管 `consultations` / `section_responses` 表記錄訪談軌跡。
- **F-4.5 結構化 JSON 摘要輸出**（**Tier 1 / 新增**）：
    - Quality Gate 通過後，agent 額外產出一份 `consultation_summary.json`，與 Doc / docx 並列輸出
    - 內容（給 PM / RD 不必讀完整 BRD 即可 onboard）：
    `json { "consultation_id": "cn_01HW...", "brd_doc_url": "https://docs.google.com/...", "bu": "產險", "policy_code": "NL01008", "project_type": "風險評估", "one_line_goal": "...", "execution_mode": "near_realtime", "result_type": "score_plus_nl", "integration_systems": ["Smartbiz", "核保平台"], "anchor_case": "...", "business_value_signal": "...", "success_metrics": ["..."], "kill_criteria": ["..."], "hidden_constraints": ["..."], "downstream_consumer": {"role": "...", "interface": "...", "next_action": "..."}, "exclusion_scope": ["..."], "reference_alignment": {"reference_brd": "...", "similar_to": "...", "different_from": "..."}, "key_business_rules": ["規則 1...", "規則 2..."], "io_fields": { "input": [{"name_zh": "...", "name_en": "...", "format": "...", "example": "..."}], "output": [...] }, "exception_cases": ["失敗情境 1...", "失敗情境 2..."], "open_for_ai_team": ["技術選型", "API 格式", "guardrail 規格"], "generated_at": "2026-05-24T10:30:00+08:00" }`
    - 8 個 key（`anchor_case` ~ `reference_alignment`）由 BRD 草稿 + `section_responses` 萃取；題目以 archetype 形式併入既有章節題庫（拆解地圖見 Appendix H）
    - 透過 LLM `with_structured_output` 從 BRD 草稿 + `section_responses` + `state.anchor_entities` 萃取（不另外問 BU）
    - 在 Slack 提供「📋 Copy summary JSON」與「⬇ Download summary.json」按鈕；亦寫入 `consultations.summary_json` 欄位供 API 取用
    - **設計理由**：BRD 全文長、章節多，PM / RD 看摘要比看 doc 快十倍；亦為未來「需求看板 / 自動派工」留接口

### 4.5 Slack Bot 互動

- **F-5.1 Slash Command 與啟動位置**：
    - **指令**：
        - `/brd-new [一句話描述]` → 啟動新諮詢；描述可選，附上會觸發 keyword_route 預先勾選 modal（F-1.4）
        - `/brd-resume <consultation_id>` → cross-thread fallback resume（僅 Layer 2，見 F-5.4）
        - `/brd-list` → 列出當前使用者進行中 / 已完成的諮詢（顯示 slug 而非 UUID）
    - **啟動位置規範**：
        - `/brd-new` **必須在 channel 主層**（如 `#brd-consultation`）**或 BU 與 bot 的 DM** 觸發
        - 若 BU 在現有 thread 內打 `/brd-new` → bot 回 **ephemeral 訊息**「請到 channel 主層開新 session（避免與該 thread 既有 session 混淆）」並 reject 該指令
        - **設計理由**：thread 內既有 active session 會啟用 thread-aware auto-resume（F-5.4 Layer 1）；slash 啟動行為與 prose 接續行為必須清楚分流
    - **每個 session = 一個獨立 thread**：
        - 收到 `/brd-new` 後，bot **主動在 channel 主層建立一則 parent message**（含 session slug + Doc 連結佔位）→ 後續訪談 / 草稿 review / quality gate **全部在該 parent message 的 thread 下展開**
        - `consultations.slack_thread_ts` 儲存此 thread_ts，作為 `consultation_id` 的 1:1 反查鍵（§8.1）
        - **多 session 並存**：BU 可同時有多個 active thread（每個對應一個 consultation）；同 channel 視覺上清楚分離，**不會多出聊天室**
    - **同 BU active session 上限**：`consultations` + `explorations` `status='in_progress'` 加總 ≤ 3；超過時 `/brd-new` reject 並列出進行中清單，提示先收尾
- **F-5.2 OAuth**：與 Diff_agent 共用同一份 OAuth token（`oauth_tokens` 表共用）—— 使用者授權一次，兩個 agent 都可用。
- **F-5.3 互動 UI**：使用 Slack Block Kit 提供：
    - Pre-flight 表單（modal）
    - 章節草稿 review 按鈕（Accept / Refine / Skip）
    - 「Open in Google Docs」按鈕
    - 「Export as docx」按鈕
- **F-5.4 中斷 / 續寫（兩層 resume 機制）**：
    - **Layer 1（主路徑）— Thread-aware auto-resume**：
        - BU 直接回到原 thread 發任何訊息 → bot 從 `slack_thread_ts` 反查 `consultation_id` → 自動還原 LangGraph state 並接續對應 node
        - **零 slash command、零 ID 輸入**；適用 BU 找得回原 thread（最常見情境）
    - **Layer 2（fallback）— `/brd-resume <consultation_id>`**：
        - 適用：BU 找不到原 thread（換 channel / 換 device / 距離太久滾出視窗）
        - 流程：先打 `/brd-list` 列出進行中 session（顯示 slug）→ 複製 `<consultation_id>` → `/brd-resume <id>`
        - **僅作為 fallback**，不是主要 resume 路徑
    - **State 持久化**：PostgresSaver checkpointer 保存所有 graph state；任一 interrupt 點皆可斷後續寫
    - **歧義處理**：若同一 thread 曾經先做 Explore 後 hand-off 為 Consult → Explore session 在 hand-off 時標 `status='handed_off'`，`slack_thread_ts` 重綁到新 `consultation_id`；**同一 thread 任一時刻只能綁一個 active session**
- **F-5.5 App Home Dashboard（V2，Tier 3）**：
    - Slack App Home tab 顯示 BU 的所有 active / completed sessions（Consult + Explore 合併呈現）
    - 卡片內容：session slug、status、進度百分比、上次活動時間、`[▶ 繼續]` / `[⚙ 詳情]` 按鈕
    - 頂端固定兩顆 quick-action 按鈕：`[+ 新諮詢]`（觸發 `/brd-new`）、`[+ 新探索]`（觸發 `/brd-explore`）
    - **延後到 V2 的理由**：MVP 階段 Slack 內建「Threads」左側欄已能覆蓋大多回找需求；App Home 是強化體驗，不是核心
    - **實作 hint**：透過 Slack `app_home_opened` event + `views.publish` API；Consult 與 Explore 共用此 view（同 bot 帳號）

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
   ║   │   └────┬─────┘   在 Slack 回答;       │                 ║
   ║   │        │         需求背景 Q2 答完後   │                 ║
   ║   │        │         LLM 抽 anchor_      │                 ║
   ║   │        │         entities (F-2.2.4)  │                 ║
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
    5. **section_loop（sub-loop）** —— 對 BU 訪談 5 個 H1（不含 API 格式 H2）執行 `interview → draft → review → apply` 子流程；每個 sub-node 之間以 `interrupt()` 等待 Slack 端 BU 回應；**「需求背景」第 2 題（具體案例型 keystone）BU 答完後，interview node 立即 LLM 抽出 `anchor_entities` 寫入 state，後續所有章節 `draft` prompt 共用此 anchor 防幻覺**（詳 §4.2 F-2.2.4）
    6. `fill_placeholders` —— 對 3 個 H1（修訂記錄 / 初步技術評估 / 時程規劃）+ 1 個 H2（API 格式）自動寫入 placeholder；修訂記錄自動填 v1.0 第一列
    7. `quality_gate` —— 跨章節一致性檢查
    8. `summary_export` —— 用 LLM `with_structured_output` 從 BRD drafts + section_responses + anchor_entities 萃取 JSON 摘要（含 8 個 archetype 衍生 key），寫入 `consultations.summary_json`
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
| **Doc Ops** | `google-api-python-client`（Docs API + Drive API）； Consult 直接寫 final 內容（非 Suggesting mode） | ✅ SDK / 略異模式 |
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
   (本章節題目以 archetype 標記;Q1 動機型 / Q2 具體案例 keystone /
    Q5 成功定義型 / Q6 比照型條件;見 Appendix H 拆解地圖)

   ┌─────────────────────────────────────────┐
   │ [需求背景] 1 / 5  ·  動機型              │
   │                                         │
   │ Q: 先不管 AI 怎麼做 ── 如果這件事「這個月  │
   │    都沒被處理」，實際上會發生什麼？        │
   │    (損失 / 客訴 / 合規 / 工時 / 業務機會,  │
   │     任一即可)                            │
   │                                         │
   │ 💡 Why: 過濾偽需求                      │
   │                                         │
   │             [Skip this question]        │
   └─────────────────────────────────────────┘

   BU 回答 → Agent 累積 → 進 Q2 (具體案例 keystone)

   ┌─────────────────────────────────────────┐
   │ [需求背景] 2 / 5  ·  具體案例 (keystone) │
   │                                         │
   │ Q: 請給我「最近一週」真實案件 ── 從輸入   │
   │    講到結束狀態;用真實數字 / 代號         │
   │    (個資請改代號 e.g. CUST_001)         │
   │                                         │
   │ 💡 此題會被後續章節 LLM 引用作 anchor,   │
   │    降低敘述幻覺                          │
   │                                         │
   │             [Skip this question]        │
   └─────────────────────────────────────────┘

   BU 詳答 → interview node LLM 從答案抽 anchor_entities:
     ["CUST_001", "業務員", "核保人員", "核保平台",
      "Smartbiz", "12 分鐘", "risk_score=0.7"]
   → 寫入 state.anchor_entities (F-2.2.4),後續所有章節
     draft prompt 共用此 anchor 防幻覺
   → 進 Q3, Q4, Q5 ...

8. 章節題目問完後, Agent 用 LLM 草擬該章節:

    ┌─────────────────────────────────────────┐
    │ [需求背景] 草稿                          │
    │                                         │
    │ "目前核保人員在評估 CUST_001 類案件時,    │
    │  面臨..." (約 100-200 字;LLM 已用       │
    │   anchor_case / anchor_entities 校準)   │
    │                                         │
    │  [✅ Accept]  [✏️ Refine]  [⏭ Skip]   │
    └─────────────────────────────────────────┘

9. BU 點 Accept → Agent 寫入 Doc 該章節 → 進下一章節
   BU 點 Refine → Agent modal 問修改方向 → 重新生成
   BU 點 Skip   → 章節留空, 進下一章節

   (繼續走完 需求分析 / 執行方式 / User Cases / 例外處理 共 5 章;
    執行方式 Q1 = 下游使用者型;例外處理 Q1 = 假設挖掘型 +
    條件 Q2 = 邊界型;見 Appendix H)

10. 5 個 H1 跑完後, Agent 執行 fill_placeholders:
    • 修訂記錄: 自動填 v1.0 第一列
    • 初步技術評估 / 時程規劃: 寫入 placeholder + BU hint
    • 執行方式 → API 格式 H2: 寫入 placeholder + BU hint

11. Agent 執行 Quality Gate:
    ✅ 業務邏輯失敗情境已對應到例外處理
    ⚠️ IO 欄位表第 3 欄 "process_score" 未在業務邏輯被引用
        [Auto-fix] [Manual-fix] [Ignore]

12. Agent 執行 summary_export → 產出 summary.json
    (從 BRD drafts + section_responses + anchor_entities 萃取
     8 個 archetype 衍生 key: anchor_case /
     business_value_signal / success_metrics / kill_criteria /
     hidden_constraints / downstream_consumer / exclusion_scope /
     reference_alignment)

13. Agent 在 thread 回最終訊息:
    ✅ BRD 初稿完成
       • 5 個 H1 BU 訪談章節已寫入 Doc
       • 3 個 H1 + 1 個 H2 由 agent 自動 placeholder (修訂記錄
         v1.0 / 初步技術評估 / 時程規劃 / 執行方式 → API 格式)
       [📄 Open in Google Docs]  [⬇ Export as docx]
       [📋 Copy summary JSON]    [⬇ Download summary.json]

14. (跨 session) BU 隔天想接續編修:
    /brd-resume cn_01HW...
    → 從 PostgresSaver 還原 state, 從中斷的章節訪談 /
      quality gate 任一斷點接續
```

---

## 8. 資料模型 (Data Model)

兩層：**business 表**由我們設計、**LangGraph checkpoint 表**由 PostgresSaver 自動建立。

### 8.1 Business 表（自管）

```sql
consultations
  id (uuid)                -- 同時當作 LangGraph thread_id
  slug                     -- 友善別名 e.g. consult-產險-NL01008-20260505;
                           --   unique per (initiated_by);對外顯示用
                           --   (F-5.1 / F-5.4 Layer 2 替代 UUID)
  slack_thread_ts          -- Slack thread timestamp;與 id 1:1 反查
                           --   (F-5.4 Layer 1 thread-aware auto-resume)
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
  from_exploration_id      -- uuid | null;若由 Explore_agent hand-off 而來
                           --   (詳 Explore_agent.md Appendix E)
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
    # Identity
    consultation_id: str
    slack_user_id: str
    # Pre-flight (8 欄;modal 收集後寫入)
    bu: Literal["產險", "壽險", "銀行", "證券"]
    project_type: str
    policy_code: str | None
    process_target: str
    execution_mode: Literal["realtime", "near_realtime", "batch"]
    result_type: str
    integration_systems: list[str]
    one_line_goal: str
    # Template (load_template 後注入,後續章節共用)
    template_questions: dict[str, list[str]]   # section_heading -> questions
    # Doc
    brd_doc_id: str | None
    brd_doc_url: str | None
    # Section loop state
    current_section: str
    completed_sections: list[str]
    current_section_responses: list[SectionResponse]   # 當前章節已收集回答
    current_draft: str | None                          # 當前章節草稿
    refine_count: int                                  # 該章節 refine 次數
    # Anchor (需求背景 Q2 答完後 LLM 抽出;F-2.2.4)
    anchor_entities: list[str]                         # 案例中的人物 / 系統 / 數字;下游章節 draft prompt 共用
    # Output
    summary_json: dict | None                          # F-4.5 結構化摘要
```

**簡化說明（v0.7 → v0.8）**：

- ❌ 移除 `global_clarifications`：原 Phase 1.5 收集欄位；題目改以 archetype 形式併入 `template_configs` 章節題庫，答案直接落在 `current_section_responses` / `section_responses` 表。
- ❌ 移除 `raw_input_text` / `routed_keywords`：keyword_route node 用完即丟，不需貫穿整個 graph；持久化軌跡仍寫入 `consultations.raw_input_text` / `routed_keywords` business 表（§8.1）。
- ❌ 移除 `few_shot_brds`：改 lazy load —— `draft` node 需要時直接讀 `template_questions` 中的 `few_shot_section_path` 從檔案撈，不放 state。
- ❌ 移除 `quality_issues`：改 `quality_gate` node 內 local 變數，gate 完即丟；BU 對 Auto-fix / Manual-fix / Ignore 的選擇直接觸發 side-effect（重 draft / 改 doc / 寫 audit log），不需貫穿 state。
- ❌ 移除 `docx_export_url`：`export` node 完成即回 Slack 訊息，不需保留 state。
- ✅ **保留 `anchor_entities`**：仍是跨章節共用 context，但生成位置從原 Phase 1.5 改為 section_loop 第 1 章節 Q2 答完時（F-2.2.4）。

結果：state 欄位數從 22 → 15（-32%），每個欄位都有清楚的跨 node 生命週期。

### 8.3 LangGraph checkpoint 表

由 `PostgresSaver.create_tables(conn)` 自動建立（同 Diff_agent §8.3）。**Consult_agent 必須使用 PostgresSaver**（不能用 MemorySaver），因為諮詢可能跨多日中斷續寫。

---

## 9. Appendix

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

### B-1. `template_configs/產險/preflight.yaml`（Layer 2 BU-specific options）

```yaml
# F-1.2 Layer 2：BU-specific 欄位的 options 來源
bu: 產險
policy_codes:
-code: NL01008
label: 產品責任險（食品業）
-code: NL01009
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
> 

### B-2. `template_configs/產險/風險評估.yaml`（章節引導題庫）

```yaml
project_type: 風險評估
title_template:"{bu} ACT - {topic} AI 工具 BRD"
sections:
需求背景:
questions:
-"目前 BU 在這個業務環節遇到什麼痛點？"
-"現行人工流程的瓶頸在哪？(時間 / 一致性 / 規模)"
-"為什麼選擇 AI 解決而非其他方案？"
-"預期帶來的業務價值是什麼？"
few_shot_section_path:"references/產險/NL01008_照片辨識.docx#需求背景"
業務邏輯:
questions:
-"AI 工具的處理對象是什麼？(具體描述輸入)"
-"判斷規則的核心邏輯是什麼？(一句話)"
-"判斷結果有哪幾種類型？分別代表什麼？"
-"失敗或無法判斷的情境如何處理？"
few_shot_section_path:"references/產險/NL01008_照片辨識.docx#業務邏輯"
io_table_schema:
input:
columns:["欄位名稱","欄位英文","資料格式","範例","備註"]
output:
columns:["欄位名稱","欄位英文","資料格式","範例","備註"]
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
產險:["產險","產品責任險","車險","ACT","核保","Smartbiz"]
壽險:["壽險","保單","理賠","新契約"]
銀行:["銀行","授信","信用卡","存款"]
證券:["證券","下單","交易","風控"]

project_type_keywords:
合理性檢核:["合理性","檢核","校驗","稽核"]
風險評估:["風險","評分","分流","高風險"]
流程評估:["流程","案件流程","工作流","SLA"]
文件辨識:["照片","OCR","圖片","文件辨識"]

policy_code_keywords:
NL01008:["產品責任險","店面照片","食品業"]
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

  "anchor_case": "CUST_001 於 2026-05-02 由業務員上傳店家照片 → 核保人員人工分類為固定店面 → 12 分鐘完成 → 報價系統取得 risk_score=0.7",
  "business_value_signal": "目前每週約 30 件需人工複審；若全月停擺，預估遞延報價金額約 NTD 200 萬",
  "success_metrics": [
    "3 個月內人工複審時間從 12 分鐘 / 件降至 < 3 分鐘",
    "高風險案件正確分流率 > 85%"
  ],
  "kill_criteria": [
    "連續 2 個月誤判率 > 10%",
    "業務員回退率 > 30%"
  ],
  "hidden_constraints": [
    "僅適用 NL01008 險種",
    "依賴 Smartbiz 同步完成 (T+1)"
  ],
  "downstream_consumer": {
    "role": "核保人員",
    "interface": "核保平台",
    "next_action": "決定是否進人工複核或直接核保"
  },
  "exclusion_scope": ["高金額（> NTD 500 萬）案件"],
  "reference_alignment": {
    "reference_brd": "NL01008 照片辨識",
    "similar_to": "規則樹 + 信心度退回機制",
    "different_from": "本次新增攤販 / 固定店面二分類；不需 OCR 文字判讀"
  },

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

### H. 章節訪談題庫補強 (Section Interview Probing Questions)

> **設計目的**：把 BA 真正會做的「具體化 / 挑戰 / 反問 / 盲點掃描」對話動作，以**章節擴充題**形式併入既有 `template_configs/<bu>/<project_type>.yaml` 的 `sections.*.questions`。**不再是獨立 phase**（v0.7 的 Phase 1.5 已拆解）。
>
> **與一般引導題的區別**：這些題目以 `archetype` 標記、有 `why_we_ask`（對 BU 透明）、有 `follow_up` 規則（模糊詞 / 過短偵測）、有 `feeds_into`（餵向 summary.json 哪個 key）。LLM 在 draft node 會優先引用這些題目的回答。
>
> **檔案位置**：每個 BU 的 `template_configs/<bu>/<project_type>.yaml` `sections.*` 之下擴充題目；不另建檔。

**Archetype → 章節對應地圖**：

| Archetype | 改放章節 | 在該章節的位置 | 餵向 summary.json |
| --- | --- | --- | --- |
| 動機型 + 反事實型 | 需求背景 | 第 1 題 | `business_value_signal` |
| **具體案例型 (keystone)** | 需求背景 | **第 2 題** | **`anchor_case` + state.anchor_entities** |
| 成功定義型 | 需求背景 | 結尾題 | `success_metrics`, `kill_criteria` |
| 比照型 | 需求背景 | 條件題（僅有 few-shot 時） | `reference_alignment` |
| 下游使用者型 | 執行方式 | 第 1 題 | `downstream_consumer` |
| 假設挖掘型 | 例外處理 | 第 1 題 | `hidden_constraints` |
| 邊界型 | 例外處理 | 條件題（僅自動化決策） | `exclusion_scope` |

8 種 archetype 全覆蓋（動機 / 案例 / 反事實 / 邊界 / 成功定義 / 假設挖掘 / 下游 / 比照）。

**完整題目 catalog**：

```yaml
# 把以下 archetype 題目按「改放章節」對應位置插入
# template_configs/<bu>/<project_type>.yaml 的 sections.*.questions

archetypes:

  - archetype: 動機型 + 反事實型
    place_in: 需求背景 / 第 1 題
    feeds_into:
      brd_sections: [需求背景]
      summary_json: [business_value_signal]
    question: |
      先不管 AI 怎麼做 —— 如果這件事「這個月都沒被處理」，
      實際上會發生什麼？
      （損失金額 / 客訴件數 / 合規風險 / 工時負擔 / 業務機會錯失，
       任一即可；附實際數字更佳）
    why_we_ask: 過濾偽需求；區分「想做」與「真的有痛」
    follow_up:
      vague_keywords: [可能, 大概, 應該, 視情況, 也許]
      probe: 你說的「{vague_phrase}」具體是？有上週的實際數字嗎？
    skip:
      allowed: true
      consequence: flag_for_ba_review=true；需求背景 prompt 加註「動機未明」

  - archetype: 具體案例型 (keystone)
    place_in: 需求背景 / 第 2 題
    keystone: true
    extracts: state.anchor_entities      # 此題答完後 LLM 抽 entities (F-2.2.4)
    feeds_into:
      brd_sections: [需求背景, 業務邏輯, User Cases, 例外處理, IO 欄位表]
      summary_json: [anchor_case]
    question: |
      請給我「最近一週（或最近一件）」真實發生的案件 ——
      從你看到輸入那一刻講起：
        1. 看到什麼資料 / 文件 / 客戶請求？
        2. 你 / 同事怎麼處理？中間經過幾個系統 / 幾個人？
        3. 做完之後，什麼狀態算「結束」？
      請用該案例的真實數字 / 名稱（個資請改代號 e.g. CUST_001），
      不要用範例化敘述。
    why_we_ask: |
      把抽象拉回地面；此案例會作為 anchor_entities，
      後續所有章節 LLM prompt 引用，降幻覺
    follow_up:
      vague_keywords: [通常, 一般而言, 有時候, 大致上]
      probe: 「通常」太抽象 —— 請鎖定最近一件真實案件，細節亂沒關係。
      min_length: 80
      short_probe: 還缺一點：用了什麼系統 / 結束狀態 / 過了幾個人？
    skip:
      allowed: true
      consequence: |
        state.anchor_entities = []；後續章節 draft 改用 fallback prompt
        （無 anchor 約束）；flag_for_ba_review=true；
        BA spot-check 時優先檢查章節敘述是否有自編情境

  - archetype: 成功定義型
    place_in: 需求背景 / 結尾題
    feeds_into:
      brd_sections: [需求背景]
      summary_json: [success_metrics, kill_criteria]
    question: |
      想像「上線 3 個月後的回顧會議」：
        (a) 看到什麼數字 / 現象，你會說「這個工具有用，值得擴大」？
        (b) 反過來，看到什麼會讓你想「下架它」？
      兩個答案一起給（各 1–2 點即可）。
    why_we_ask: KPI 與 kill criteria 不前置定義，後面 PM 一定回頭問
    follow_up:
      one_sided_probe: 那 (b) 呢？——「下架它」的訊號？
    skip:
      allowed: true
      consequence: summary_json.success_metrics=null; flag_for_ba_review

  - archetype: 比照型
    place_in: 需求背景 / 條件題
    trigger_condition: state.template_questions 內含 few_shot_section_path
    feeds_into:
      brd_sections: [需求背景, 業務邏輯]
      summary_json: [reference_alignment]
    question: |
      我幫你載入了參考：「{few_shot_brd_title}」。

      ── 該 BRD 摘要（3 bullets）──
      {few_shot_summary_3_bullets}
      ─────────────────────

      你的需求跟它：
        1. 最像的部分是哪一塊？（可沿用其結構）
        2. 最不一樣的地方是什麼？（這次客製重點）
    why_we_ask: few-shot 不是讓 BU 抄，是逼 critical comparison
    skip:
      allowed: true

  - archetype: 下游使用者型
    place_in: 執行方式 / 第 1 題
    feeds_into:
      brd_sections: [執行方式, User Cases, IO 欄位表]
      summary_json: [downstream_consumer, integration_systems]
    question: |
      AI 給出結果之後：
        1. 「第一個」看到結果的人是誰？（角色 / 部門 / 系統）
        2. 他在哪個介面看？（系統 A / Email / Slack / 報表）
        3. 他看完要做什麼決定或下一步動作？
      若第一個看到的是「另一個系統」而非人，請說明該系統拿到後做什麼。
    why_we_ask: 多數 BU 焦點在「AI 怎麼算」而忽略「結果給誰用」；
                此題決定 IO schema 與 integration_systems
    follow_up:
      self_consumer_probe: |
        那再下一棒呢？BU 處理完後資料會傳給誰？
        （往往才是真正的下游）
    skip:
      allowed: true
      consequence: summary_json.downstream_consumer=null; flag_for_ba_review

  - archetype: 假設挖掘型
    place_in: 例外處理 / 第 1 題
    feeds_into:
      brd_sections: [業務邏輯, 例外處理]
      summary_json: [hidden_constraints]
    question: |
      回顧需求背景 Q2 你提到的案例，
      「最容易被外人忽略的隱性條件」是什麼？例如：
        • 特殊客戶 / 通路（只有 VIP、只有電銷）
        • 前置資料（必須先有 X 才能跑這個流程）
        • 時間窗 / 季節性（月底結帳週才發生）
        • 外部系統 dependency（必須等 Smartbiz 同步完）
    why_we_ask: 隱性 assumption 是後期 RD 卡住的最大來源
    follow_up:
      no_answer_probe: |
        想不到的話反過來問：如果今天換你的同事接這案件，
        他最容易忽略 / 做錯的地方是什麼？
    skip:
      allowed: true
      consequence: 例外處理 prompt 加註「待 BA 補充隱性條件」

  - archetype: 邊界型
    place_in: 例外處理 / 條件題
    trigger_condition: |
      state.execution_mode in [realtime, near_realtime]
      OR state.result_type implies automated_decision
    feeds_into:
      brd_sections: [例外處理, 業務邏輯]
      summary_json: [exclusion_scope, guardrail_hints]
    question: |
      下面三種情境，你「不希望」AI 自動介入的是哪一種？
      （可複選 / 全選 / 全不選）
        (a) 高金額 / 高風險案件（怕誤判成本太高）
        (b) VIP / 特殊客戶（必須人工服務）
        (c) 規則無法窮舉的灰色地帶（經驗判斷為主）
      還有沒有第四種你想排除的情境？
    why_we_ask: 自動化決策必須前置定義「不自動」邊界
    skip:
      allowed: true
```

**anchor_entities 抽取邏輯（§4.2 F-2.2.4 已落地）**：

- 在 section_loop 處理「需求背景」**第 2 題**（archetype: 具體案例型 keystone）BU 答完之後、進入下一題之前，interview node 透過 LLM 從答案中抽出 entities（人物 / 系統 / 數字 / 時間 / 案例代號），寫入 `state.anchor_entities`。
- 後續所有章節的 `draft` node prompt 注入 `{anchor_case}`（該題完整答案）+ `{anchor_entities}`（list），LLM 草擬時敘述須圍繞此 anchor，避免自編情境。
- 若 BU Skip → `state.anchor_entities = []`、`flag_for_ba_review=true`、後續 draft 用 fallback prompt。

**v0.7 → v0.8 重構落地對照**：

| 變動類別 | v0.7 | v0.8 |
| --- | --- | --- |
| Graph node | 9 main + 1 sub-loop（含 `global_clarification` node） | 8 main + 1 sub-loop（拆掉 `global_clarification`） |
| State 欄位數 | 22 | 15（-32%） |
| 砍掉的 state 欄位 | — | `global_clarifications`, `raw_input_text`, `routed_keywords`, `few_shot_brds`, `quality_issues`, `docx_export_url` |
| 保留的設計精華 | Phase 1.5 全局澄清 + anchor_entities | anchor_entities（改在 section_loop Q2 後產生）+ archetype 題庫併入章節題庫 |
| summary.json 對外 8 keys | ✅ Phase 1.5 產出 | ✅ section_responses + drafts 萃取（不變） |
| BU 端體感 | Modal → Phase 1.5 (10–15 分鐘) → 5 章節 (30 分鐘) | Modal → 5 章節 (30–40 分鐘) |

---

*— End of PRD v0.8 —*