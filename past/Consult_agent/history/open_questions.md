# Consult_agent — Pre-PRD Open Questions

> 版本：v0.1
> 撰寫日期：2026-05-03
> 作者：victorchen@cathayholdings.com.tw
> 狀態：待對齊（pending alignment with Shane / team）
> 目的：在動筆寫 PRD v0.1 之前，先列出所有需要對齊的決策點與待解問題

---

## 0. 文件背景

本文件整理 Consult_agent（協助 BU 從 0 → 1 撰寫 BRD 的 agent）在 PRD 撰寫前需要對齊的問題。

**已知前提：**

- 姊妹專案 `Diff_agent/PRD.md` (v0.1, 2026-04-28, Owner: 雨諠 吳) 已定義會議錄音 → BRD 增量更新流程；架構、技術棧、Slack 互動模式皆已收斂。
- 本資料夾上層 `BRD_Agent/` 中已有 3 份範例 BRD（合理性檢核 / 外部風險照片辨識 / 案件流程評估），其中第 3 份為 BU 寫到一半的半成品，正是 Consult_agent 的目標客戶情境。
- Cathay 內部已有「金控 Data AI BA 團隊 BRD 標準模板」（Diff_agent PRD §3.3 已定義），Consult_agent 應沿用同一模板。

**本文件不是 PRD**，是 PRD 的前置對齊清單。每一題回答後即可寫入 PRD 對應章節。

---

## 1. 策略對齊問題（最高優先，需與 Shane / 團隊確認）

### Q1-1：Consult_agent 與 Diff_agent 是兩個獨立 agent，還是同一個 bot 的兩個 mode？

**為何重要：** 影響 Slack command 設計、共用程式碼結構、PRD 是否要合併。

**選項：**

- (A) 兩個獨立 agent — `/brd-new`（Consult） vs `/brd-update`（Diff）；各自獨立 PRD、獨立 LangGraph app；共用 BRD schema 與 Slack bot 帳號。
- (B) 統一 agent 兩個 mode — `/brd <create|update>`；單一 LangGraph app 內依使用者輸入分流到不同 sub-graph；單一 PRD（合併維護）。
- (C) 兩個 agent + 一個 router agent — 使用者只說「我要寫 BRD」，router 判斷該進 create flow 還是 update flow。

**我的建議：** (A)。理由：Diff_agent PRD 已經 freeze，合併會延後其交付（2026-05-08 PoC）；Consult_agent 可獨立開發再共用 Slack bot 入口。

---

### Q1-2：BRD 最終輸出格式 — docx / Google Docs / Markdown？

**為何重要：** 影響整個 pipeline 末端的實作（python-docx vs Google Docs API vs 純文字輸出）。

**已知事實：**

- 範例 3 份 BRD 都是 .docx 格式，檔名帶版本號（`_YYYYMMDD_Vx.y.docx`），人工維護版本軌跡。
- Diff_agent 假設 BRD 已存在於 Google Docs（為了用 Suggesting mode），但 Cathay 修訂記錄顯示 docx 才是 BA 之間實際流通的格式。
- 大量內容承載於表格（IO 欄位表 5 欄、判斷規則表 5–9 欄），表格生成是難點。

**選項：**

- (A) 直接產 docx（python-docx 套用金控模板）→ 與 Cathay 既有交付格式一致，但表格生成複雜。
- (B) 產 Markdown，由 BA 手動轉 docx → MVP 簡單、可控，但增加人工步驟。
- (C) 產 Google Docs（與 Diff_agent 對齊）→ 後續 Diff_agent 直接接手 update lifecycle，但需確認 Cathay 是否能接受 Google Docs 作為交付格式。

**待確認：** 金控 / 產險端正式交付給 AI 科 / CD 科時用什麼格式？docx 是必要的嗎？

---

### Q1-3：BU 真實進入路徑 — 純文字 / 會議錄音 / 簡報？

