# BU Agent — 整體使用流程與架構規劃 (Overview)

> 版本：v0.3
> 撰寫日期：2026-05-12
> 範圍：BU Agent 階段（Explore mode + Consult mode）的整體使用流程、階段交接，與自建前端架構草案
> 與舊架構關係：本文重新規劃 BU 端體驗，把舊 `Explore_agent` + `Consult_agent` 兩個並列 agent 收斂為**單一 BU Agent 內的兩個 mode**，並棄用 Slack、改採**自建 web 前端**；舊 PRD（`Explore_agent/explore_agent.md` v0.1 / `Consult_agent/consult_agent.md` v0.8 / `BU_Agent_v2_題庫.md`）作為功能細節的設計參考，**不被本文取代**

> **v0.3 修訂重點**（2026-05-12 放寬內網限制假設）：
> - 移除「必須內網部署」硬性假設；預設改為 **cloud 部署**（待法遵與資安個案核可），但保留 on-prem / private cloud 作為備援部署拓撲
> - §1.2「為何不用 GPTs」改寫：主論點從「金控合規 deal-breaker」改為「雙欄 live 預覽 UX 無法成立」為第一否決點；合規改為次要論點（仍需個案核可）
> - §10.5 認證：主推 Cathay SSO，但不再強制「內網 AD」；支援外部 IdP（OIDC）選項
> - §10.6 部署：新增 cloud 部署拓撲描述；列出內網 / cloud 兩種部署對合規、成本、維運的影響
> - §8 Q10 / Q11：調整候選答案，反映 cloud-first 情境下的 auth / real-time 選項
> - 本次修訂**不改動** §2–§7 BU 旅程設計、兩 mode 職責、交接邏輯；只改部署與資料落地假設
> - 注意：此修訂為「工程規劃假設調整」，正式上線前仍須通過 Cathay 資料分級 / 法遵 / 資安 review；若 review 結論是必須內網，則 §10.6 的備援方案立即成為主方案

> **v0.2 修訂重點**（2026-05-10 改採自建前端，棄 Slack）：
> - 前端從 Slack 改為自建 web app；後端維持 LangGraph + PostgresSaver + Gemini 2.5 Pro 不變
> - 移除所有 slash command 設計（`/brd-explore` / `/brd-new` / `/brd-resume`）；改為 web 路由 + UI navigation
> - §3 / §4 / §5 / §6 涉及 Slack thread / modal / 訊息描述，全面改為 web session / form / 工作區
> - 新增 §10「前端架構草案」：split layout（左對話 / 右工作區）、mode-aware 工作區、後端 API 形態
> - §7 Migration notes 增加「Slack → 自建前端」差異欄
> - §8 Open Questions 移除 Slack-specific 問題（slash 設計、thread-aware resume），新增前端框架選型、auth 機制、real-time 通信、BA Agent 是否共用前端等

> **v0.1 修訂重點**（2026-05-10 BU Agent 兩階段重構初稿）：
> - 新增 BU Agent 作為 BU 端 single entry point；內部分為 Explore mode 與 Consult mode 兩個階段
> - 明訂 Explore mode 的雙輸出（結構化 JSON + 段落需求描述），作為 mode 內交接介面
> - 明訂 Consult mode 採「建初步 BRD 大綱 → 第 2 輪訪談」兩步推進，產出初版（粗略）v1.0 BRD
> - 明訂 BU Agent → BA Agent 的階段交接點與交付物清單
> - 與舊三姊妹架構（Explore / Consult / Diff 三 agent）的差異整理至 §7

---

## 1. 背景與動機 (Background)

舊三姊妹架構（`overview.md` v0.1）將 BU 旅程切為三個獨立 agent 並掛在 Slack 上。實作上揭露幾個問題：

1. **BU 心智負擔**：BU 要先自我判斷「我屬於哪個起始狀態」才知道用哪個 slash。實際對話中 BU 經常不確定自己是「0 idea」還是「vague idea」，導致選錯 slash 卡關。
2. **Explore → Consult 之間的銜接 friction**：deep link `--from-exploration <id>` 雖可預填 metadata，但 Consult pre-flight modal 仍是另一條對話流；BU 體感是「開了第二個視窗從頭再來」。
3. **角色分界誤解**：原 `Explore_agent` + `Consult_agent` 都是 BU 互動，「兩個 agent」這個 framing 對 BU 而言是內部實作細節，不是有意義的階段分界。
4. **BA / Diff 的角色實際上是 BU 完稿之後的第二階段**：Diff_agent 的使用者主要是 BA，與 BU 階段是清楚的責任分界線。

