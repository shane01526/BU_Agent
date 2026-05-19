# BRD Agent — 三專案總覽 (Overview)

> 版本：v0.1
> 撰寫日期：2026-05-05
> 範圍：Explore_agent / Consult_agent / Diff_agent 三個並行子專案的對照與整合視圖
> 對應 PRD：`Explore_agent/explore_agent.md` v0.1 / `Consult_agent/consult_agent.md` v0.8 / `Diff_agent/Diff_PRD.md` v0.1

---

## 1. 背景動機 (Background & Motivation)

各 BU 向金控 Data AI BA 團隊提出 AI 工具需求時，須產出符合「Data AI BA 團隊 BRD 標準模板」的 BRD，以利後續移交給 AI 科 / CD 科進行技術評估與開發。整條 BRD 生命週期目前存在三段式痛點：

| 階段 | 痛點 | 現狀觀察 |
| --- | --- | --- |
| **0 → 候選方向** | BU 被要求導入 AI，但**根本不知道要做什麼**；缺乏 AI 適用度判斷力 | 對話常停在「我們也想做點 AI 但不知道從哪開始」 |
| **候選 → BRD v1.0** | BU 雖熟業務、不熟模板；章節大量留白、IO 欄位未對齊規則 | 參考 `BRD_案件流程評估_20260113_V1.1.docx`（不完整草稿） |
| **BRD v1.0 → v1.1+** | 會議結論手動回寫成本高；遺漏與失真；變更追蹤困難 | 60 分鐘會議約需 30–60 分鐘整理，難回溯「哪場會議改了哪條規則」 |

三姊妹專案的設計，就是把上述三段式痛點各拆成一個專屬 agent，**每個 agent 服務一段 BU 旅程，但共享同一套 Slack bot / Postgres / OAuth 基礎設施**，避免跨 agent 重複 onboard。

---

## 2. 目標情境 (Target Scenarios)

依 BU 進場時的「想法明確程度」分流到不同 agent：

| BU 起始狀態 | 觸發 slash | 對應 agent | 終點產物 |
| --- | --- | --- | --- |
| **0 idea**：被要求導入 AI 但不知道做什麼 | `/brd-explore` | **Explore_agent** | top 3 候選方向 + 預測的 Consult pre-flight 8 欄 |
| **vague idea**：知道大方向但講不出規則細節 | `/brd-new` | **Consult_agent** | BRD v1.0 Google Doc + `summary.json`（給 PM/RD） |
| **clear idea + 既有 BRD**：開完需求會議要更新 | `/brd-update` | **Diff_agent** | Google Docs Suggesting-mode edits + anchored comments |
| **既有 Explore 結果想接著寫** | `/brd-new --from-exploration <id>` | Consult（從 Explore 接力） | 同 Consult 終點 |

> 設計邏輯：每個 agent 都假設**前一段已完成或不需要**，避免多模式糾纏；若 BU 跨階段使用，透過 deep link 而非單體巨無霸 agent 串接。

---

## 3. 使用者 & User Stories

### 3.1 Persona

| 角色 | 三姊妹中的位置 | 主要訴求 |
| --- | --- | --- |
| **BU SME** | 三個 agent 的對話對象 | 用日常語言講需求，不必記 BRD 模板格式 |
| **PM** | Consult 輸出消費者 | 不讀整份 BRD 即可掌握需求要點 → 開技術 epic |
| **RD / Tech Lead** | Consult / Diff 輸出消費者 | 拿到 IO schema + 業務規則即可開工；遇到 ambiguity 時可回溯 |
| **BA** | Diff 主要使用者；Consult / Explore 監督者 | 由「撰稿者」轉為「品質審核 + 異常處理」 |
| **AI 科 / CD 科** | 終端讀者 | 接到結構正規的 BRD，可直接做技術評估 |

### 3.2 單一模式 User Stories（每個 agent 各一）

**US-A — 只用 Explore（決策者：「先看看能做什麼」）**
產險 BU 主管被要求「半年內導入一個 AI 工具」但無具體想法。BU 在 Slack 輸入 `/brd-explore`，回答 5 必選 + 部分條件題（每題 ≤ 1 分鐘），Agent 回傳 top 3 候選（理賠文件分類 / 客訴語意分群 / 風險照片辨識）並附 5 維度 AI 適用度評分。BU 與主管討論後決定**先暫存 candidate JSON**、不立刻啟動 Consult，等預算盤點後再續。