**為何重要：** 決定 Consult_agent 與 Diff_agent 的分工邊界。

**情境：**

- 情境 A：BU 直接在 Slack 打字描述需求 → Consult_agent 引導
- 情境 B：BU 先開內部會議口頭討論 → 錄音 → 餵給 Diff_agent（但此時 BRD 還不存在，Diff_agent 設計上需要 existing Doc）
- 情境 C：BU 已有 PPT / Word 散稿 → 上傳 → Consult_agent 萃取後引導

**可能結論：** Consult_agent 處理 A + C；若 BU 想用會議錄音 0 → 1，需考慮：
- 改造 Diff_agent 支援「target Doc 不存在時先建立空模板再 apply suggestions」
- 或在 Consult_agent 加 ASR node（與 Diff_agent 同樣 Gemini Files API）

---

### Q1-4：跨 BU 通用性的時程 — MVP 限定產險嗎？

**為何重要：** 影響 BRD content model 的泛化程度。

**已知事實：**

- 3 份範例 BRD 全為產險 ACT（Title 都是「產險 ACT - <主題> AI 工具 BRD」）。
- Cathay Holdings 包含壽險 / 銀行 / 證券 / 產險，各 BU 是否使用同一 BRD 模板？未知。

**待確認：**

- 「金控 Data AI BA 團隊 BRD 標準模板」是否真的跨所有 BU 一致？
- MVP 是否先綁產險（NL01008 產品責任險）？
- 其他 BU 的 BRD 範例是否能取得 1–2 份做對照？

**建議寫入 PRD 為 Open Question + Risk**。

---

### Q1-5：使用者究竟是誰 — BA 還是 BU SME？

**為何重要：** 兩種 persona 的引導策略差很多。

**從修訂記錄觀察：**

- 範例 BRD 1：金控 Polly、Amber 寫初稿；產險 BU Luke、Abby（數據）confirm
- 範例 BRD 2：金控 Haily、Lynn 寫
- 範例 BRD 3：未填人員（半成品）

→ **看起來實際撰寫者是「金控 Data AI BA 團隊」**，產險 BU 只是 SME 提供資訊與 confirm。

**選項：**

- (A) Agent 服務 BA — 引導 BA 把從 BU 訪談到的資訊結構化寫入 BRD
- (B) Agent 服務 BU SME — 讓 BU 自助寫初稿，BA 後續潤飾
- (C) Agent 服務雙方 — 在不同階段切換角色

**我的建議：** (A) 為 MVP 主要 persona — 與 Diff_agent 一致（Diff_agent 也是 BA-facing），且修訂記錄顯示 BA 是 owner。BU SME 自助（B）為 V2 考慮。

---

## 2. 內容與情境設計問題

### Q2-1：MVP 涵蓋 BRD 的哪幾個章節？

**Cathay BRD 標準模板 8 章 H1：**

1. 修訂記錄
2. 需求背景
3. 需求分析（含 5 個 H2：業務流程 / 業務邏輯 / 輸入規則 / 判斷規則 / 輸出說明）
4. 執行方式（含 2 個 H2：系統欄位資料格式 / API 格式）
5. User Cases
6. 例外處理
7. 初步技術評估
8. 時程規劃

**觀察：**

- 範例 BRD 中「初步技術評估」「API 格式」常標註「由 AI 科 / CD 科協助」→ **不是 BU 寫的**
- 範例 BRD 中「User Cases」「時程規劃」常為空 → BU 可能不太會寫
- BU 真正會寫且範例最完整的是：**需求背景 / 業務邏輯 / 判斷規則 / 輸入輸出欄位**

**待決定：** MVP 是否聚焦這 4 章？其他章節（執行方式 / 例外處理）是否一起做？

**我的建議：** MVP = 需求背景 + 業務邏輯 + 判斷規則 + IO 欄位表（4 章），明確排除「初步技術評估」「API 格式」（兩者本來就由其他團隊接手）。

---