故本次重構**同時改動兩個方向**：

- **角色分界重切**：BU 旅程合併為單一 BU Agent（內部兩 mode）→ BA Agent 接手；本文 §2–§7 規範
- **前端平台重選**：棄 Slack 改採自建 web app；本文 §10 規範（部署拓撲見 §10.6）

### 1.1 為何不繼續用 Slack

- BRD 是章節密集的工作，Slack 的 interactive component（block kit / modal）撐不到「左對話 / 右 BRD 即時預覽」「章節 inline edit」「大綱樹狀展開」等 BRD 專屬 UX
- mode 內部切換、Step 1 自動大綱呈現、Step 2 章節層級訪談並列預覽，這些在 web UI 可以做得遠比 Slack thread 流暢
- BU Agent 與未來 BA Agent 的 review / Suggesting UI 邏輯一致時，自建前端可共用元件；Slack + Google Docs Suggesting mode 是雙工具切換

### 1.2 為何不用 ChatGPT Custom GPTs

- **UX deal-breaker**：Custom GPTs 僅有單欄對話；本文規劃的「左對話 / 右 BRD 即時預覽 + 章節 inline edit」（§10.1 / §10.2）無法在 GPTs 內實現 → Epic B2 / D2 / E3 / E4 等核心 UX 全部不成立。這是第一順位否決理由
- 體驗倒退：兩個 GPT 之間的 mode 切換要 BU 手動 copy/paste 雙輸出（§4.1.4），破壞 §3.2「同一 agent 連續對話」設計
- 持久化、跨日 resume、conversation_trace 仍需自建 backend 對接 Actions，工程量並未降低
- 資料落地：OpenAI platform 會保留 conversation context，BU 若於對話中提及險種代碼 / 客戶資料將離開 Cathay 控制邊界；即使 cloud-first 情境下也仍須走正式資料分級 review，流程成本高於自建
- 詳細三方案比較見 `Plan_bu_agent/frontend_platform_comparison.md`

> 本文僅規範 **BU Agent 階段**；BA Agent 細節留待後續另立文件。

---

## 2. 定位 (Positioning)

### 2.1 一句話定位

> **BU Agent 是 BU 端唯一的 BRD 草擬助手，從「想用 AI 但不確定方向」一路陪到「BU 自認可以送 BA 的 v1.0 初稿」**。

### 2.2 服務對象

| 角色 | 與 BU Agent 的關係 |
| --- | --- |
| **BU SME** | **唯一主操作者**；全程對話對象 |
| BU 主管 | 旁觀者；協助 BU 決策候選方向（不直接對話） |
| BA | **本階段不參與**；於 BU Agent 完成後進入 BA Agent 階段接手 |
| AI 科 / CD 科 | 終端讀者；本階段不參與 |

### 2.3 不做什麼 (Non-Goals)

- ❌ 不做 BA review / spot-check（屬 BA Agent）
- ❌ 不做會議錄音增量更新（屬 BA Agent）
- ❌ 不做 BRD 定稿、版號管理（v1.1+ 由 BA Agent 處理）
- ❌ 不替 BU 決策最終候選方向；agent 永遠輸出選項，BU 做選擇
- ❌ 不在 Explore mode 內就把 BRD 寫出來；mode 邊界明確不混淆

---

## 3. 整體使用流程 (End-to-End Flow)

### 3.1 流程總圖

```
                         ┌──────────────────────────────────┐
[BU 想用 AI]   ─────▶    │           BU Agent               │
                         │        （自建 web app）         │
                         │                                  │
                         │   ┌──────────────────────────┐   │
                         │   │   Explore mode           │   │
                         │   │   （發想 / 聚焦候選）     │   │
                         │   │                          │   │
                         │   │   工作自述 → 候選需求    │   │
                         │   └────────────┬─────────────┘   │
                         │                │                 │
                         │      Mode 內交接（雙輸出）       │
                         │   ┌────────────▼─────────────┐   │
                         │   │  • 結構化 JSON           │   │
                         │   │  • 段落需求描述          │   │
                         │   └────────────┬─────────────┘   │
                         │                │                 │
                         │   ┌────────────▼─────────────┐   │
                         │   │   Consult mode           │   │
                         │   │   （建大綱 → 第 2 輪訪談）│   │
                         │   │                          │   │
                         │   │   候選需求 → 初版 BRD    │   │
                         │   └────────────┬─────────────┘   │
                         │                │                 │
                         └────────────────┼─────────────────┘
                                          │
                              階段交接（v1.0 BRD 初版）
                                          │
                                          ▼
                              ┌──────────────────────┐
                              │      BA Agent        │
                              │  （review / 增量更新 / │
                              │     v1.0 → v1.1+）    │
                              └──────────────────────┘
```

