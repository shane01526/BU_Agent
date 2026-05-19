# BU Agent — User Stories 與完整服務流程

> 版本：v0.1
> 撰寫日期：2026-05-11
> 依據來源：`BU_Agent/bu_agent_overview.md` v0.2
> 目的：從 overview 中萃取可直接用於 PRD / 開發規劃的 User Stories 清單，並把「BU 端體感旅程」展開成可執行的端到端詳細流程步驟
> 範圍：僅涵蓋 **BU Agent 階段**（Explore mode + Consult mode）；BA Agent 僅在交接點出現

---

## 目錄 (Table of Contents)

### 主要章節

- [1. 角色與服務對象 (Personas)](#1-角色與服務對象-personas)
- [2. User Stories（Epic / Story 分層）](#2-user-storiesepic--story-分層)
- [3. 完整服務流程（詳細步驟）](#3-完整服務流程詳細步驟)
- [4. 流程端到端總覽表](#4-流程端到端總覽表)
- [5. 與 Open Questions 的關聯](#5-與-open-questions-的關聯)

### Epic 與 Story 索引（29 條 User Stories）

- [**Epic A — 進入系統與開場**](#epic-a--進入系統與開場) · 3 stories
  - [A1. 單一入口、不選 slash](#a1-單一入口不選-slash)
  - [A2. 開場 metadata 表單](#a2-開場-metadata-表單)
  - [A3. 跨日 Resume](#a3-跨日-resume)
- [**Epic B — Explore mode（發想 → 聚焦候選）**](#epic-b--explore-mode發想--聚焦候選) · 7 stories
  - [B1. 工作日常自述發散](#b1-工作日常自述發散)
  - [B2. 即時看到候選方向卡片](#b2-即時看到候選方向卡片)
  - [B3. Pain signals 與 reframe 視覺標記](#b3-pain-signals-與-reframe-視覺標記)
  - [B4. 聚焦到 1–3 個候選方向](#b4-聚焦到-1-3-個候選方向)
  - [B5. 明確選定一個方向](#b5-明確選定一個方向)
  - [B6. Cold 終止保護](#b6-cold-終止保護)
  - [B7. 整體對話控制在 5–10 分鐘](#b7-整體對話控制在-5-10-分鐘)
- [**Epic C — Mode 交接（Explore → Consult）**](#epic-c--mode-交接explore--consult) · 4 stories
  - [C1. 交接 modal 確認](#c1-交接-modal-確認)
  - [C2. 不可逆單向交接](#c2-不可逆單向交接)
  - [C3. 重新探索 escape hatch](#c3-重新探索-escape-hatch)
  - [C4. 雙輸出（JSON + 段落）作為交接介面](#c4-雙輸出json--段落作為交接介面)
- [**Epic D — Consult mode Step 1（自動建大綱）**](#epic-d--consult-mode-step-1自動建大綱) · 3 stories
  - [D1. 自動載入模板並初步填章節](#d1-自動載入模板並初步填章節)
  - [D2. 章節狀態徽章](#d2-章節狀態徽章)
  - [D3. 自動 Layer 1 預填](#d3-自動-layer-1-預填)
- [**Epic E — Consult mode Step 2（第 2 輪訪談）**](#epic-e--consult-mode-step-2第-2-輪訪談) · 6 stories
  - [E1. 只針對 needs_round2 訪談](#e1-只針對-needs_round2-訪談)
  - [E2. auto_filled 章節 Accept / Refine / Skip](#e2-auto_filled-章節-accept--refine--skip)
  - [E3. 工作區 inline edit](#e3-工作區-inline-edit)
  - [E4. Live 預覽隨對話更新](#e4-live-預覽隨對話更新)
  - [E5. 答不出來可標 flag_for_ba_review](#e5-答不出來可標-flag_for_ba_review)
  - [E6. 跨章節一致性 quality gate](#e6-跨章節一致性-quality-gate)
- [**Epic F — 交接至 BA Agent**](#epic-f--交接至-ba-agent) · 5 stories
  - [F1. 送 BA 按鈕](#f1-送-ba-按鈕)
  - [F2. 產出 v1.0 BRD（粗略初版）](#f2-產出-v10-brd粗略初版)
  - [F3. 附交付物 summary.json / conversation_trace](#f3-附交付物-summaryjson--conversation_trace)
  - [F4. 自動通知 BA（不需 BU 自己 ping）](#f4-自動通知-ba不需-bu-自己-ping)
  - [F5. BU 端完成畫面](#f5-bu-端完成畫面)
- [**Epic G — 平台 / Non-Functional Stories**](#epic-g--平台--non-functional-stories) · 4 stories
  - [G1. Split layout + mode progress bar](#g1-split-layout--mode-progress-bar)
  - [G2. Streaming agent 回覆](#g2-streaming-agent-回覆)
  - [G3. Auto save 與 checkpoint](#g3-auto-save-與-checkpoint)
  - [G4. Agent 不代 BU 決策](#g4-agent-不代-bu-決策)

### 流程 Phase 索引

- [Phase 0 — 登入與開場 (Onboarding)](#phase-0--登入與開場-onboarding)
- [Phase 1 — Explore mode（約 5–10 分鐘）](#phase-1--explore-mode約-5-10-分鐘)
- [Phase 2 — Mode 交接 (Explore → Consult)](#phase-2--mode-交接-explore--consult)
- [Phase 3 — Consult mode Step 1（自動建大綱、無對話）](#phase-3--consult-mode-step-1自動建大綱無對話)
- [Phase 4 — Consult mode Step 2（第 2 輪訪談，約 20–30 分鐘整個 Phase 3+4）](#phase-4--consult-mode-step-2第-2-輪訪談約-20-30-分鐘整個-phase-34)
- [Phase 5 — 交接至 BA Agent](#phase-5--交接至-ba-agent)
- [Phase R — Resume 子流程（任意 phase 可觸發）](#phase-r--resume-子流程任意-phase-可觸發)

---

## 1. 角色與服務對象 (Personas)

| 代號 | 角色 | 與 BU Agent 的關係 |
| --- | --- | --- |
| P1 | **BU**（業務單位主題專家） | **唯一主操作者**；全程對話對象 |
| P2 | BA（Business Analyst） | 本階段不參與；於 BU Agent 完成後於 BA Agent 階段接手 |
| P3 | AI Team | 終端讀者；本階段不參與、但 BRD 中會保留其 placeholder 章節 |

> 以下 User Stories 一律以 P1（BU）為主語，除非另外標註。

---

## 2. User Stories（Epic / Story 分層）

依 BU 旅程順序分成 6 個 Epic，共 31 條 User Story。每條 Story 附驗收準則（AC）與來源節次。

### Epic A — 進入系統與開場

#### A1. 單一入口、不選 slash
> **身為** BU，
> **我想要** 只透過一個 BU Agent web app 入口進入，
> **以便** 我不需要先判斷「我屬於 0 idea 還是 vague idea」就能開始。

- **AC (Acceptance Criteria: 定義「這條 Story 要做到什麼程度才算完成」的具體、可驗證條件清單)**：
  - 進入 web app 後僅有 1 個主 CTA「開始新諮詢」，不需選擇 Explore / Consult
  - 開場表單完成後由 agent 自動進入 Explore mode，BU 不會看到 mode 術語


#### A2. 開場 metadata 表單
> **身為** BU，
> **我想要** 在開場表單填 BU 別、角色簡述、（選填）第一句 hint，
> **以便** agent 開場就能聚焦到我的領域脈絡。

- **AC**：
  - BU 別（必填；產險 / 壽險 / 銀行 / 證券 / 投信 …）
  - 角色簡述（必填；1–2 句）
  - Raw text hint（選填）
  - 送出後工作區顯示 Explore mode 介面、對話區出現第一題


#### A3. 跨日 Resume
> **身為** BU，
> **我想要** 關掉瀏覽器後下次登入能直接回到上一個中斷點，
> **以便** 我不必重講一次前面的內容。

- **AC**：
  - Sessions 列表顯示該 BU 所有 session、狀態、最後更新時間
  - 點選後恢復到上一個 `interrupt()` 位置（對話紀錄、工作區狀態皆還原）

---

### Epic B — Explore mode（發想 → 聚焦候選）

#### B1. 工作日常自述發散
> **身為** BU，
> **我想要** agent 先問我每天 / 每週的工作，
> **以便** 我可以從熟悉的脈絡出發，而不是空想「AI 能幹嘛」。

- **AC**：
  - 第 1 題落在題庫階段 1（發散）
  - 每輪 agent 問 1 題、最多 2 題
  - 每輪 agent 先 surface 有用資訊（Give-then-Ask），再問下一題

#### B2. 即時看到候選方向卡片
> **身為** BU，
> **我想要** 在對話進行中，右側工作區即時出現候選方向卡片與 5 維度 rubric heatmap，
> **以便** 我能邊講邊看到 agent 怎麼理解我的工作。

- **AC**：
  - 工作區顯示 top 1–3 候選方向卡片
  - 每張卡片有 5 維度分數（rule_repeat / data_avail / reversibility / scale_roi / gap）視覺化
  - 工作區內容隨對話輪次 live 更新

#### B3. Pain signals 與 reframe 視覺標記
> **身為** BU，
> **我想要** 看到哪些是我明說的 pain points，哪些是 agent 主動 reframe 的，
> **以便** 我能分辨「我已確認」vs「agent 提議」的部分。

- **AC**：
  - 工作區卡片上的 pain signals 有 timeline / 標籤
  - Agent reframe 的建議以不同樣式標註（依題庫機制 2 視覺標記）

#### B4. 聚焦到 1–3 個候選方向
> **身為** BU，
> **我想要** agent 在對話後段帶我收斂到 1–3 個候選方向，
> **以便** 我不用自己決定要聚焦哪裡。

- **AC**：
  - 題庫階段 3（收斂）後工作區只留 ≤ 3 張候選卡片
  - 階段 4（Challenge）會 stress-test 最上位候選

#### B5. 明確選定一個方向
> **身為** BU，
> **我想要** 在收斂題明確選定一個候選方向，
> **以便** agent 可以準備進入 Consult mode。

- **AC**：
  - BU 在階段 4 / 5 題目中明確點選或回覆確認
  - 系統標記 `selected_candidate: <rank>`

#### B6. Cold 終止保護
> **身為** BU，
> **我想要** 當我連續 2 輪都說「都不太對」時，agent 不要硬塞進 Consult，
> **以便** 我不會被迫寫一份我還沒想清楚的 BRD。

- **AC**：
  - 連續 2 輪 BU 明確否定（或低信心）→ agent 標記為 cold
  - 工作區顯示「建議離線找 BA 對焦」而非進入 Consult mode

#### B7. 整體對話控制在 5–10 分鐘
> **身為** BU SME，
> **我想要** Explore mode 整體對話大約 5–10 分鐘結束，
> **以便** 我不會覺得「又要開一個半小時會」。

- **AC**：
  - 題庫題數與節奏符合 5–10 分鐘預期
  - 工作區 progress bar 反映已走到哪個階段

---

### Epic C — Mode 交接（Explore → Consult）

#### C1. 交接 modal 確認
> **身為** BU，
> **我想要** 在 Explore 結束時看到 agent 整理好的段落需求描述並詢問我「要不要進入下一步」，
> **以便** 我能在進入 BRD 撰寫前先確認方向沒偏。

- **AC**：
  - 工作區彈出 modal 顯示 200–400 字段落需求描述（§4.1.4 B；長度上限待 §8 Q3）
  - Modal 提供 2 個動作：「進入 Consult mode」 / 「再討論一下」

#### C2. 不可逆單向交接
> **身為** BU，
> **我想要** 知道進入 Consult 後就不會自動退回 Explore，
> **以便** 我能安心地讓工作區切成 BRD 介面而不怕誤觸。

- **AC**：
  - 點選「進入 Consult mode」後 progress bar 推進，工作區切換為 BRD 大綱樹
  - 若想推翻方向，需主動點「重新探索」按鈕

#### C3. 重新探索 escape hatch
> **身為** BU，
> **我想要** 進入 Consult Step 1 看到大綱後，若覺得方向不對，有一個明確按鈕可以回到 Explore，
> **以便** 我不會卡在不想寫的 BRD 上。

- **AC**：
  - 工作區提供「重新探索」按鈕
  - 點選後當前候選方向被標記 cold，agent 回到 Explore mode
  - （具體 UX 細節待 §8 Q7 決議

#### C4. 雙輸出（JSON + 段落）作為交接介面
> **系統** （非 BU 直接可見），
>  Explore 結束時同時產出結構化 JSON 與段落需求描述，
> **以便** Consult mode 能機讀建大綱，BU 也能人讀確認。

- **AC**：
  - JSON 含 `exploration_id / bu / sme_role / candidates / selected_candidate / predicted_consult_fields / trace`
  - 段落文字 200–400 字，涵蓋問題、AI 切入位置、預期 IO、BU vs reframe 標記

---

### Epic D — Consult mode Step 1（自動建大綱）

#### D1. 自動載入模板並初步填章節
> **身為** BU，
> **我想要** 進入 Consult 後不用再從零訪談每個章節，
> **以便** 我只需要補 Explore 還沒講到的部分。

- **AC**：
  - Agent 自動載入該 BU / project_type 的 BRD 模板（YAML config）
  - 以雙輸出為 context，預填能自動推得的章節
  - 工作區在數秒內呈現「BRD 大綱樹」

#### D2. 章節狀態徽章
> **身為** BU，
> **我想要** 在大綱樹上一眼看到哪些章節已填、哪些要訪談、哪些是 AI 科負責，
> **以便** 我知道接下來要花力氣的章節有哪些。

- **AC**：
  - 每章節顯示三種徽章之一：`auto_filled` / `needs_round2` / `placeholder`
  - 點章節可展開已填入內容預覽
- **來源**：§4.2.3 Step 1 第 3–4 點

#### D3. 自動 Layer 1 預填
> **身為** BU，
> **我想要** Consult 不再問我 pre-flight 基本 metadata，
> **以便** 我不會覺得 agent 剛剛才問過又問一次。

- **AC**：
  - `bu / process_target / project_type / one_line_goal` 從 Explore JSON 直接帶入
  - Layer 2 BU-specific 欄位若需要，仍走 web app 開場表單（不再是 Slack modal）

---

### Epic E — Consult mode Step 2（第 2 輪訪談）

> #### Epic E 功用闡述
>
> **定位：整個 BU Agent 的「產出核心」**
>
> Epic E 是 BU Agent 真正**把 粗略 BRD 寫出來**的階段。前面 Epic A~D 是鋪陳（進場、探索方向、自動建大綱），Epic F 是收尾（交接 BA）；**Epic E 才是 BU 實際把需求內容填進 BRD 各章節的主戰場**。
>
> **為什麼叫「第 2 輪」**
>
> | 輪次 | 在哪做 | 做什麼 |
> | --- | --- | --- |
> | 第 1 輪 | Explore mode（Epic B） | 發散工作日常、挖 pain signals、聚焦候選方向 |
> | **第 2 輪** | **Consult Step 2（Epic E）** | **把候選方向逐章展開成 BRD 內容** |
>
>
> **Epic E 要解決的 4 個具體問題**（對應 6 條 Story）
>
> 1. **效率問題 → E1「只針對 needs_round2 訪談」**
>    Consult Step 1 已把章節分成 `auto_filled` / `needs_round2` / `placeholder` 三類，E1 確保 agent 只問 Explore 沒涵蓋到的章節，不重複消耗 BU 時間。
>
> 2. **確認成本問題 → E2「Accept / Refine / Skip」+ E3「工作區 inline edit」**
>    對 agent 已自動填好的 `auto_filled` 章節，BU 不需逐字口述修改：
>    - E2 提供三顆按鈕快速決策（接受 / 要求修改 / 跳過）
>    - E3 允許在工作區直接 inline 改文字，不必透過對話講一遍
>
> 3. **體感問題 → E4「Live 預覽隨對話更新」**
>    BU 在對話區回答時，右側工作區對應章節即時長出內容。解決舊架構「講完整輪不知道寫成什麼樣」的黑盒感，讓 BU 邊答邊看成品形狀。
>
> 4. **卡關保護 → E5「flag_for_ba_review」+ E6「跨章節一致性 quality gate」**
>    - E5：BU 答不出的細節不要硬逼，留記號給 BA 下一階段補洞（避免 BU 為了寫完而亂填）
>    - E6：送出前 agent 自動檢查章節間是否矛盾（避免 BU 疲勞寫出前後不一致的內容）
>
> **在整體流程中的位置**
>
> ```
> Epic B (Explore)         → 挖出候選方向
>    ↓
> Epic C (交接 modal)      → BU 確認、切換 mode
>    ↓
> Epic D (Consult Step 1)  → agent 自動建大綱、分類章節
>    ↓
> 【 Epic E — Consult Step 2 】← 產出 v1.0 BRD 的主戰場
>    ↓
> Epic F (送 BA)           → 交付給 BA Agent
> ```
>


#### E1. 只針對 needs_round2 訪談
> **身為** BU，
> **我想要** 第 2 輪訪談只問 Explore 沒涵蓋的章節，
> **以便** 我的訪談總時間控制在 20–30 分鐘。

- **AC**：
  - Agent 僅對 `needs_round2` 章節提問
  - 對 `placeholder` 章節直接跳過
  - `section_loop` 架構保留但縮減使用範圍

#### E2. auto_filled 章節 Accept / Refine / Skip
> **身為** BU，
> **我想要** 對 agent 已自動填好的章節，能在對話區直接 Accept / Refine / Skip，
> **以便** 我能快速確認不需逐字重打。

- **AC**：
  - 對話區提供三顆按鈕：Accept / Refine / Skip
  - Refine ≤ 3 輪守門（沿用舊 Consult §F-2.2.2，細節待 §8 Q2）

#### E3. 工作區 inline edit
> **身為** BU，
> **我想要** 在右側工作區直接編輯章節內容，
> **以便** 我不需要把想改的字再透過對話講一遍。

- **AC**：
  - 章節段落可點擊進入 inline edit 模式
  - 編輯結果同步回 BRD live 預覽與後端

#### E4. Live 預覽隨對話更新
> **身為** BU，
> **我想要** 章節內容隨對話即時更新，
> **以便** 我能在寫 / 答的同時看到成品形狀。

- **AC**：
  - 對話區每輪回覆後，工作區對應章節即時更新
  - 章節間可自由捲動導航

#### E5. 答不出來可標 flag_for_ba_review
> **身為** BU，
> **我想要** 對我答不出來的細節，agent 不要硬逼，
> **以便** 我可以在留下記號後讓 BA 在下一階段補洞。

- **AC**：
  - Agent 偵測 BU 答不出的章節，自動標 `flag_for_ba_review`
  - Flag 清單會併入 summary.json 傳給 BA Agent

#### E6. 跨章節一致性 quality gate
> **身為** BU，
> **我想要** 在送出前 agent 先做一次一致性檢查，
> **以便** 我不會送出彼此矛盾的章節。

- **AC**：
  - 有衝突時對話區提示並指向對應章節

---

### Epic F — 交接至 BA Agent

#### F1. 送 BA 按鈕
> **身為** BU，
> **我想要** 一個明確的「送 BA」按鈕來結束我的階段，
> **以便** 我知道什麼時候算做完。

- **AC**：
  - 工作區在章節完成後出現「送 BA」按鈕
  - 未完成必要章節前按鈕為 disabled，hover tooltip 說明原因

#### F2. 產出 v1.0 BRD（粗略初版）
> **身為** BU，
> **我想要** 送 BA 時系統產出 v1.0 BRD 初版，
> **以便** BA 能拿到可 review 的版本。

- **AC**：
  - BU 章節（需求背景 / 需求分析 / 執行方式不含 API 格式 / User Cases / 例外處理...等）有內容
  - 載體格式待決議（markdown inline / Google Doc / markdown→docx）

#### F3. 附交付物 summary.json / conversation_trace
> **身為** BA / PM / RD，
> **我想要** 一併拿到 summary.json 與 conversation_trace，
> **以便** 我能快速 onboard 與事後歸因。

- **AC**：
  - summary.json 含 one_line_goal / key_business_rules / io_fields / exception_cases / open_for_ai_team / flag_for_ba_review
  - conversation_trace 涵蓋 Explore + Consult 全程

#### F4. 自動通知 BA（不需 BU 自己 ping）
> **身為** BU，
> **我想要** 系統自動通知 BA，
> **以便** 我不需要去記「誰是我的 BA」或手動發訊息。

- **AC**：
  - 送 BA 後觸發 in-app + email 通知（具體通道待 §8 Q12）
  - BU 端工作區顯示「已通知 BA（@xxx）」

#### F5. BU 端完成畫面
> **身為** BU，
> **我想要** 看到一個明確的「你這邊的工作告一段落」畫面，
> **以便** 我知道可以安心離開。

- **AC**：
  - 工作區切換為「完成」畫面，顯示 BRD 連結 / 預覽、BA handle、「返回 sessions 列表」

---

### Epic G — 平台 / Non-Functional Stories


#### G1. Split layout + mode progress bar
> **身為** BU，
> **我想要** 左對話右工作區的固定版面 + 頂部 progress bar，
> **以便** 我隨時知道走到哪一階段。

- **AC**：
  - Progress bar 三節點：Explore → Consult Step 1 → Consult Step 2
  - 工作區內容隨 mode 切換版面（§10.2）

#### G2. Streaming agent 回覆
> **身為** BU，
> **我想要** agent 回覆以 streaming 方式顯示，
> **以便** 我不用盯著轉圈圈等整段。

- **AC**：
  - 採 SSE 或 WebSocket（擇一，細節待 §8 Q11）
  - 對話區逐字 / 逐段渲染

#### G3. Auto save 與 checkpoint
> **身為** BU，
> **我想要** 對話與章節編輯自動儲存，
> **以便** 停電 / 瀏覽器當掉不會 lose progress。

- **AC**：
  - PostgresSaver 於每個 LangGraph interrupt point 前 checkpoint
  - Save 粒度（每輪 / 每章節 / hybrid）待決議

#### G4. Agent 不代 BU 決策
> **身為** BU SME，
> **我想要** agent 永遠輸出選項讓我挑、不自作主張，
> **以便** 最終責任歸屬清楚在我。

- **AC**：
  - 候選方向由 BU 選擇
  - 章節有 Accept / Refine / Skip 而非自動 confirm

---

## 3. 完整服務流程（詳細步驟）

以下把「BU 打開 web app」到「BA Agent 接手」展開成線性步驟，並標註每一步的 mode、前端動作、後端動作、產生 / 更新的資料。

### Phase 0 — 登入與開場 (Onboarding)

**Step 0.1　登入**
- 前端：BU 以 Cathay AD / SSO 登入 BU Agent web app（§10.5）
- 後端：驗證身分、取得 `user_id`
- 資料：建立或刷新使用者 session token

**Step 0.2　Sessions 列表**
- 前端：顯示該 user 的歷史 sessions（狀態、最後更新時間）+ 頂部「開始新諮詢」CTA（§10.4）
- BU 行為：點「開始新諮詢」→ 進入 Step 0.3；或點舊 session → 跳至該 session 的上一個 interrupt point（Resume，詳 Phase R）

**Step 0.3　開場 metadata 表單**
- 前端：彈出開場表單（BU 別 必填、角色簡述 必填、Raw text hint 選填）
- BU 行為：填寫送出
- 後端：建立新 `session_id`（同時為 LangGraph `thread_id`）、寫入 metadata
- 產出：一筆新 session record，狀態 `explore`

---

### Phase 1 — Explore mode（約 5–10 分鐘）

> 目標：從工作日常自述中挖出 1–3 個候選 AI 切入方向；產出雙輸出交接給 Consult mode。

**Step 1.1　Explore 版面初始化**
- 前端：進入 split layout；左對話區顯示「歡迎 + 第一題」；右工作區顯示空白候選卡片佔位
- 頂部 progress bar：`●Explore ── ○Consult Step 1 ── ○Consult Step 2`
- 後端：LangGraph 啟動 Explore subgraph、設第一個 `interrupt()`

**Step 1.2　題庫階段 1（發散）**
- 內容：1–2 題，詢問 BU 每天 / 每週工作內容（依題庫）
- 每輪規則：Give-then-Ask（先 surface 有用資訊再提問）；每輪 1 題、最多 2 題
- 工作區：候選卡片雛形開始出現

**Step 1.3　題庫階段 2（脈絡建立）**
- 內容：針對 BU 提到的流程深挖 pain signals、量能、反轉性、資料可得性
- 工作區：候選卡片開始有 5 維度 rubric 分數、pain signals timeline 逐步累積
- 視覺標記：BU 明說的 signal vs agent reframe 提議以不同樣式呈現（機制 2）

**Step 1.4　題庫階段 3（收斂）**
- 內容：把候選方向收斂到 ≤ 3 張卡片
- 工作區：只留 top 1–3 候選；其餘收入折疊區

**Step 1.5　題庫階段 4（Challenge）**
- 內容：stress-test 最上位候選（reversibility、scale / ROI、gap 再驗證）
- BU 行為：對 challenge 表達同意 / 反駁 / 修正

**Step 1.6　題庫階段 5（交接準備）**
- 內容：引導 BU 明確選定一個候選方向
- 終止條件判斷：
  - (a) BU 明確選定 → 進 Step 1.7
  - (b) 連續 2 輪表示「都不太對」→ 標 cold、進 Step 1.6-exit（Cold exit）

**Step 1.6-exit　Cold exit（替代分支）**
- 前端：工作區提示「建議離線找 BA 對焦」並提供「返回 sessions 列表」
- 後端：session 狀態 `cold`；不進 Consult mode
- 通知：（可選）通知 BA 該 BU 需離線對焦
- 結束整條流程

**Step 1.7　產出雙輸出**
- 後端：
  - (A) 生成 **結構化 JSON**（含 `exploration_id / bu / sme_role / candidates / selected_candidate / predicted_consult_fields / trace`，§4.1.4 A）
  - (B) 生成 **段落需求描述**（200–400 字，§4.1.4 B）
- 資料：雙輸出寫入 session 附屬欄位，供 Consult mode 讀取

---

### Phase 2 — Mode 交接 (Explore → Consult)

**Step 2.1　交接 modal**
- 前端：工作區彈出 modal，顯示段落需求描述 + 兩顆按鈕「進入 Consult mode」 / 「再討論一下」
- 分支：
  - 按「再討論一下」 → 回到 Step 1.5（可繼續微調）
  - 按「進入 Consult mode」 → 進 Step 2.2

**Step 2.2　版面換檔**
- 前端：
  - Progress bar 推進為 `○Explore ── ●Consult Step 1 ── ○Consult Step 2`
  - 工作區版面從候選卡片換為「BRD 大綱樹」骨架
  - 對話區顯示「正在建立初步 BRD 大綱…」
- 後端：LangGraph 轉入 Consult subgraph；狀態改為 `consult_step1`
- 不可逆性：標記 current candidate 為 `active`，除非 BU 點「重新探索」否則不回 Explore

---

### Phase 3 — Consult mode Step 1（自動建大綱、無對話）

> 目標：auto 填能從 Explore 推得的部分，標記章節狀態。

**Step 3.1　載入模板**
- 後端：依 `bu / project_type` 載入對應 BRD 模板（YAML config）
- Layer 1 Core 5 欄自動帶入（`bu / process_target / project_type / one_line_goal`）
- Layer 2 BU-specific 欄位若開場表單未蒐集，此時補提（罕見；主要在 Step 0.3 蒐集）

**Step 3.2　Prompt LLM 初步填章節**
- 輸入 context：結構化 JSON + 段落需求描述
- 模型：Gemini 2.5 Pro（§10.3 技術棧）
- 輸出：各章節草稿文字 + 每章節狀態
  - `auto_filled`：Explore 已涵蓋，待 BU 確認
  - `needs_round2`：Explore 未涵蓋，待訪談
  - `placeholder`：AI 科 / CD 科章節，本階段跳過

**Step 3.3　工作區呈現大綱樹**
- 前端：BRD 大綱樹顯示章節結構 + 每節狀態徽章 + 已填入內容預覽（可展開 / 折疊）
- BU 行為：
  - 檢視大綱是否合理
  - 若覺得方向偏離 → 點「重新探索」（Step 3.3-exit）
  - 若 OK → 對話區出現 Step 4 第一問

**Step 3.3-exit　重新探索（替代分支）**
- 前端：點「重新探索」按鈕
- 後端：當前候選標 cold；LangGraph 回 Explore subgraph
- 前端：progress bar 回退為 `●Explore`；回到 Step 1.5

---

### Phase 4 — Consult mode Step 2（第 2 輪訪談，約 20–30 分鐘整個 Phase 3+4）

> 目標：針對 `needs_round2` 章節訪談、對 `auto_filled` 章節逐一確認，產出 v1.0 BRD 初版。

**Step 4.1　章節層級訪談（對每個 needs_round2 章節循環）**
- 對話區：agent 對該章節提問（1–2 題）
- 工作區：對應章節以 live 預覽方式逐步 fill
- 規則：
  - 答不出 → agent 詢問是否標 `flag_for_ba_review`；BU 同意則標記、跳下個章節
  - Refine ≤ 3 輪守門（§8 Q2 細節待定）
- 結束單章節條件：BU 明確 Accept / Skip / flag

**Step 4.2　auto_filled 章節確認（對每個 auto_filled 章節）**
- 對話區：agent 呈現 already-drafted 段落 + 三顆按鈕 Accept / Refine / Skip
- 工作區：該章節區塊反白，滑過會高亮
- BU 可在工作區 inline edit 後按 Accept
- 結束條件：BU 對該章節完成一次決策

**Step 4.3　跨章節一致性 quality gate**
- 觸發：所有 `needs_round2` / `auto_filled` 章節皆有決策後
- 後端：跑跨章節一致性檢查
- 分支：
  - 無衝突 → 進 Step 4.4
  - 有衝突 → 對話區指出衝突點與對應章節 → BU 修正 → 再跑 gate

**Step 4.4　「送 BA」按鈕啟用**
- 前端：工作區出現「送 BA」主 CTA（啟用狀態）
- BU 行為：
  - 按「送 BA」 → 進 Phase 5
  - 繼續微調 → 隨時可點（只要 gate 通過）

---

### Phase 5 — 交接至 BA Agent

**Step 5.1　產出交付物**
- 後端生成：
  - **v1.0 BRD 初版**（載體格式待 §8 Q4：markdown inline / Google Doc / markdown→docx）
  - **summary.json**（one_line_goal / key_business_rules / io_fields / exception_cases / open_for_ai_team / flag_for_ba_review）
  - **conversation_trace**（Explore + Consult 全程，含 agent reframe 與 BU 決策路徑）
  - **flag_for_ba_review 清單**（供 BA 優先處理）

**Step 5.2　傳遞給 BA Agent**
- 後端：以 API endpoint 或共用 DB 直讀（待 §8 Q14）將交付物交給 BA Agent
- 後端：session 狀態改為 `handed_off_to_ba`

**Step 5.3　通知 BA**
- 通道：in-app + email（具體通道待 §8 Q12）
- 內容：BRD 連結、BU handle、flag_for_ba_review 摘要

**Step 5.4　BU 端完成畫面**
- 前端：工作區切為「完成」畫面，顯示：
  > 已完成初版 BRD：[BRD 連結 / 預覽]
  > 已通知 BA（@xxx）接手 review。如有後續會議錄音、修訂需求，BA 會用 BA Agent 介面處理（不在這個 session）。
  > 你這邊的工作告一段落。[返回 sessions 列表]
- BU 行為：點「返回 sessions 列表」 → 回 Step 0.2

---

### Phase R — Resume 子流程（任意 phase 可觸發）

**Step R.1　重新登入後點舊 session**
- 前端：從 sessions 列表點未完成的 session
- 後端：以 `user_id` + `session_id` 查 PostgresSaver，取最近 checkpoint

**Step R.2　還原 UI 狀態**
- 前端：
  - Progress bar 回到該 session 當前階段
  - 對話區重播歷史訊息（或僅顯示至上一個 agent reply）
  - 工作區還原對應 mode 的版面（候選卡片 / 大綱樹 / BRD live 預覽）
- 後端：LangGraph 從上一個 `interrupt()` 恢復

**Step R.3　無縫續談**
- BU 行為：直接在對話區輸入回應或在工作區操作，繼續該 phase 的流程

---

## 4. 流程端到端總覽表

| Phase | Mode | 時長估計 | BU 主要動作 | 工作區主要內容 | 主要產出 |
| --- | --- | --- | --- | --- | --- |
| 0. Onboarding | — | < 1 分鐘 | 登入、填開場表單 | Sessions 列表 / 開場表單 | 新 session record |
| 1. Explore | Explore | 5–10 分鐘 | 對話自述工作、選定方向 | 候選卡片 + 5 維 rubric heatmap + pain timeline | 雙輸出（JSON + 段落）|
| 2. 交接 modal | Explore→Consult | < 1 分鐘 | 確認段落、按「進入 Consult」 | 段落需求描述 modal | Consult mode 啟動 |
| 3. Consult Step 1 | Consult | < 1 分鐘（auto） | 檢視大綱 | BRD 大綱樹 + 狀態徽章 | 章節狀態標記 + 初步草稿 |
| 4. Consult Step 2 | Consult | 20–30 分鐘（含 Phase 3）| 訪談、Accept/Refine/Skip、inline edit | BRD live 預覽 + inline edit | v1.0 BRD（粗略初版）|
| 5. 交接 BA | BU Agent 尾端 | < 1 分鐘 | 按「送 BA」 | 完成畫面 | summary.json / trace / BA 通知 |
| R. Resume | 任意 | 視狀態 | 從 sessions 列表點選 | 還原 mode 對應版面 | 無（僅還原） |

---

## 5. 與 Open Questions 的關聯

| Open Q | 影響的 Story / Step |
| --- | --- |
| Q1 Mode 切換自動度 | C1 / Step 2.1 |
| Q2 Refine ≤ 3 輪守門 | E2 / Step 4.1 / Step 4.2 |
| Q3 段落描述長度上限 | C1 / Step 1.7 |
| Q4 v1.0 BRD 載體格式 | F2 / Step 5.1 |
| Q5 JSON schema 完整定義 | C4 / Step 1.7 |
| Q6 Save 粒度 | G5 / Step R |
| Q7 推翻方向 UX | C3 / Step 3.3-exit |
| Q8 trace 權限 | F3 / Step 5.1 |
| Q9 前端框架 | Epic G 全部 |
| Q10 認證機制 | G2 / Step 0.1 |
| Q11 Real-time 通信 | G4 / 所有 streaming 環節 |
| Q12 通知機制 | F4 / Step 5.3 |
| Q13 BA Agent 是否共用前端 | Phase 5 之後 |
| Q14 trace 傳遞形式 | Step 5.2 |

> 決議上述問題前，部分 AC 為草案性質。

---

*— End of BU Agent User Stories and Flow v0.1 —*