### Q2-2：Scenario 分類體系 — LangGraph 怎麼分支？

**從 3 份 BRD 萃取的維度：**

| 維度 | 觀察值 | 建議在 graph 中的用法 |
|---|---|---|
| 險種代碼 | NL01008 產品責任險（3 份都是） | Pre-flight 收集 → 載入對應 BU 詞彙表 |
| 專案類型 | 合理性檢核 / 風險評估 / 流程評估 | 決定 sub-graph 主路徑 |
| 處理對象 | 文字 / 圖片 / 結構化資料 | 影響 IO 欄位表引導問題 |
| 執行模式 | 即時（15 秒）vs 批次（15 分鐘） | 影響「執行方式」章節範本 |
| 結果類型 | Pass/Fail/Reminder + 分數 + 文字說明 | 影響「輸出內容」章節範本 |
| 介接系統 | Smartbiz / 核保平台 / postgreSQL / guardrail | 觸發「初步技術評估」依賴清單 |

**待決定：**

- 上述哪些維度作為 **必填 pre-flight**？
- 哪些用 **觸發詞偵測** 動態切換 sub-graph（例：BU 講到「規則」→ 進規則樹引導器）？
- Pre-flight 是否需要先讓 BU 上傳「需求草稿」或「會議筆記」供 agent 預判？

---

### Q2-3：對話流是「結構化主幹 + 開放支線」還是「全結構化」還是「全自由」？

**從 Diff_agent PRD 沒有明示這一點，但 Consult_agent 必須決定。**

**選項：**

- (A) 全結構化 — 依 BRD 章節順序逐一引導，每章節固定問題清單。優點：完整性可保證；缺點：像填表單。
- (B) 主幹結構化、支線開放（建議） — 主流程跑章節，BU 講到關鍵詞觸發專家 sub-graph。
- (C) 全自由 — 自由聊，agent 動態判斷該補哪一章。優點：自然；缺點：完整性難保。

**我的建議：** (B)。

---

### Q2-4：Quality Gate 怎麼判斷 BRD 已完成？

**待決定：**

- 章節 completeness check：每章節是否填滿？
- 跨章節一致性 check：例外處理是否覆蓋業務邏輯所有 fail 路徑？IO 欄位是否在業務邏輯被引用？
- LLM-as-judge：用 LLM 對照範例 BRD 評分？
- BA 主觀確認：最終由 BA 在 Slack 按「Done」結束流程？

---

## 3. 技術與架構問題

### Q3-1：是否 100% 沿用 Diff_agent 的技術棧？

**Diff_agent 已驗證的技術棧（PRD §6）：**

- LangGraph + langchain-core + PostgresSaver
- Gemini 2.5 Pro（含 audio Files API）+ langchain-google-genai
- slack-bolt
- google-api-python-client（Docs API + Drive API）
- google-auth + google-auth-oauthlib（per-user OAuth）

**待確認：**

- Consult_agent 若改採 docx 輸出（見 Q1-2），需引入 python-docx，是否會與既有環境衝突？
- 若 MVP 不寫 Google Docs，是否還需要 OAuth flow？（簡化點）
- 是否考慮加入 RAG 讀取既有 BRD 範例作為 few-shot reference？Diff_agent 沒做 RAG（倚賴 Gemini 1M context），Consult_agent 是否同樣？

---

### Q3-2：資料模型如何設計？

**參考 Diff_agent 的 business 表：`meetings` / `edit_proposals` / `oauth_tokens`**

**Consult_agent 建議新增表：**

- `consultations` — 一場諮詢 = 一個 LangGraph thread_id
- `brd_drafts` — 諮詢過程中的 BRD 草稿（含版本軌跡）
- `section_responses` — BU 對每個章節引導問題的回答

**待決定：**

- 是否與 Diff_agent 共用同一個 Postgres database？schema 命名如何區隔（`consult_*` / `diff_*`）？
- 草稿如何持久化 — 純結構化（每章節 JSON）還是直接存 docx blob？