### 3.2 BU 端體感旅程

| 步驟 | BU 體感 | 內部 mode |
| --- | --- | --- |
| 1 | 我想用 AI 但不知道從哪用 → 打開 BU Agent web app | 進入 Explore mode |
| 2 | 講講我每天 / 每週的工作，agent 幫我發散 | Explore mode 對話中 |
| 3 | 跟 agent 一起聚焦到 1-3 個候選方向 | Explore mode 收斂 |
| 4 | Agent 說「方向確認了」，工作區自動切到 BRD 大綱檢視 | **內部 mode 切換** → Consult mode |
| 5 | 工作區顯示初步大綱 + 章節狀態，agent 在對話區繼續逐章問細節 | Consult mode 第 2 輪訪談 |
| 6 | 工作區顯示完整初版 BRD，BU 可在右側直接 inline edit | BU Agent 階段結束 |
| 7 | Agent 通知 BA 接手（in-app + email） | 進入 BA Agent 階段 |

> **關鍵設計**：Step 4 的 mode 切換對 BU 是**單一 web session 內的工作區換版面**，不是另開頁面 / 另登入。BU 不需理解「Explore mode」「Consult mode」這兩個術語。

---

## 4. 兩個 Mode 的職責邊界

### 4.1 Explore mode

#### 4.1.1 目標

從 BU 的工作日常自述中，挖出 1-3 個有 AI 切入空間的**候選需求方向**，並產出可被 Consult mode 直接吃下的結構化交接物。

#### 4.1.2 輸入

| 輸入 | 必填 | 說明 |
| --- | --- | --- |
| BU 別 | 是 | web app 開場表單欄位（產險 / 壽險 / 銀行 / 證券 / 投信 …） |
| 角色簡述 | 是 | 1-2 句描述自己的職務（例：產險核保 SME） |
| Raw text hint | 否 | 開場輸入框第一句話；用於 agent 開場聚焦 |

#### 4.1.3 對話節奏

依 `BU_Agent_v2_題庫.md` 的 5 階段設計（發散 / 脈絡建立 / 收斂 / Challenge / 交接準備），整體對話約 **5–10 分鐘**，每輪 1 題、最多 2 題。Give-then-Ask 原則：每輪先 surface 有用資訊（過去案例、AI 能力 pattern match），再問下一題。對話區（左欄）顯示 agent 提問與 BU 回答；工作區（右欄）即時顯示候選方向卡片與 5 維度 rubric heatmap。

#### 4.1.4 輸出（雙輸出設計）

Explore mode 完成後同時產出兩份內容，作為 mode 內交接介面：

**(A) 結構化 JSON**（給 Consult mode 機讀）

預期 schema 草案：

```yaml
exploration_id: ex_01HW...
bu: 產險
sme_role: 核保部 SME
candidates:
  - rank: 1
    direction: 理賠文件型別自動分類
    score_5d: { rule_repeat: 5, data_avail: 4, reversibility: 5, scale_roi: 4, gap: 5 }
    process_target: 理賠文件型別
    project_type: 分類
    pain_signals: [人工歸檔耗時, 月均 5000 件, 誤分類僅延遲處理]
  - rank: 2
    ...
selected_candidate: 1                # BU 已確認的選項，供 Consult mode 直接接續
predicted_consult_fields:            # 對應 Consult mode 預填欄位
  bu: 產險
  process_target: 理賠文件型別
  project_type: 分類
  one_line_goal: 自動將每月 5000 件理賠文件依型別歸檔
trace:                                # 機制 1：完整對話追蹤（責任歸屬）
  rounds: [...]
  agent_reframes: [...]
  bu_choices: [...]
```

> Schema 細節（欄位完整表、型別、必填性）留至 BU Agent 主 PRD 規範。

**(B) 段落需求描述**（給 BU 與 Consult mode 共讀）

一段 200–400 字的自然語言描述，內容涵蓋：