**US-B — 只用 Consult（已有想法、現要寫 BRD）**
產險 BU SME 接到上級指示「做 NL01008 店面照片風險評估的 AI 工具」。BU 直接 `/brd-new 想做產險 NL01008 店面照片風險評估的 AI 工具`，Agent 偵測候選分類在 pre-flight modal 預先勾選，BU 確認後，逐章被引導完成「需求背景 → 業務邏輯 → IO 規則 → 例外處理 → User Cases」5 個 H1，產出 BRD v1.0 Doc + `summary.json`。

**US-C — 只用 Diff（既有 BRD，定期會議更新）**
BA 已有《合理性檢核 BRD》v1.0 在 Google Docs，剛開完「食品業判斷規則討論會議」。BA 在 `#brd-updates` channel 輸入 `/brd-update <doc-url>` 並上傳會議錄音 mp3。Agent 5 分鐘內在 Doc 寫入 5 條 Suggesting-mode edits（每條附 timestamp + quote anchored comment），BA 在 Docs UI 端逐項 Accept / Reject。

### 3.3 完整三段旅程 User Story（**重點**）

**US-D — Explore → Consult → Diff 完整鏈路（壽險 0 idea → 試行版 → 試行後迭代）**

> 跨度約 3 週；對應 BU 從「沒想法」一路到「v1.1 修訂」的完整路徑。

1. **Day 1（Explore 階段）** — 壽險 BU 主管接到「導入一個 AI 工具」KPI，但本 BU 之前無 AI 案例。BU SME 在 Slack `#brd-consultation` 輸入 `/brd-explore`，回答 5 題 discovery：日常最重複的工作（保單審核文件分類）、手作環節最痛點（理賠文件型別 OCR 後人工歸檔耗時）、量級（每月 5,000 件）、可逆性（誤分類僅延遲處理、可人工救回）、現有解（無）。

2. **Day 1 末（Explore 收尾）** — Agent 跑 cluster_pain_points + 5 維度 rubric，回傳 top 3：
   - **C1：理賠文件型別自動分類**（綜合分 4.6 / 5）
   - **C2：保單條款 QA 內網助手**（4.0 / 5）
   - **C3：理賠話術品質檢核**（3.4 / 5；可逆性低，標 ⚠️）

   BU 與主管挑 C1，按 Slack「✅ 選這個」按鈕。Agent 預測 C1 的 Consult pre-flight 8 欄並回 deep link：

   ```
   /brd-new --from-exploration ex_01HW...
   ```

3. **Day 2 (Consult 階段)** — BU 點 deep link，Slack 開新 thread，pre-flight modal 已**預先填好** bu=壽險 / project_type=分類 / process_target=理賠文件型別 / 等 8 欄，BU 一眼確認、按提交。Agent 載入「壽險 / 分類」template + 產險 NL01008 照片辨識 BRD 作 cross-BU few-shot，建立空 BRD Doc。

4. **Day 2–4（Consult 訪談）** — BU 逐章在 Slack 答題：
   - 需求背景 Q2（具體案例型 keystone）→ 抽出 `anchor_entities = ["保單號 LF12345", "理賠申請書", "醫療收據", "診斷證明書"]`
   - 業務邏輯、IO 規則、例外處理、User Cases 章節 draft 全部以此 anchor 為錨點防幻覺
   - 每章 Accept/Refine/Skip；中途下班 → 隔天回到 thread 自動 resume（thread-aware Layer 1）

5. **Day 5（Consult 完成）** — Agent 跑 quality_gate 後產出：
   - BRD v1.0 Google Doc（給 BA / AI 科）
   - `summary.json`（給 PM / RD：one_line_goal / key_business_rules / io_fields / exception_cases / open_for_ai_team）
   - 自動 @ BA 進 thread review

6. **Week 2 (BA review + 內部會議)** — BA 在 Doc 端做小幅修飾、定稿為 `BRD_理賠文件分類_20260512_V1.0.docx`。AI 科召開技術評估會議，與會 BU + RD 討論欄位細節，得出 3 條補充 / 修正。

7. **Week 3（Diff 階段）** — BA 把 60 分鐘會議錄音拖到 `#brd-updates`，輸入 `/brd-update https://docs.google.com/.../理賠文件分類`。Agent 5 分鐘後在 Doc 寫入 4 條 Suggesting-mode 建議（業務邏輯 update / IO 欄位表更新提醒 / 例外處理 insert / 初步技術評估 update），每條附 `[00:18:42] "..."` 形式 anchored comment。BA 逐條 Accept，Doc 自動進入 v1.1 — 全鏈路無人工聽打、無模板格式記憶負擔。