---

### Q3-3：BU 隱私與合規

**Diff_agent PRD 沒有專門處理 PII masking（只在 §10 P2 timeline 帶過 "PII masking"），Consult_agent 也需要。**

**待確認：**

- BU 在 Slack 對話中可能講出客戶資料、案件號（如範例中的 qsbz240409061647）— 是否需要 redact？
- LLM 端送進 Gemini 的內容是否需走金控內部 guardrail（範例 BRD 提到「需串接產險內部的 guardrail」）？
- audit trail 要保留到什麼程度（FSC / 個資法考量）？

---

## 4. 範圍與 MVP 問題

### Q4-1：MVP 時程？

**參考 Diff_agent：2 週 PoC（約 10 個工作日），2026-05-08 完成。**

**待決定：** Consult_agent 起跑日？預期 PoC 日？是否與 Diff_agent 整合測試（例：Consult_agent 產出 BRD → Diff_agent 接手 update）？

---

### Q4-2：MVP 不做的事（Non-Goals）— 我建議的清單

- ❌ 多 BU 通用（先綁產險 NL01008）
- ❌ 中後段章節（初步技術評估 / API 格式 / 時程規劃 — 這些非 BU 負責）
- ❌ 流程圖生成（圖片合成風險高；Diff_agent 也沒做）
- ❌ 修訂記錄表自動填寫（手動就好）
- ❌ 跨諮詢學習（不在不同 BU 之間 transfer learning）
- ❌ 即時多人協作（單一 BA 單一 thread）

**待 Shane / 團隊 confirm 此清單。**

---

### Q4-3：成功指標？

**Diff_agent 用：延遲 < 5 分鐘 / Suggestion Accept Rate ≥ 50% / 幻覺 < 1%**

**Consult_agent 候選指標：**

- BRD 第一版產出時間（傳統 X 小時 → agent 後 Y 分鐘）
- BU 對 agent 產出的修改幅度（diff ratio）
- BA 對 agent 產出的接受率（章節 accept count / total）
- 下游 IT / AI 科退件率（agent 後 vs 之前的對比）
- 半成品比例（範例 BRD 3 那種空白 BRD 的數量降低）

**待決定哪 1–3 個作為 PoC gate。**

---

## 5. 已識別的風險（先記下，PRD 寫入 Risks 章節）

- **R-A**：BRD 模板隨時間變更 — Diff_agent §12.1 R-6 已提到 heading 樣式不一致；Consult_agent 若硬編模板可能失效。**緩解：** 抽出模板為設定檔。
- **R-B**：BU 講不出來 — agent 引導再精細也救不了 BU 對需求毫無概念的情境（範例 BRD 3 可能就是這種）。**緩解：** 加「載入相似專案 BRD 作為 few-shot」按鈕。
- **R-C**：與 Diff_agent 邊界模糊 — 若 BU 在 Consult 流程中又想插入會議錄音怎麼辦？**緩解：** Q1-3 對齊後決定。
- **R-D**：跨 BU 模板差異未知 — 見 Q1-4。
- **R-E**：產出格式（docx）vs Diff_agent 預期（Google Docs）不一致 — 見 Q1-2。

---

## 6. 建議的下一步

1. **本週內**：找 Shane 過一次本文件，逐題對齊（Q1-1 ~ Q1-5 為必過）
2. **下週**：依對齊結果寫 Consult_agent PRD v0.1 Draft（仿 Diff_agent PRD 結構）
3. **若可能**：找 1 位金控 BA（如 Polly / Amber / Haily / Lynn）做 30 分鐘訪談，了解他們寫 BRD 時最卡的環節，作為 PRD §1 背景動機的素材
4. **若可能**：取得 1–2 份非產險 BU 的 BRD 範例，驗證模板跨 BU 一致性（Q1-4）

---

*— End of Open Questions v0.1 —*