- BU 想解決的問題（從 pain signals 抽取）
- 工作流程中 AI 切入的位置
- 預期輸入 / 輸出形式（粗略，不必到 IO schema 等級）
- BU 已確認 vs agent 主動 reframe 提出的部分（依 `BU_Agent_v2_題庫.md` 機制 2 視覺標記）

> 這段文字會在 Step 4 mode 切換時於 web UI confirmation modal 顯示給 BU 確認「是否進入 Consult mode」。

#### 4.1.5 終止條件

- BU 在收斂題（`BU_Agent_v2_題庫.md` 階段 4 / 階段 5）明確選定一個候選方向
- 或 BU 連續 2 輪表示「都不太對」→ agent 標記為 cold，建議離線找 BA 對焦（不直接進入 Consult mode）

### 4.2 Consult mode

#### 4.2.1 目標

依據 Explore mode 雙輸出，建立初步 BRD 大綱、與 BU 進行**第 2 輪訪談**，產出初版（粗略）v1.0 BRD。

「粗略」的定義：覆蓋 5 個 BU 訪談章節（需求背景 / 需求分析 / 執行方式不含 API 格式 / User Cases / 例外處理），但不要求每章節都到「BA 認為可發包」的細緻度；agent 偵測到 BU 答不出來的部分標 `flag_for_ba_review`，留給 BA Agent 階段補完。

#### 4.2.2 輸入

| 輸入 | 來源 | 說明 |
| --- | --- | --- |
| 結構化 JSON | Explore mode (A) | 機讀，自動建立 metadata、預填 pre-flight |
| 段落需求描述 | Explore mode (B) | 給 BU 確認、給 LLM 當 context（few-shot 之外的 grounding） |
| BU 第 2 輪訪談回應 | web 對話區 | 章節層級的細節釐清 |

#### 4.2.3 兩步推進邏輯

Consult mode 拆為兩個明確子步驟，**不再是傳統 section_loop 從零訪談**：

**Step 1 — 建初步 BRD 大綱（auto，無 BU 對話）**

Agent 接收 Explore 雙輸出後：

1. 載入該 BU / project_type 的 BRD 模板（YAML config）
2. 用結構化 JSON + 段落描述當 prompt context，**先填入** 5 個 BU 章節能從 Explore 內容自動推得的部分
3. 標記每個章節：
   - `auto_filled`：Explore 已涵蓋，第 2 輪僅需 BU 確認
   - `needs_round2`：Explore 未涵蓋，第 2 輪要訪談
   - `placeholder`：屬 AI 科 / CD 科填寫，本階段跳過
4. **工作區（右欄）切換為「BRD 大綱樹」檢視**：顯示章節結構 + 每節狀態徽章 + 已填入內容預覽。BU 在工作區直接點選章節展開細節、確認大綱結構是否合理

**Step 2 — 第 2 輪訪談（章節層級，僅針對 needs_round2）**

對 `needs_round2` 章節逐一訪談；對 `auto_filled` 章節 BU 可在工作區直接 inline edit，或在對話區點 Accept / Refine / Skip。工作區隨對話即時更新章節內容（live preview）。

> 與舊 Consult_agent 的 section_loop 差異：舊版每章從零開始問 4-5 題；新版因 Explore 已挖過 signal，第 2 輪訪談聚焦在「Explore 沒講到的章節」與「需求細節釐清」，預期總對話時間從 30–60 分鐘降到 **20–30 分鐘**。

#### 4.2.4 輸出

| 輸出 | 形式 | 說明 |
| --- | --- | --- |
| **v1.0 BRD（初版、粗略）** | 內部 markdown，可在 web UI inline edit；後續可匯出 docx | 5 BU 章節有內容；3 H1 + 1 H2 為 placeholder（依舊 `Consult_agent/consult_agent.md` §3.6 canonical list）。是否仍走 Google Doc 為協作載體於 §8 Q4 待議 |
| **summary.json** | JSON | 給 PM / RD 快速 onboard：one_line_goal / key_business_rules / io_fields / exception_cases / open_for_ai_team / `flag_for_ba_review` 列表 |
| **conversation_trace** | JSON | Explore + Consult 全程對話、agent reframe、BU 決策路徑（給 BA Agent 階段做歸因 / 補洞） |

#### 4.2.5 終止條件