> **關鍵交接點**：(i) Explore → Consult 透過 `--from-exploration` deep link + `predict_consult_fields`；(ii) Consult → Diff 透過共用 BRD doc_id（Consult 寫 final、Diff 寫 Suggesting）。三 agent 共用 oauth_tokens、Slack bot、Postgres，BU 視角是同一個 bot 的不同對話。

---

## 4. 簡短 Pipeline (Pipeline at a Glance)

每個 agent 的核心 node 序列：

| Agent | Slash | Node 序列（簡寫） | HITL 機制 |
| --- | --- | --- | --- |
| **Explore** | `/brd-explore` | `collect_context` → `load_questions` → **discovery_loop** (`ask` ⇄ `probe`) → `cluster_pain_points` → `score_candidates` → `predict_consult_fields` → `present_in_slack` → `await_selection` → `handoff_to_consult` | LangGraph `interrupt()` 在 Slack 端 |
| **Consult** | `/brd-new` | `keyword_route` → `collect_metadata` → `load_template` → `create_doc` → **section_loop** (`interview` → `draft` → `review` → `apply`) × 5 H1 → `fill_placeholders` → `quality_gate` → `summary_export` → `export` (optional) | LangGraph `interrupt()` 在 Slack 端 |
| **Diff** | `/brd-update` | `transcribe` → `fetch_doc` → `extract_edits` → `apply_as_suggestions` | Google Docs Suggesting mode（不在 graph 內 interrupt） |

**共通設計**：每場 run = 一個 `consultation_id` / `exploration_id` / `meeting_id`（同時為 LangGraph `thread_id`），state 由 PostgresSaver 持久化；Slack thread_ts ↔ session_id 1:1 對應，支援 thread-aware auto-resume（Layer 1）+ `/brd-resume` slash fallback（Layer 2）。

---

## 5. 三種功能的簡要架構圖 (Architecture Sketches)

### 5.1 Explore_agent（0 → 候選）

```
                  ┌─────────────┐
   BU ──────────▶ │  Slack Bot  │ ◀── 共用 bot 帳號
                  └──────┬──────┘
                         │ /brd-explore
                         ▼
   ╔═══════════ LangGraph (Explore) ═══════════╗
   ║   collect_context (modal: bu + 角色簡述)   ║
   ║          ▼                                ║
   ║   load_questions (依 bu 載 yaml)           ║
   ║          ▼                                ║
   ║   ┌───── discovery_loop ─────┐            ║
   ║   │  ask  ◀interrupt()▶  probe│            ║
   ║   └───────────────────────────┘            ║
   ║          ▼                                ║
   ║   cluster_pain_points (LLM)               ║
   ║          ▼                                ║
   ║   score_candidates (5 維度 rubric, top 3) ║
   ║          ▼                                ║
   ║   predict_consult_fields (8 欄)           ║
   ║          ▼                                ║
   ║   present_in_slack ─── await_selection    ║
   ║                       (選 / 重探 / 放棄)   ║
   ║          ▼                                ║
   ║   handoff_to_consult (deep link)          ║
   ╚════════════════════════════════════════════╝
                  │
                  ▼
       Postgres: explorations.result_json
       (不寫 Doc；候選 JSON 留在 DB)
```

### 5.2 Consult_agent（候選 → BRD v1.0）

```
                  ┌─────────────┐
   BU ──────────▶ │  Slack Bot  │
                  └──────┬──────┘
                         │ /brd-new [--from-exploration <id>]
                         ▼
   ╔═══════════ LangGraph (Consult) ═══════════╗
   ║   keyword_route (raw text → 候選分類)      ║
   ║          ▼                                ║
   ║   collect_metadata (pre-flight 8 題)       ║
   ║          ▼                                ║
   ║   load_template (YAML + few-shot BRD)     ║
   ║          ▼                                ║
   ║   create_doc (Docs API: Title + 8 H1)     ║
   ║          ▼                                ║
   ║   ┌───── section_loop × 5 H1 ─────┐       ║
   ║   │ interview ─◀interrupt() BU▶─  │       ║
   ║   │   ↓ (Q2 後抽 anchor_entities) │       ║
   ║   │ draft   (Gemini structured)   │       ║
   ║   │   ↓                           │       ║
   ║   │ review  ─◀interrupt() BU▶─    │       ║
   ║   │         (Accept/Refine/Skip)  │       ║
   ║   │   ↓                           │       ║
   ║   │ apply   (Docs API batchUpdate)│       ║
   ║   └────────────────────────────────┘       ║
   ║          ▼                                ║
   ║   fill_placeholders (技術評估/API/修訂)    ║
   ║          ▼                                ║
   ║   quality_gate (跨章節一致性)              ║
   ║          ▼                                ║
   ║   summary_export → JSON                   ║
   ║          ▼                                ║
   ║   export (optional → docx)                ║
   ╚════════════════════════════════════════════╝
                  │
                  ▼
       Google Docs (BRD v1.0) + summary.json + Postgres
```

