# BU Agent — 對話 / 回覆 / 彈窗邏輯整理

> 依據 `audio` 分支現況；更新日期 2026-05-21
> 範圍：BU Agent（Explore + Consult）；不含 BA Agent
> 用途：日後迭代的 source of truth；新進工程師入門對齊

> **Last updated 2026-05-25** — 同步至 code 現況。本次主要變更：
> - §2.3 / §4.4 補 `pending_ai_necessity_decision` / `pending_stage5_decision` early-return 條件
> - §4 補 score_candidates 的 ai_necessity triage 規則（streak ≥ 2 / 7 類 solution_class）與 stage 5 卡關計數
> - §6 SSE 補 `ai_necessity_warning` / `stage5_stuck` / `bu_turn_recorded` event payload
> - §7 三個彈窗（HandoffConfirm / AiNecessity / Stage5Stuck）改寫為完整 deferred-reply pattern：endpoint / agent 回應 / SSE 事件序
> - 新增 §X meta 問題承接：`explore_question.j2` 最高優先規則（「還有其他方向 / 多給幾個 / 換個角度」→ 先承接 ≤50 字 + 第二句新題）
> - §7 末加「reload 防呆」：cache-read + cleanup effect 雙重保險策略

---

## 目錄

1. [高層概觀](#1-高層概觀)
2. [Explore Subgraph 對話邏輯](#2-explore-subgraph-對話邏輯)
3. [Consult Subgraph 對話邏輯](#3-consult-subgraph-對話邏輯)
4. [Agent 回覆模組（LLM streaming 節點）](#4-agent-回覆模組llm-streaming-節點)
5. [Mode 切換的決策點](#5-mode-切換的決策點)
6. [SSE 事件清單](#6-sse-事件清單)
7. [彈窗觸發 / 按鈕對應](#7-彈窗觸發--按鈕對應)
8. 「卡住」/ 解鎖機制（為什麼有 turn_done）

---

## 1. 高層概觀

### 訊息往返流程

```
[BU 輸入] ──POST /sessions/{id}/messages──> sessions.py
                                              │ _spawn(_run_turn_bg)
                                              │ 回 202 立刻
                                              ▼
                                          session_service.run_turn
                                              │ 1. publish bu_turn_recorded
                                              │ 2. graph.aupdate_state(history+=BU)
                                              │ 3. graph.ainvoke({})  ←─── main_graph route
                                              │                            │
                                              │                            ├─ explore subgraph
                                              │                            └─ consult subgraph
                                              │ 4. publish turn_done (兜底)
                                              ▼
                                          (節點內 stream)
                                          bus.publish(session_id, type, data)
                                              │
                                              ▼
                                          SessionBus (in-memory pub/sub + 256 ring buffer)
                                              │
[ 前端 EventSource ] ◀──SSE──── /sessions/{id}/events  (sse.py)
   │
   ▼
page.tsx onEvent switch → state setters / modal triggers
```

### 名詞表

| 名詞 | 型 | 範圍 | 說明 |
|------|----|------|------|
| `mode` | str | `"explore"` / `"cold"` / `"consult_step1"` / `"consult_step2"` / `"submit"` / `"done"` | 主流程位置；main_graph entry 看 mode 路 explore vs consult |
| `stage` | int | 1–5 | Explore 階段；converge_check 推進；MAX_STAGE=5 |
| `ready_to_handoff` | bool | — | True 時 Explore 直接走 emit_dual_output |
| `selected_candidate` | int? | rank 1–3 | BU 選的候選方向 |
| `scored_candidates` | list | — | LLM 評分過的候選；空 list = 未產出 |
| `history` | list[TraceEntry] | — | BU + agent 全對話；replace semantics（每次傳完整 list） |
| `pending_question` | str? | — | agent 上一問；給 Consult 跨輪追蹤用 |

### Subgraph 職責

- **main_graph** (`backend/app/graph/main_graph.py:30–35`)：根據 `mode` 路給 explore 或 consult。
  `consult_step1` / `consult_step2` / `submit` / `done` → consult；其他 → explore。
- **explore subgraph**：把 BU 自述 → pain signals → 候選方向 → 收斂 → 雙輸出。
- **consult subgraph**：載入 BRD 模板 → 自動填章節 → section_loop 二輪訪談 → quality_gate → build_deliverables。

---

## 2. Explore Subgraph 對話邏輯

對齊 `backend/app/graph/explore/subgraph.py:19–73`。

### 2.1 entry router（START → 哪個節點）

| 條件 | 走向 |
|------|------|
| `state.ready_to_handoff` | `emit_dual_output` |
| history 已含任何 BU reply | 完整 pipeline：`extract_signals` → `cluster_pain_points` → `score_candidates` → `converge_check` |
| 都沒有（首次） | `discovery_loop`（出第一題） |

### 2.2 完整 pipeline 各節點

```
extract_signals  →  cluster_pain_points  →  score_candidates  →  converge_check  ─┐
   (LLM)              (M4 no-op,            (LLM 結構化           (heuristic:        │
                       保拓樸)                + 5 維評分)           stage++/cold/    │
                                                                   stuck/ready)     │
                                                                                    ▼
                                                                              after_converge
```

### 2.3 after_converge 七分支（按優先序）

`backend/app/graph/explore/subgraph.py`

| 順序 | 條件 | 走向 |
|------|------|------|
| 1 **[新增 2026-05-25]** | `state.pending_ai_necessity_decision` | `END`（彈窗已發、等 BU 在 modal 選項，graph 不搶話） |
| 2 **[新增 2026-05-25]** | `state.pending_stage5_decision` | `END`（同上，stage 5 卡關彈窗版） |
| 3 | `state.mode == "cold"` | `END`（cold_exit） |
| 4 | `state.ready_to_handoff` | `emit_dual_output` → `handoff_ready` |
| 5 | `scored_candidates` 非空 + `stage >= 4` + `needs_divergent_question(state)` | `discovery_loop`（換切角發散） |
| 6 | `scored_candidates` 非空 + `stage >= 4` + 其他 | `acknowledge_and_guide`（承接 + 引導選卡） |
| 7 | else | `discovery_loop`（一般輪：問下一題） |

**Pending flags 解除時機**：兩個 `pending_*_decision` flag 是 transient 的：
- `pending_ai_necessity_decision`：在 `acknowledge_ai_necessity_warning` / `override_ai_necessity_warning` / `explain_solution_class` service handler 完成時 clear
- `pending_stage5_decision`：在 `dismiss_stage5_stuck` / `quick_handoff` service handler 完成時 clear

### 2.4 `needs_divergent_question(state)` 觸發條件

`backend/app/graph/explore/nodes.py`（緊接 `_recent` 之後）。回傳 True 代表 BU 對候選不滿
或還沒決定，應換切角發散；False 走承接引導。

**條件 A**：BU 最後一句含任一 `DISSATISFIED_KEYWORDS`：

| 類別 | 關鍵字 |
|------|--------|
| 核心否定 | 不太對、不對、都不是、沒一個對 |
| 軟否定 | 不喜歡、感覺不準、不甚適合、不適合 |
| 認另選 | 再來幾個、想試別的、想試試別的、還有別的、還有别的、換一個、換個、其他 |
| 評論不足 | 太表面、不夠具體、別的面向、别的面向 |

**條件 B**：上一輪 agent 是 `acknowledge_and_guide`（其結尾固定句含「整理在右側」）+
`state.selected_candidate is None` + BU 訊息既不含 `#1`/`#2`/`#3`/「第一/第二/第三」、
也不含任何候選 `direction` 前 6 字。

**[新增 2026-05-25] meta 問題承接（discovery_loop 內 prompt 規則）**：

當 `needs_divergent_question` 為 True、route 到 `discovery_loop` 時，`explore_question.j2`
含一條**最高優先**規則：偵測 BU 是否在問 meta 問題：

- 直接問「還有沒有其他方向 / 還有別的嗎 / 能不能多給幾個 / 換個角度看 / 再來幾個 / 想試別的」
- 對候選不夠滿意但沒否定具體某條（僅說「不太貼切」「不夠具體」「太表面」「都不太對」）

LLM 必須**先用 1 句 ≤ 50 字直接回應**該 meta 問題（如「好,我換個角度，從『XX 流程』再想看看」），
**第二句**才是新探索題（≤ 60 字、挑 stage seeds 中未在 recent_history 出現過的切角）。
整體輸出 ≤ 110 字、最多 2 句。**不**重跑 score_candidates 產新候選，僅文字承接。

### 2.5 兩個保護機制

- **cold_exit**（`converge_check` 內，`backend/app/graph/explore/nodes.py:369–385`）：
  最後 2 個 BU turn 都含「不太對 / 不對 / 沒想法 / no」其中一詞 → 設 `mode="cold"` +
  publish `cold_exit`。
- **stage5_stuck**（同檔案 `converge_check`）：`stage == 5` + 仍未選 candidate +
  `stage_5_rounds >= 3` + 未 `stage_5_stuck_acked` → publish `stage5_stuck` event。
  **[新增 2026-05-25]** 同時 patch `pending_stage5_decision = True` 鎖住本 super-step,
  `after_converge` 看到此 flag 直接 END,讓 graph 不再產 agent 回覆;
  由兩個 modal endpoint（dismiss/quick_handoff）之一接手。

---

## 3. Consult Subgraph 對話邏輯

對齊 `backend/app/graph/consult/subgraph.py:33–69` 與 `nodes.py`。

### 3.1 entry router（START → 哪個節點）

`subgraph.py:42–53`，按優先序：

| 條件 | 走向 |
|------|------|
| `state.mode == "submit"` | `build_deliverables` |
| `brd_outline` 為空 | `load_template`（Step 1 自動建大綱） |
| 任一章節 status 為 `needs_round2` | `section_loop`（Step 2 訪談下一章） |
| 都填完了 | `quality_gate`（跨章節一致性檢查） |

### 3.2 Step 1：建大綱與 auto-fill

進入 consult 第一輪（BU 在 HandoffConfirmModal 點「進入 Consult mode」、`confirm_handoff()`
切 `mode = consult_step1` + 一次 `ainvoke`）：

```
load_template ──> auto_fill_outline ──> section_loop（同一個 super-step）
```

- **`load_template_node`**：依 `state.bu` + selected candidate 的 `project_type` 載
  `backend/app/graph/consult/templates/{BU}_{project_type}.yaml`；找不到 fallback 到
  `default.yaml`。組空 `brd_outline` 骨架，每章帶 `default_status`（多為 `needs_round2`，
  AI 科 / CD 科章節為 `placeholder`）。
- **`auto_fill_outline`**（LLM structured output、`auto_fill_outline.j2`）：
  - 一次產所有 `needs_round2` 章節的 draft（`SectionDraftListOutput`）
  - context 含：selected candidate、explore pain_signals、explore paragraph、
    每章 template 的 `extract_from_explore` hints、`ai_necessity_triage`、knowledge card
  - 失敗或某章漏返回 → `_heuristic_draft()` fallback（規則式短句）
  - `placeholder` 章節寫死「（由 AI 科 / CD 科後續補充）」
  - 末端 publish `outline_ready`、設 `current_section_idx` 指向第一個 `needs_round2`、
    切 `mode = consult_step2`
- **edge**：`auto_fill_outline → section_loop` 直接接（`subgraph.py:64`）。
  v9 改動：同一個 super-step 內就 publish 第一章提問，避免 v6/v7 的兩輪 ainvoke 第二輪
  變 noop 的問題。

### 3.3 Step 2：section_loop 二輪訪談

每次 BU 送訊息進入 consult_step2，`session_service.run_turn` 流程：

```
1. 寫 BU TraceEntry（帶 section_id = current_section_idx 對應章節） + publish bu_turn_recorded
2. _integrate_bu_answer_to_section()：用 apply_section_answer.j2 把 BU 答覆 LLM-merge
   進當前章節 draft，publish section_updated（失敗 fallback：原 draft + [BU 補充] 原話）
3. graph.ainvoke({})：consult subgraph entry → 仍有 needs_round2 → section_loop
4. section_loop 對 current_section_idx 章節用 section_question.j2 產下一道訪談題（streaming）
5. publish turn_done（兜底）
```

#### `section_loop` 節點重點（`nodes.py:314–433`）

- **章節 Q&A 序列**：用 `_previous_qa_for_section(state.history, sid)[-10:]` 過濾出本章
  歷史 turns（依 `TraceEntry.section_id`），不會被別章歷史污染
- **狀態指標**（餵給 prompt）：
  - `rounds_in_this_section`：本章 BU 已回幾次
  - `was_visited`：本章先前已訪談過（rounds≥1 或 draft>100 字）
  - `accept_hint_count`：agent 在本章已提過幾次「Accept / 資訊夠了」
  - `last_bu_is_short`：BU 最後一句是否短答 / 客套（regex：嗯/哦/喔/好/ok/對/不知道/沒有/還好/看你/你決定/都可以 或 ≤20 字）
  - `is_fresh_revisit`：`was_visited` + 從上次 Accept 提示後 BU 還沒新講超過 1 句
- **prefix 立即推送**：先 publish `agent_reply_delta` 帶章節標題 `【{title}】`，再 stream LLM body
- **Auto-advance 強推**：若 `accept_hint_count >= 2` + `last_bu_is_short` + 非 fresh_revisit
  → 直接把本章標 `accepted`、跳下一個 `needs_round2`、publish `section_updated` +
  `current_section_changed`，**接著對下一章 publish 第一道訪談題**（避免 chat 空白）。
  若無下一章 → return 等下次 ainvoke 走 quality_gate。設計理由：prompt 規則 6 在
  count≥2 後會停止追問，count 不再增加；BU 仍只發短答時就強推，避免無限循環。
- **Fallback**：LLM 失敗或回空 → 用 template 第一條 seed question
- **History**：append agent TraceEntry（含 `section_id`、`linked_candidate_id`），
  寫入 `pending_question`
- **agent_reply_done payload 含 `section_id`** → 前端 `setPendingSectionId` 立刻跳章

#### `section_question.j2` 規則（`backend/app/graph/shared/prompts/section_question.j2`）

按 prompt 順序：

1. 一句話、≤ 60 字
2. 不加「請問」「想了解」客套，直接切入
3. 不重問已涵蓋的面向（看 previous_qa）
4. BU 上輪部分回答了 → 改問延伸 / 量化
5. **`is_fresh_revisit` 為 True**（BU 點回頭續訪 accepted/skipped/flagged 章節）：
   - 開場必須是「上次我們聊過 X / Y，你想新增或修正什麼？」
   - 不可從零問起；忽略歷史中的 Accept 提示
6. **`rounds_in_this_section >= 3` + previous_qa ≥ 4 + 非 fresh_revisit** → 收斂模式：
   - `accept_hint_count == 0` → 改問「資訊夠了，要不要先 Accept？」
   - `accept_hint_count == 1` + BU 上句很短 → 「建議直接 Accept；或點 Skip / Flag → BA」
   - `accept_hint_count == 1` + BU 上句有新內容 → 消化它、問延伸、本輪不再提 Accept
   - `accept_hint_count >= 2` → 「這章先停在這裡。Skip / Flag → BA / Accept 任一個都可以推進」、停止追問
7. `rounds >= 2` + BU 答不出來 → 「這部分要不要先 flag 給 BA？」

### 3.4 章節狀態與按鈕

每個 section 有 `status` ∈ {`needs_round2`, `auto_filled`, `accepted`, `skipped`,
`flagged_for_ba`, `placeholder`}。BU 在右側工作區可以：

- **inline edit draft** → PATCH `/sessions/{id}/sections/{section_id}` →
  `edit_section()`：覆寫 draft，標 `last_edit_by="bu"`，publish `section_updated`
- **Accept / Refine / Skip / Flag** → POST `/sessions/{id}/sections/{section_id}/action` →
  `section_action()`：
  - accept → `accepted`；skip → `skipped`；flag → `flagged_for_ba`；refine → 留 `needs_round2`
  - 找下一個 `needs_round2` 章節 set `current_section_idx`；都沒了 set None（觸發 quality_gate）
  - publish `section_updated` + 若有下一章 publish `current_section_changed`
  - 推進 graph 一輪（會跑 section_loop 問下一章 / 跑 quality_gate）
- **點選某章節（含已 accepted / skipped / flagged）** → POST
  `/sessions/{id}/sections/{section_id}/select` → `select_section()`：
  - 該章 reset 為 `needs_round2` + set `current_section_idx`
  - publish `section_updated` + `current_section_changed`
  - 推進 graph 一輪 → section_loop 進「`is_fresh_revisit` 續訪開場」

> 前端守門：accepted / skipped / flagged_for_ba 章節點選時先彈
> `RevisitSectionConfirmModal`（純前端狀態機，不發 SSE），確認後才呼叫 endpoint。

### 3.5 Quality gate

所有 `needs_round2` 都處理掉後，下次 graph entry 走 `quality_gate`：

- LLM structured output（`quality_gate.j2` + `ConflictListOutput`）
- 跳過 `placeholder` 與 `flagged_for_ba` 章節、跳過空 draft
- 章節數 < 2 → 直接 pass
- 命中矛盾 → publish `conflict_detected`（payload 含 `conflicts: [{section_ids, description}]`）
- LLM 失敗 → 預設 pass（不阻擋送 BA）

### 3.6 Build deliverables（送 BA）

BU 點頂部「送 BA」 → POST `/sessions/{id}/submit` → `submit_session()`：

```
1. aupdate_state(mode="submit")
2. graph.ainvoke({}) → entry 看到 mode=submit → build_deliverables
3. build_deliverables 組裝：
   - brd_md：title + sections 全文（含未填章節寫「_(未填)_」）
   - summary_json：one_line_goal、flag_for_ba_review section_ids、ai_necessity_triage 等
   - conversation_trace：完整 history dump
   publish deliverables_ready
4. service 寫 deliverables 表（upsert），切 session.mode=done、status=done
```

前端 `deliverables_ready` 抵達後 `router.push` 到 `/sessions/{id}/done`。

---

## 4. Agent 回覆模組（LLM streaming 節點）

每節列：何時跑、prompt 檔、規則摘要、SSE 事件、寫進 history、fail fallback。

### 4.1 `discovery_loop`（Explore）

- **何時**：entry 首問 / after_converge 第 3、5 條分支
- **Prompt**：`backend/app/graph/shared/prompts/explore_question.j2`
- **規則摘要**：1-2 句、≤ 70 字（stage 4-5 銜接式發散時 ≤ 80 字）、引用 BU 業務術語、不重問
  已給 metadata；**規則 6**（stage 4-5 + 已有候選 + BU 不滿/沒決）要求先具體承接 BU 上句、
  再帶新切角發散
- **SSE**：每 chunk `agent_reply_delta` → 結尾 `agent_reply_done`
- **History**：append agent TraceEntry；`pending_question` 寫成本題
- **Fallback**：LLM 回空字串 → 用題庫 `seeds[0]` 補一發 delta

### 4.2 `acknowledge_and_guide`（Explore）

- **何時**：after_converge 第 4 條分支
- **Prompt**：`backend/app/graph/shared/prompts/acknowledge_and_guide.j2`
- **規則摘要**：開頭承接 BU 上句 ≤ 50 字；結尾固定句「我已經把幾個可能方向整理在右側,
  你覺得哪一個最貼近你想推進的?」；全文 ≤ 100 字、≤ 2 句；**禁止問新探索題**
- **SSE**：`agent_reply_delta` / `agent_reply_done`
- **History**：append agent TraceEntry；`pending_question` 寫成本句
- **Fallback**：LLM 失敗 → 寫死「了解,我把幾個可能方向整理在右側,你覺得哪一個最貼近你想推進的?」

### 4.3 `extract_signals`（Explore，無 streaming）

- **何時**：entry 收到 BU reply 後
- **Prompt**：`backend/app/graph/shared/prompts/extract_signals.j2`（structured output → `PainSignalListOutput`）
- **SSE**：每抽出一條 → `pain_signal_added`
- **State**：append `pain_signals`
- **Fallback**：LLM 失敗 → 把 BU 全段當一條 signal

### 4.4 `score_candidates`（Explore，無 streaming）

- **何時**：cluster_pain_points 後
- **Prompt**：`backend/app/graph/shared/prompts/score_candidates.j2`（structured → `CandidateListOutput`）；
  每條 candidate 含 5 維 score + `solution_class` ∈ 7 類 + `ai_necessity` ∈ {low, medium, high} + `solution_rationale`
- **SSE**：`candidate_updated`
- **AI necessity triage**：
  - 計算 `low_ai_necessity_streak`：top1 ai_necessity == "low" → +1，否則 reset 0
  - 觸發條件 `streak >= 2 and not ai_necessity_warned and top is not None`：
    - publish `ai_necessity_warning`（payload: `solution_class`, `rationale`, `top_candidate`, `candidates: top3`）
    - patch `ai_necessity_warned = True`（避免下次 streak 累加再觸發）
    - patch `pending_ai_necessity_decision = True` **[新增 2026-05-25]**：鎖住本 super-step,
      `after_converge` 看到此 flag 直接 END,讓 graph 不再產 agent 回覆;
      由三個 modal endpoint（acknowledge/override/explain）之一接手後續 LLM stream
- **State**：寫 `scored_candidates` + `candidate_directions`；維護 4 個 ai_necessity 旗標
- **Fallback**：
  - LLM 失敗 + 已有上輪候選 → **republish 上輪、不改 state**（避免畫面突變 preset）
  - LLM 失敗 + 從未有候選（冷啟首輪）→ 套 `_heuristic_candidates_fallback` preset

### 4.5 `emit_dual_output`（Explore）

- **何時**：`ready_to_handoff` 為 True
- **Prompt**：`backend/app/graph/shared/prompts/emit_paragraph.j2`（streaming）
- **內容**：(A) deterministic structured JSON（含 `ai_necessity_triage`、`trace`）+ (B) LLM 寫的 200-400 字段落
- **SSE**：`handoff_ready`（payload: paragraph + structured）
- **Fallback**：段落字數 < 80 或 > 600 → 退 deterministic 模板

### 4.6 AI 必要性彈窗 endpoint handlers（[改寫於 2026-05-25]）

三個 endpoint 共用 `_run_ai_necessity_decision` helper（`backend/app/services/session_service.py`），
跟兩個 atomic helper `_record_bu_option_choice` / `_stream_agent_reply` 組合，採三段式：

1. **記 BU 選項標籤 trace**（寫死 label 字串）→ publish `bu_turn_recorded`
2. **render prompt + LLM stream**（依 endpoint 用不同 prompt）→ publish `agent_reply_delta` × N → `agent_reply_done`
3. **寫 agent trace + clear `pending_ai_necessity_decision`**

| Endpoint | BU label（寫進 history） | Prompt | 額外 state patch |
|---|---|---|---|
| `/ai-necessity/acknowledge` | `「我了解了，讓我繼續想想」` | `acknowledge_ai_necessity.j2` | `ai_necessity_warned=True` |
| `/ai-necessity/override` | `「我有理由，還是想用 AI 試試看」` | `override_ai_necessity.j2` | `ai_necessity_warned=True`, `bu_overrode_ai_necessity=True` |
| `/ai-necessity/explain` | `「想了解 {solution_class} 跟 AI 的差別」` | `explain_solution_class.j2` | `ai_necessity_warned=True` |

三個 endpoint 都用 `_spawn` 背景跑（不阻塞 endpoint 5-15 秒等 LLM）。
LLM 失敗時 `_stream_agent_reply` fallback_text 兜底,確保 UI 不卡死。

### 4.7 Stage 5 卡關 endpoint handlers（[新增 2026-05-25]）

兩個 endpoint 重用同一組 atomic helper：

| Endpoint | BU label | Stream agent? | State patch |
|---|---|---|---|
| `/stage5/dismiss` | `「再聊一下，我想想」` | ✅ 用 `stage5_keep_talking.j2` 跑 LLM stream（80-150 字、提換切角） | `stage_5_stuck_acked=True`, `pending_stage5_decision=False` |
| `/stage5/quick-handoff` | `「先用 #N 試試 BRD」` | ❌ 不 stream，直接走 emit_dual_output | `selected_candidate=N`, `ready_to_handoff=True`, `stage_5_stuck_acked=True`, `pending_stage5_decision=False`，再 `graph.ainvoke({})` 觸發 handoff |

`/stage5/dismiss` 也走 `_spawn` 背景跑（因為現在會 stream）。
`/stage5/quick-handoff` 仍同步等（handoff 流程本來就阻塞 5-10 秒）。

### 4.8 Consult 側節點

詳細流程已在 §3 闡述。各節點的回覆模組速覽：

- **`load_template_node`**：純規則，無 LLM、不 streaming
- **`auto_fill_outline`**：LLM structured output（`auto_fill_outline.j2` + `SectionDraftListOutput`）；publish `outline_ready`；fallback：`_heuristic_draft()`
- **`section_loop`**：LLM streaming（`section_question.j2`）；publish `agent_reply_delta` × N → `agent_reply_done`（含 `section_id`）；fallback：template seed question
- **`_integrate_bu_answer_to_section`**（service-level）：LLM streaming（`apply_section_answer.j2`，但只把結果寫進 draft，**不 publish 給 chat**）；publish `section_updated`；fallback：原 draft + [BU 補充] 原話
- **`quality_gate`**：所有章節非 needs_round2 後跑；LLM 跨章節找矛盾，命中時 publish
  `conflict_detected`
- **`build_deliverables`**：mode=`submit` 時組 BRD markdown + summary.json + trace；
  publish `deliverables_ready`

---

## 5. Mode 切換的決策點

main_graph 內部不切 mode；都由 service 層用 `aupdate_state` 推。

| From → To | 觸發 | 對應 service / endpoint |
|-----------|------|-----------------------|
| (init) → `explore` | session 建立 | `create_session()` |
| `explore` → `cold` | converge_check 判 2-連續否定 | graph 內部（`converge_check`） |
| `explore` → `consult_step1` | BU 在 HandoffConfirmModal 點「進入 Consult mode」 | POST `/handoff/confirm` → `confirm_handoff()` |
| `consult_step1` → `consult_step2` | `auto_fill_outline` 末端 set | graph 內部（同一 super-step 連到 section_loop） |
| `consult_*` → `explore` | BU 點「重新探索」（任何 modal 或頂部按鈕） | POST `/explore/reset` → `reset_explore()` |
| `consult_step2` → `submit` → `done` | BU 點「送 BA」 | POST `/submit` → `submit_session()` |

特例：BU 在 stage 5 stuck modal 點「先用 #N 試試 BRD」 → POST `/stage5/quick-handoff`：
service 直接設 `selected_candidate=N` + `ready_to_handoff=True` + `stage_5_stuck_acked=True`，
下一個 `ainvoke` 走 `emit_dual_output`。

---

## 6. SSE 事件清單

對齊 `frontend/src/lib/sse.ts:18–37 KNOWN_EVENTS` 與 `page.tsx:88–245` switch case。

| Event | Backend publisher | Payload 要點 | 前端 side effect |
|-------|------------------|-------------|----------------|
| `agent_reply_delta` | discovery_loop / acknowledge_and_guide / emit_dual_output / explain_solution_class / section_loop | `turn_id`, `text_delta` | append streaming text；`awaitingAgent = false` |
| `agent_reply_done` | 同上每個 streaming 節點結尾 | `turn_id`, `full_text`, `stage`, 可選 `section_id` | 定版 liveMessages、refetch session、setPendingSectionId |
| `bu_turn_recorded` | session_service.run_turn 寫 BU trace 後 | `turn_id`, `text` | append BU message（dedupe 用 turn_id） |
| `candidate_updated` | score_candidates | `candidates: [...]` | 更新候選卡 |
| `pain_signal_added` | extract_signals | `signal: {...}` | append pain timeline |
| `stage_changed` | converge_check | `stage` | 目前無 side effect（前端讀 data.stage） |
| `stage5_stuck` | converge_check | `rounds`, `candidates` | 開 `Stage5StuckModal`（mode='explore' + 新 event id） |
| `ai_necessity_warning` | score_candidates | `solution_class`, `rationale`, `top_candidate`, `candidates` | 開 `AiNecessityWarningModal`（同上守門） |
| `handoff_ready` | emit_dual_output | `paragraph`, `structured` | 開 `HandoffConfirmModal`（同上守門） |
| `mode_changed` | confirm_handoff / reset_explore | `from`, `to`, 可選 `reason` | refetch session |
| `outline_ready` | consult.auto_fill_outline | `sections: [...]` | 結束 generatingOutline、塞 liveSections |
| `section_updated` | edit_section / section_action / select_section / integrate_bu_answer | `section_id`, `section: {...}` | 更新該章 state |
| `current_section_changed` | section_action / select_section | `section_id` | setPendingSectionId（提早跳章視覺） |
| `cold_exit` | converge_check | `reason` | refetch session |
| `deliverables_ready` | submit_session（推測，目前未在程式中找到顯式 publish；由 mode 切 done 帶動） | — | router push `/sessions/{id}/done` |
| `conflict_detected` | quality_gate | `conflicts: [...]` | alert 顯示矛盾摘要 |
| `turn_done` | session_service.run_turn 結尾無條件 | `mode`, `stage`, `history_len` | `awaitingAgent = false`（兜底） |
| `heartbeat` | sse.py 25s timeout 時 | 空 | （無） |

> SSE endpoint 是 type-agnostic：`backend/app/api/v1/sse.py` 直接把 `payload["type"]`
> 當 event name 送出。新增 event 只需 backend publish + 前端 KNOWN_EVENTS 加名 + 前端
> switch case。

---

## 7. 彈窗觸發 / 按鈕對應

四個 modal。其中三個由 SSE 事件觸發（Explore 相關），一個是純前端狀態機（Consult Revisit）。

### 7.1 HandoffConfirmModal（`components/modal/HandoffConfirmModal.tsx`）

- **開啟條件**：SSE `handoff_ready` 抵達 + `modeRef.current === 'explore'` + event id > 上次處理過
- **Payload**：`paragraph`（200-400 字）
- **按鈕**：

| 按鈕 | 動作 |
|------|------|
| 「進入 Consult mode」 | POST `/sessions/{id}/handoff/confirm` → `confirm_handoff()` 切 `mode=consult_step1` 並 ainvoke 一次 |
| 「再討論一下」 | POST `/sessions/{id}/handoff/dismiss` → 清 `ready_to_handoff` |

### 7.2 Stage5StuckModal（`components/modal/Stage5StuckModal.tsx`）

> **[Deferred-reply pattern 改寫於 2026-05-25]**：彈窗發出時 graph 不再產 agent 回覆;
> BU 點選項後 endpoint 才 record BU label + stream agent reply（quick_handoff 例外不 stream）。

- **開啟條件**：SSE `stage5_stuck` + `modeRef.current === 'explore'` + event id 守門 + `qc.getQueryData<SessionFullState>` 顯示 NOT (`acked && !pending`)
- **Backend 觸發**：`converge_check` 偵測 stage 5 連 3 輪未選 candidate；publish event 同時 set `pending_stage5_decision=True` 暫停 graph
- **Payload**：`rounds`、`candidates: top3`
- **按鈕**：

| 按鈕 | BU label（寫進 history） | 動作 |
|------|------|------|
| 「我還想多聊一下」 | `「再聊一下，我想想」` | POST `/sessions/{id}/stage5/dismiss` → 走 `dismiss_stage5_stuck`：record BU label → LLM stream 用 `stage5_keep_talking.j2` 跑 80-150 字承接（提換切角）→ patch `stage_5_stuck_acked=True`, `pending_stage5_decision=False` |
| 「先用 #N 試試 BRD」 | `「先用 #N 試試 BRD」` | POST `/sessions/{id}/stage5/quick-handoff {rank}` → `quick_handoff`：record BU label → patch `selected_candidate=N` + `ready_to_handoff=True` + `stage_5_stuck_acked=True` + `pending_stage5_decision=False` → `graph.ainvoke({})` 走 emit_dual_output（**不 stream** agent reply） |
| 「換個角度重新發想」 | — | `confirm` 對話框 + POST `/sessions/{id}/explore/reset` → `reset_explore()`（不變） |

前端：handler 點完 `setAwaitingAgent(true)` + `setStage5Stuck(null)` + `qc.invalidateQueries`，
等 SSE 回 `agent_reply_delta` 自動解鎖。

### 7.3 AiNecessityWarningModal（`components/modal/AiNecessityWarningModal.tsx`）

> **[Deferred-reply pattern 改寫於 2026-05-25]**：彈窗發出時 graph 不再產 agent 回覆;
> BU 點任一選項後對應 endpoint 才 record BU label + stream agent reply（三個都 stream）。

- **開啟條件**：SSE `ai_necessity_warning` + `modeRef.current === 'explore'` + event id 守門 + `qc.getQueryData<SessionFullState>` 顯示 NOT (`warned && !pending`)
- **Backend 觸發**：`score_candidates` 偵測 top1 連續 2 輪 `ai_necessity == "low"` + 本 session 未警示過；publish event 同時 set `ai_necessity_warned=True` + `pending_ai_necessity_decision=True`
- **Payload**：`solution_class`、`rationale`、`top_candidate`、`candidates: top3`
- **按鈕**（三個都走 `_run_ai_necessity_decision` 三段式 helper，皆 `_spawn` 背景跑）：

| 按鈕 | BU label（寫進 history） | Prompt | 額外 state patch |
|------|------|------|------|
| 「我了解了，讓我繼續想想」 | `「我了解了，讓我繼續想想」` | `acknowledge_ai_necessity.j2` | — |
| 「我有理由，還是想用 AI 試試看」 | `「我有理由，還是想用 AI 試試看」` | `override_ai_necessity.j2` | `bu_overrode_ai_necessity=True`（會寫進 BRD structured JSON 的 `ai_necessity_triage.bu_overrode`） |
| 「想了解 {solution_class} 跟 AI 的差別」 | `「想了解 {solution_class} 跟 AI 的差別」` | `explain_solution_class.j2` | — |
| 「換個角度重新發想」 | — | — | `confirm` + POST `/explore/reset`（不變） |

三者完成都會 patch `ai_necessity_warned=True` + `pending_ai_necessity_decision=False`。
前端 handler pattern 同 §7.2。

### 7.4 RevisitSectionConfirmModal（`components/modal/RevisitSectionConfirmModal.tsx`）

- **開啟條件**：純前端。`ConsultFullscreenLayout` 內 `handleSelect` 偵測點選的章節 status 屬於
  `REVISIT_CONFIRM_STATUSES = {"accepted", "skipped", "flagged_for_ba"}`，setRevisitTarget
  開啟 modal（**不**先切 localSelectedId，避免取消後視覺殘留）
- **按鈕**：

| 按鈕 | 動作 |
|------|------|
| 確認 | `setLocalSelectedId(target.id)` + `onSelectSection(id)` → POST `/sessions/{id}/sections/{section_id}/select`（後端 reset 為 needs_round2、推 graph 重訪） |
| 取消 | 關閉 modal、不動 localSelectedId |

### 7.5 Reload 防呆（[新增 2026-05-25]）

SessionBus 每 session 保留 256 events ring buffer，reload 時 SSE 重連會 replay 所有歷史，
含 `ai_necessity_warning` / `stage5_stuck`。前端**雙重保險**：

1. **SSE handler cache-read 守門**（`page.tsx` 內每個彈窗 SSE case 內）：
   `const cur = qc.getQueryData<SessionFullState>(['session', sessionId])`，
   看到 `cur?.ai_necessity_warned && !cur?.pending_ai_necessity_decision` ⇒ skip（已選過）；
   stage5 同形 `cur?.stage_5_stuck_acked && !cur?.pending_stage5_decision`。
2. **Cleanup useEffect 兜底**：useQuery settle 後若旗標已 `acked && !pending` 但 modal state 還在，強制 `setXxx(null)` 把殘留 modal 關掉。最壞情況閃一下立刻關。
3. **Handler 點完 invalidate**：三個 ai handler + 兩個 stuck handler 結尾 `qc.invalidateQueries({ queryKey: ['session', sessionId] })`，縮短 cache stale 窗口。

差異化關鍵：`pending=true` 表「上次離開時 BU 還沒選」，reload 後仍要彈讓他完成決策；
`pending=false` 表「已選過」，replay 時略過。`SessionFullState` 透過 `get_session()` endpoint
expose 5 個彈窗旗標（`ai_necessity_warned` / `pending_ai_necessity_decision` / `bu_overrode_ai_necessity` / `stage_5_stuck_acked` / `pending_stage5_decision`）給前端讀。

---

## 8. 「卡住」/ 解鎖機制（為什麼有 turn_done）

前端 `awaitingAgent` 預設靠 `agent_reply_delta` 抵達解鎖。但 graph 有 silent path：

- `cold_exit` 只 publish `cold_exit`、無 reply
- `emit_dual_output` 只 publish `handoff_ready`、無 reply（chat 不該多話）
- 早期 v9 stage>=4 silent END（已被 v10/v11 改回 `acknowledge_and_guide` 或 `discovery_loop`）

兜底：`session_service.run_turn` 結尾無條件 `bus.publish("turn_done", {...})`，前端
`page.tsx` 收到一律 `setAwaitingAgent(false)`。即使日後再加新 silent path 也不會卡 input。

---

## 文件交叉檢核

- 每個 SSE event 在 `backend/app/graph/...`(publisher) + `frontend/src/lib/sse.ts:KNOWN_EVENTS` +
  `frontend/src/app/sessions/[id]/page.tsx` switch 三處對齊
- 每個 modal 提到的按鈕對得上 `backend/app/api/v1/sessions.py` 的 endpoint
- `after_converge` 5 條分支對得上 `backend/app/graph/explore/subgraph.py:53–66`