- BU 對所有 `needs_round2` 章節 Accept 或 Skip
- 或 BU 點工作區的「送 BA」按鈕
- Quality gate：跨章節一致性檢查（沿用舊 `Consult_agent` `quality_gate` node 設計）

---

## 5. Mode 內部交接 (Explore → Consult)

### 5.1 交接觸發點

當 Explore mode 達到 §4.1.5 終止條件時，**不需 BU 額外動作**，agent 在同一 web session 內：

1. 工作區彈出 modal 顯示 §4.1.4 (B) 段落需求描述
2. 詢問 BU：「我把這次討論整理成上面這段。要不要我直接幫你列 BRD 大綱？」
3. BU 點「進入 Consult mode」 → progress bar 自動推進、工作區換版面為「BRD 大綱樹」、agent 開始 Step 1 自動填章節

> **設計原則**：交接是**單向**的（Explore → Consult 不可逆）。若 BU 在 Consult Step 1 看到大綱後想推翻方向，需在 UI 點「重新探索」按鈕，agent 才會回到 Explore mode 並把當前候選標 cold。

### 5.2 為何要雙輸出（不只 JSON）

| 目的 | 結構化 JSON | 段落需求描述 |
| --- | --- | --- |
| 給 Consult mode 機讀，自動建大綱 | ✅ 主要用途 | △ 輔助 LLM context |
| 給 BU 在 mode 切換點確認 | ❌ JSON 對 BU 太冷 | ✅ 主要用途 |
| 給 BA Agent 階段回溯責任 | ✅ trace 欄位 | ✅ 對話原貌 |
| 給未來分析 / 改進題庫 | ✅ score / signals 可彙整 | △ 需 NLP 抽取 |

兩者缺一不可：JSON 是機器介面，段落是人類介面。

### 5.3 結構化 JSON 必要欄位（與舊 Explore predict_consult_fields 對齊）

最少需提供以下欄位給 Consult mode（細節由主 PRD 規範）：

- `bu`、`process_target`、`project_type`、`one_line_goal`（對應舊 Consult pre-flight Layer 1 Core 5 欄）
- `selected_candidate`（BU 已確認方向，避免 Consult mode 還要再問一次）
- `pain_signals` / `score_5d`（給 Consult mode draft 章節時當素材）
- `trace`（責任歸屬）

---

## 6. 階段交接：BU Agent → BA Agent (Handoff)

### 6.1 觸發時機

- BU 在 Consult mode 完成所有章節並點工作區的「送 BA」按鈕
- 或 quality_gate 通過 + BU 已 Accept 全部 `needs_round2` 章節

### 6.2 交付物清單

| 交付物 | 形式 | 接收方 |
| --- | --- | --- |
| **v1.0 BRD（初版、粗略）** | 內部 markdown 或 Google Doc URL（依 §8 Q4 決議） | BA Agent 主檔 |
| **summary.json** | JSON | BA Agent / PM / RD |
| **conversation_trace** | JSON | BA Agent（包含 Explore + Consult 全程） |
| **flag_for_ba_review 清單** | JSON 子集 | BA Agent 優先處理項目 |

### 6.3 BU 端結束體驗

工作區切換為「完成」畫面，顯示：

> 已完成初版 BRD：[BRD 連結 / 預覽]
> 已通知 BA（@xxx）接手 review。如有後續會議錄音、修訂需求，BA 會用 BA Agent 介面處理（不在這個 session）。
> 你這邊的工作告一段落。[返回 sessions 列表]

> **設計原則**：BU 不需主動 ping BA、不需理解 BA Agent 是誰；交接由 system 處理（in-app notification + email，細節 §8 Q12）。

### 6.4 BA Agent 範圍（本文不展開）

BA Agent 階段預計涵蓋：

- v1.0 review / spot-check（吸收舊 Consult `BA review` 角色）
- 會議錄音增量更新（吸收舊 Diff_agent 全部功能）
- v1.0 → v1.1+ 版號維護
- BU 答不出 / `flag_for_ba_review` 項目補洞

> 細節留待 `BA_Agent/ba_agent_overview.md`（待建）規範。BA Agent 是否共用同一前端 web app（不同 view）或獨立 app，列入 §8 Q13。

---

## 7. 與舊架構的差異 (Migration Notes)

### 7.1 對照表