### 5.3 Diff_agent（v1.0 → v1.1+）

```
                  ┌─────────────┐
   BA ──────────▶ │  Slack Bot  │
                  └──────┬──────┘
                         │ /brd-update <doc-url> + audio
                         ▼
   ╔═══════════ LangGraph (Diff) ═══════════╗
   ║   transcribe (Gemini audio)            ║
   ║          ▼                              ║
   ║   fetch_doc (Docs API + Comments API   ║
   ║              讀上輪 reject reasons)     ║
   ║          ▼                              ║
   ║   extract_edits (LLM structured →      ║
   ║       insert/update/delete proposals)  ║
   ║          ▼                              ║
   ║   apply_as_suggestions                 ║
   ║   (Docs API batchUpdate Suggesting mode║
   ║    + comments.create timestamp + quote)║
   ╚═════════════════════════════════════════╝
                  │
                  ▼
       Google Docs (Suggesting mode)
       BA 在 Docs UI 逐條 Accept / Reject
       (Agent 不參與 review，audit 由 Docs Revision History)
```

---

## 6. 技術選型概述 (Tech Stack Overview)

三 agent 共用同一組技術棧，差異只在「是否寫 Doc」與「checkpointer 必要性」。

| 層次 | 共用選型 | Explore | Consult | Diff |
| --- | --- | --- | --- | --- |
| Pipeline 框架 | LangGraph + `langchain-core` | ✅ | ✅ | ✅ |
| HITL 機制 | LangGraph `interrupt()` | ✅ Slack 等回應 | ✅ Slack 等回應 | ❌ 改用 Docs Suggesting mode |
| Checkpointer | PostgresSaver | ✅ 必須持久化 | ✅ 必須持久化 | ✅（audit 用，P1 可 MemorySaver） |
| LLM | Gemini 2.5 Pro (`langchain-google-genai`) | ✅ | ✅ | ✅ |
| 結構化輸出 | `with_structured_output` | cluster / score / predict | section draft / summary | edit proposals |
| ASR | Gemini 2.5 Pro audio (Files API) | — | — | ✅ |
| Slack SDK | `slack-bolt` (Python)，**共用同一 bot 帳號** | ✅ | ✅ | ✅ |
| Doc Ops | `google-api-python-client` (Docs + Drive API) | — | ✅ 寫 final | ✅ 寫 Suggestion |
| OAuth | `google-auth` + `google-auth-oauthlib`，**共用 `oauth_tokens` 表** | ✅ | ✅ | ✅ |
| Backend | FastAPI + Postgres（同 DB 不同 schema） | ✅ | ✅ | ✅ |
| Few-shot 策略 | 整份歷史文件塞 1M context（不做 chunking / RAG） | discovery 題庫 yaml | template + few-shot BRD | 整份目標 Doc |
| 設定檔 | YAML | `explore_configs/<bu>.yaml` + `scoring_rubric.yaml` | `template_configs/<bu>/<project_type>.yaml` | — |
| Deploy | 本機 dev (uvicorn + ngrok) → Cathay 內網 (V1) | ✅ | ✅ | ✅ |

> **共用基礎設施一覽**：1 個 Slack bot 帳號 / 1 個 Postgres database / 1 張 `oauth_tokens` 表 / 同一套 Gemini quota 與部署管道。新增 BU 不改 graph 程式碼，只加 YAML config。

---

## 7. 範例對照表 (Reference Tables)

### 7.1 三種模式對照