| 維度 | 舊三姊妹架構 | 新兩階段架構（自建前端） |
| --- | --- | --- |
| Agent 數量 | 3（Explore / Consult / Diff） | 2（BU Agent / BA Agent） |
| **前端平台** | **Slack（slack-bolt）** | **自建 web app（cloud 預設 / 內網備援，詳 §10.6）** |
| BU 端入口 | 2 slash（`/brd-explore` / `/brd-new`） | 1 web app + 開場表單 |
| Explore → Consult | deep link 跨 agent | mode 內工作區換版面 |
| BU 體感 | 兩個 agent / 兩個 thread | 一個 web session / split layout |
| Consult 訪談 UI | Slack thread 訊息 + interactive buttons | 對話區 + 工作區 live 預覽 + inline edit |
| 章節 review 形式 | Google Docs Suggesting mode（Diff 階段） | web UI inline edit + Accept/Refine/Skip（細節 §8 Q4） |
| Resume 機制 | thread_ts ↔ session_id + `/brd-resume` fallback | user_id + session_id；web sessions 列表 |
| 預期總對話時間 | 30–60 分鐘 | 20–30 分鐘 |
| BA 介入點 | Consult 完成 + Diff 觸發兩處 | 統一在 BU Agent 完成後 |

### 7.2 舊 PRD 哪些設計被吸收

- 舊 `Explore_agent/explore_agent.md`：5 維度 rubric / discovery_loop / cluster_pain_points / 候選分數設計 → **直接搬入** Explore mode 子 PRD
- 舊 `Consult_agent/consult_agent.md`：BRD 模板 / placeholder canonical list（3 H1 + 1 H2） / quality_gate / summary.json schema / template_configs YAML → **直接搬入** Consult mode 子 PRD
- 舊 `BU_Agent_v2_題庫.md`：5 階段題庫 / 4 個分析任務 / 跨階段配套機制（trace 保留 / 視覺標記 / 明確同意 / completeness 追蹤 / checkpoint） → **直接搬入** Explore mode 子 PRD
- 舊 `Consult_agent` pre-flight 兩層架構（Layer 1 Core 5 欄 / Layer 2 BU-specific YAML 3 欄）：因 Explore 已負責挖 metadata，**Layer 1 由 Explore 結構化 JSON 自動填**，**Layer 2** 視 BU 需求保留為 web app 開場表單欄位（不再是 Slack modal）

### 7.3 舊 PRD 哪些設計被改變

- ❌ 舊 `--from-exploration <id>` deep link：取消（mode 內切換不需 deep link）
- ❌ 舊 Consult `keyword_route` node：取消（在新架構中由 Explore mode 涵蓋；Consult Step 1 自動建大綱不再需要 raw text routing）
- ❌ 舊 Consult `collect_metadata` node（Slack pre-flight modal）：改為 web app 開場表單
- ❌ **舊 Slack interactive component**（block kit、Accept/Refine/Skip button、quote anchor）：全部以 web UI 元件取代
- ❌ **舊 thread_ts ↔ session_id 1:1 對應**：改為 user_id + session_id 模型；resume 機制走 web UI sessions 列表
- ❌ **舊 `slack-bolt` Python SDK 與 Slack OAuth**：技術棧整層移除；`oauth_tokens` 表中 Slack 部分清空，Google Docs 部分視 §8 Q4 決議保留與否
- 🔄 舊 `section_loop`：保留架構但縮減使用範圍（只跑 `needs_round2` 章節）

### 7.4 既有檔案處置

- `Explore_agent/explore_agent.md` v0.1：保留作為 Explore mode 設計細節參考；**Slack 相關段落**（slash command / thread-aware / interactive component）在後續主 PRD 階段改寫
- `Consult_agent/consult_agent.md` v0.8：同上
- `Consult_agent/history/`：保留歷史 changelog，不動
- `Diff_agent/Diff_PRD.md` v0.1：移轉至 BA Agent 範疇；前端平台同步從 Slack 改為自建前端
- `overview.md` v0.1：保留作為舊架構紀錄；新架構以本文（`BU_Agent/bu_agent_overview.md`）為入口

---

## 8. 後續待解問題 (Open Questions)

下列項目影響主 PRD 細節，於本 overview **不做決策**，留待主 PRD 階段集中決議：

| # | 問題 | 候選答案 |
| --- | --- | --- |
| Q1 | Mode 切換是否完全自動？ | (a) 全自動（Explore 達終止條件即進 Consult）；(b) BU 在 modal 明確確認後切換；(c) 預設自動但 BU 可中斷 |
| Q2 | Consult Step 2 章節層級訪談是否仍允許 Refine ≤ 3 輪 / Skip 規則？ | 沿用舊 Consult §F-2.2.2 答覆品質守門設計 |
| Q3 | Explore 段落需求描述（§4.1.4 B）的長度上限？ | 200–400 字 vs 100–200 字 vs 不設限 |
| Q4 | v1.0 BRD 載體格式？ | (a) 內部 markdown / web 內 inline edit；(b) 仍走 Google Doc + Suggesting mode；(c) markdown 為主、export docx |
| Q5 | 結構化 JSON schema 完整定義？ | 主 PRD 階段以 Pydantic / JSON Schema 形式定錨 |
| Q6 | 跨日 resume / 自動 save draft 粒度？ | (a) 每輪對話 save；(b) 每章節 save；(c) hybrid |
| Q7 | mode 切換時 BU 想推翻方向的 UX？ | (a) 工作區「重新探索」按鈕；(b) 對話區自然語言偵測；(c) 兩者都接 |
| Q8 | conversation_trace 給 BA 看的權限？ | 全部可見 vs BU 可標 `private` 段落 |
| Q9 | 前端框架選型？ | React / Next.js / Vue / Svelte |
| Q10 | 認證機制？ | (a) Cathay SSO（OIDC，可對接內部 AD 或 cloud IdP）；(b) 外部 IdP（Auth0 / Entra ID 等）；(c) Email + magic link（PoC 階段） |
| Q11 | Real-time 通信？ | (a) WebSocket（雙向，適合 streaming agent reply）；(b) SSE（單向 server push，較簡單）；(c) HTTP long poll |
| Q15 | 部署拓撲？（v0.3 新增） | (a) cloud 部署（GCP / AWS / Azure 擇一，須通過資料分級 review）；(b) Cathay private cloud / on-prem；(c) hybrid（前端 cloud、後端 + DB on-prem） |
| Q16 | LLM 呼叫路徑？（v0.3 新增） | (a) Gemini API 直連（cloud-first）；(b) Vertex AI in Cathay-controlled project；(c) 經 Cathay API gateway / DLP proxy 轉發 |
| Q12 | 通知機制？ | (a) in-app only；(b) in-app + email；(c) in-app + email + Teams webhook |
| Q13 | BA Agent 是否共用同一前端？ | (a) 共用 web app 不同 view；(b) 完全獨立 app；(c) 共用 backend / 不同 frontend |
| Q14 | conversation_trace 給 BA Agent 階段的傳遞形式？ | API endpoint vs 共用 DB 直讀 |

---

## 9. 下一步 (Next Steps)

1. 確認本 overview v0.3 設計方向（特別是 §4.2.3 兩步推進邏輯、§10 前端架構草案、§10.6 部署拓撲）
2. 決議 §8 Q1 / Q4 / Q9 / Q10 / Q11 / Q15 / Q16（影響工程啟動與資安 review 的關鍵）
3. 啟動與 Cathay 資料分級 / 法遵 / 資安單位的 cloud 部署個案 review（v0.3 新增前置作業）
4. 撰寫 `BU_Agent/bu_agent.md` 主 PRD（吸收舊 Explore + Consult PRD 設計細節，針對自建前端改寫）
5. 啟動 `BA_Agent/ba_agent_overview.md`（吸收舊 Diff_agent + Consult `BA review` 角色；前端平台同步）

---

## 10. 前端架構草案 (Frontend Architecture Sketch)

> 此節為 overview 層級草案，工程細節留待主 PRD 與技術設計文件規範。

### 10.1 Layout 概念

採 split layout：左欄對話、右欄工作區，頂部 mode progress bar。

```
┌──────────────────────────────────────────────────────────────────┐
│ BU Agent                                       [Sessions▾] [⚙]   │
│ ●Explore ── ○Consult Step 1 ── ○Consult Step 2     ▓▓░░░░ 35%   │
├──────────────────────────────┬───────────────────────────────────┤
│                              │                                   │
│  對話區（chat）               │  工作區（mode-aware workspace）   │
│  ─────────────                │  ──────────────────               │
│  [Agent] ...                 │  ▼ Explore：候選方向卡片           │
│  [BU] ...                    │      + 5 維度 rubric heatmap       │
│  [Agent] ...                 │                                   │
│                              │  ▼ Consult Step 1：BRD 大綱樹      │
│                              │      + 章節狀態徽章                │
│                              │      + 已填入內容預覽              │
│  [輸入框]                    │                                   │
│                              │  ▼ Consult Step 2：BRD live 預覽   │
│                              │      + 章節 inline edit            │
│                              │      + Accept/Refine/Skip          │
│                              │                                   │
└──────────────────────────────┴───────────────────────────────────┘
```