| 維度 | Explore | Consult | Diff |
| --- | --- | --- | --- |
| 服務的 BU 心智狀態 | 0 idea | vague / clear idea | 已有 BRD 要更新 |
| 主要使用者 | BU SME + 主管 | BU SME（BA 監督） | BA（BU/RD 為次要） |
| 平均互動時長 | 5–10 分鐘 | 跨多日（總計 30–60 分鐘對話 + 中斷） | 5 分鐘等候 + Docs review |
| 觸發指令 | `/brd-explore [raw text]` | `/brd-new [raw text]` 或 `/brd-new --from-exploration <id>` | `/brd-update <doc-url>` + 音檔 |
| 終點產物 | top 3 候選 JSON + 預測 8 欄 | BRD v1.0 Doc + summary.json | Suggesting-mode edits + comments |
| 主要 HITL 介面 | Slack（thread 對話 + 候選按鈕） | Slack（thread 訪談 + Accept/Refine/Skip） | Google Docs（Suggesting mode 逐條 Accept/Reject） |
| Doc 寫入策略 | ❌ 不寫 Doc | ✅ 直接寫 final | ✅ 寫 Suggestion，不動 final |
| Few-shot 來源 | `explore_configs/<bu>.yaml` | `template_configs/<bu>/<project_type>.yaml` + 歷史 BRD | 上輪 reject comments + 整份目標 Doc |
| Postgres 主表 | `explorations` | `consultations` + `brd_drafts` + `section_responses` | `meetings` + `edit_proposals` |

### 7.2 三種模式的「輸入 / 輸出」對照

| Agent | 必填輸入 | 可選輸入 | 結構化輸出 |
| --- | --- | --- | --- |
| **Explore** | bu / 角色簡述（modal 2 欄） | raw text hint（重排題目用） | Candidate JSON（top 3 + scores + 預測 Consult 8 欄） |
| **Consult** | pre-flight 8 欄（bu / project_type / policy_code / …）+ 各章節對話回應 | raw text → keyword_route 預先勾選；`--from-exploration <id>` 帶入候選 | BRD v1.0 Google Doc（8 H1）+ `summary.json` |
| **Diff** | Google Docs URL + 會議錄音（≤ 60 min, ≤ 200 MB） | 會議主題 hint | Edit proposals JSON + Docs Suggestions + anchored comments |

### 7.3 Slash 指令彙整

| Slash | 啟動位置 | 行為 | 對應 thread |
| --- | --- | --- | --- |
| `/brd-explore` | channel main / DM（拒絕 thread 內） | 開新 thread，啟動 Explore | 1 session = 1 thread |
| `/brd-new` | channel main / DM | 開新 thread，啟動 Consult | 1 session = 1 thread |
| `/brd-new --from-exploration <id>` | channel main / DM（多由 Explore deep link 觸發） | 開新 thread，pre-flight 預填 | 1 session = 1 thread |
| `/brd-update <doc-url>` | channel main / DM | 開新 thread，啟動 Diff | 1 session = 1 thread |
| `/brd-resume <slug-or-id>` | 任意位置 | Layer 2 fallback：手動接續中斷 session | resume 至原 thread |

### 7.4 端到端時程示例（以 US-D 壽險 BU 完整鏈路為例）

| 階段 | 工時 | 主要產物 |
| --- | --- | --- |
| Explore 對話 | Day 1（10 分鐘 × 2 段） | top 3 候選 JSON、選定 C1「理賠文件型別自動分類」 |
| Consult pre-flight + 訪談 | Day 2–4（跨日 resume，總對話 ~45 分鐘） | BRD v1.0 Doc（5 H1 BU 章節 + 3 placeholder 章節）+ summary.json |
| BA 審稿 + AI 科技評會議 | Week 2 | 定稿 v1.0、會議錄音 60 分鐘 |
| Diff 增量更新 | Week 3（5 分鐘處理 + Docs review） | v1.1 Doc（4 條 Accepted suggestions） |

### 7.5 三 agent 共用基礎設施一覽

| 資源 | 內容 |
| --- | --- |
| Slack bot 帳號 | 1 個（同一 workspace 內，3 個 slash 都掛在這個 bot） |
| Postgres database | 1 個；business 表分屬 3 schema (explorations / consultations / meetings)；checkpoint 表由 PostgresSaver 統一建立 |
| `oauth_tokens` 表 | 1 張共用（每位 BU/BA 一筆 row，記 Google refresh token；3 agent 都可用） |
| Gemini quota | 1 組 service account |
| 部署管道 | 本機 dev (uvicorn + ngrok) → Cathay 內網 (V1) |
| 共用設計約定 | thread_ts ↔ session_id 1:1；slash 限 channel main / DM；每個 interrupt 訊息附「💾 進度已自動暫存」+「想開新諮詢?」hint；App Home Dashboard quick-action（V2） |

---

*— End of Overview v0.1 —*