### 10.2 工作區內容（mode-aware）

| Mode | 工作區內容 |
| --- | --- |
| Explore | 候選方向卡片（top 1–3，含 5 維度 rubric heatmap）、pain signals timeline、reframe 建議標籤 |
| Consult Step 1 | BRD 大綱樹（章節 + 狀態徽章 auto_filled / needs_round2 / placeholder）、可展開預覽已填入內容 |
| Consult Step 2 | BRD live 預覽（依章節捲動）、inline edit、Accept/Refine/Skip 按鈕、章節間導航 |
| 完成 | 完整 BRD 預覽、summary.json 摘要、「送 BA」按鈕 |

### 10.3 後端 API 形態（草案）

維持舊架構技術棧（LangGraph + PostgresSaver + Gemini 2.5 Pro），前端透過：

- **REST**：sessions CRUD、開場 metadata 提交、export 觸發、handoff 至 BA Agent
- **SSE 或 WebSocket**：agent 回覆 streaming、mode 切換事件、章節即時更新（細節 §8 Q11）

LangGraph `interrupt()` 仍是 HITL 主機制；interrupt point 不再對應 Slack 訊息回覆，而對應 web UI 的對話區 reply 或工作區按鈕事件。

### 10.4 持久化與 Resume

- 每位 BU 一個 user_id；每場諮詢一個 session_id（同時為 LangGraph thread_id）
- web app sessions 列表（頂部 drawer 或左下）顯示該 BU 的所有 session、狀態、最後更新時間
- BU 任意時點關閉視窗 → PostgresSaver 已 checkpoint；重新登入點 session 即恢復至上一個 interrupt point
- 不再需要舊 Slack 的 thread-aware Layer 1 / `/brd-resume` Layer 2 雙層 fallback

### 10.5 認證（草案）

- 主推 Cathay SSO（OIDC 標準）整合；底層 IdP 可為內部 AD 或雲端 IdP，視 §8 Q10 決議
- cloud-first 情境下，若暫無 Cathay SSO 介接權限，PoC 階段可退為 Email + magic link（Q10 選項 c）
- 不再需要 Slack workspace token；`oauth_tokens` 表中的 Google Docs 部分視 §8 Q4 決議保留與否

### 10.6 部署

> **v0.3 變更**：不再預設內網部署；改為 **cloud 為預設、內網為備援**，最終由 §8 Q15 決議。以下列兩種拓撲供後續比較。

**方案 A：Cloud 部署（v0.3 預設）**
- 服務（前端 + 後端 + DB）部署於 GCP / AWS / Azure 任一；優先選擇與 Gemini 同區域以降低延遲
- 前端透過 CDN / 託管服務（Vercel、Cloud Run、App Service 等擇一）對外暴露；後端 FastAPI 與 PostgreSQL 於同一 VPC 內
- 使用者從一般網際網路存取；走 SSO + TLS；DB 僅開內部 subnet，不對外
- 優點：部署速度快、可與 Gemini API 直連（§8 Q16 選項 a）、易於擴縮
- 前提：須通過 Cathay 資料分級 / 法遵 / 資安個案 review，確認 BRD 內容（含險種代碼、潛在客戶資料）可於所選雲端區域落地

**方案 B：Cathay private cloud / on-prem（備援）**
- 若 cloud review 未過，退回本方案；與舊架構部署位置一致
- LLM 呼叫須走 Cathay API gateway / DLP proxy（§8 Q16 選項 c）或 Cathay-controlled Vertex AI project（選項 b）
- 認證強制走內部 AD SSO

**方案 C：Hybrid（候選）**
- 前端於 cloud（給使用者體驗）、後端 + DB 於 on-prem（資料落地）
- 透過 VPN / private link 連接；複雜度最高，僅在 A / B 都有障礙時考慮

**共通工程事項**
- 前端 build artifact 與後端 FastAPI 同 CI/CD 管道；dev 階段可 local 啟兩個 server（與部署拓撲無關）
- 正式環境至少 2 個後端 replica；DB 採 managed service（cloud）或 HA cluster（on-prem）

---

*— End of BU Agent Overview v0.3 —*
