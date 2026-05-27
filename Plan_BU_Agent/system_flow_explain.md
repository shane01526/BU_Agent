# BU Agent 流程圖逐張解說

> **配套檔**：`Plan_BU_Agent/system_flow.md`（圖 index）+ `Plan_BU_Agent/diagrams/*.mmd`（圖原始檔）
> **用途**：給新人 onboard 用的逐步講解。每張圖讀完這份等於有人在旁邊邊指邊說。
> 章節對齊 `system_flow.md` 的 Diagram Index：Part A（結構圖）→ L0 / L1.1–L1.6；Part B（sequence）→ S01–S11。

---

## L0 — 端到端旅程 `00_main_journey.mmd`

**這張圖在說什麼**：BU 從打開網站到把 BRD 送出給 BA 之間，整段路會經過哪些畫面、哪些岔出。是所有圖的「總目錄」，後面所有 L1.x 與 Sxx 圖都是這張的局部放大。

**逐步講解**

1. **登入**（`/login`）：mock 模式選一個測試使用者，cookie 存 `x-dev-user-id`。
2. **Sessions 列表**（`/sessions`）：兩條路 — 點「開始新諮詢」進 New Session 表單；或點舊 session 走 Resume 路徑（詳 S02）。
3. **New Session 表單**（`/sessions/new`）：頁面一進來就 `GET /api/v1/models` 動態抓模型清單；BU 填 BU 別 / 角色 / hint，挑一個 LLM model，送出後呼叫 `create_session`（`session_service.py:24`）。建完立刻在背景 spawn 第一輪 graph kickoff。
4. **進入 Explore mode**：第一題由 `discovery_loop`（`nodes.py:124`）產生，用 `explore_question.j2` LLM stream 出來。
5. **Explore 對話迴圈**：BU 每送一則訊息走一次「extract_signals → cluster → score_candidates → converge_check → 路由」。`score_candidates` 產 candidates（含 5 維 score + solution_class + ai_necessity 標記）；`converge_check` 推進 stage（1→5）並偵測 cold / stuck。
6. **三條岔出**：
   - **AI 必要性彈窗**：top1 `ai_necessity=low` 連續 ≥2 輪、未 warned 過 → 彈 `AiNecessityWarningModal`（詳 S05）。
   - **Stage 5 收斂彈窗**：stage=5 連 3 輪未選 candidate、未 acked → 彈 `Stage5StuckModal`（詳 S06）。
   - **Cold Exit**：BU 連續 2 輪否定 → 設 `mode=cold`（詳 S11 Path B）。
7. **進入 Consult**：BU 點候選卡（或 Stage 5 quick_handoff）→ `emit_dual_output`（`nodes.py:551`）產 paragraph + structured JSON → 彈 `HandoffConfirmModal`（詳 S07）→ 確認後進 Consult Step 1。
8. **Consult Step 1**：`load_template` 讀 BU 對應 yaml + `auto_fill_outline` 用 LLM structured output 一次填好整個 BRD 大綱草稿。
9. **Consult Step 2**：對 `needs_round2` 章節跑 `section_loop` 一章一章訪談；BU 可 inline edit、按 Accept/Refine/Skip/Flag、或點 strip 切到別章重訪（`select_section` 含 RevisitSection 防呆）。
10. **送 BA**：所有章節都不在 `needs_round2` 後跑 `quality_gate` 檢查跨章衝突（M3 永遠 pass），BU 點「送 BA」→ `build_deliverables` 寫 deliverables 表 → 跳 `/sessions/[id]/done`。

**重點觀念**：mode 切換（explore / consult_step1 / consult_step2 / cold / submit / done）都不在 graph 內部切，是 service layer 用 `aupdate_state` 推（詳 L1.6）。

---

## L1.1 — Explore Subgraph `10_explore_subgraph.mmd`

**這張圖在說什麼**：Explore 模式內部的 LangGraph 拓樸 — 從 `entry_router` 進來會分流到三條起點，最後在 `after_converge` 用「優先序的 7 分支」決定下一步。

**逐步講解**

1. **`entry_router`**（`subgraph.py:30-43`）三個入口：
   - `ready_to_handoff=True`（BU 已選候選或 quick_handoff）→ 跳 `emit_dual_output`。
   - history 含 BU reply → 進 pipeline `extract_signals`。
   - 首輪、history 空 → 直接 `discovery_loop` 出第一題。
2. **Pipeline 三節點**（任一 BU 訊息會跑完）：
   - `extract_signals`（`nodes.py:188`）：LLM structured output 抽 pain signals，publish `pain_signal_added`。
   - `cluster_pain_points`（`nodes.py:305`）：M4 仍是 no-op，保留拓撲位置。
   - `score_candidates`（`nodes.py:311`）：LLM structured output 產 candidates 含 5 維 score + solution_class + ai_necessity，publish `candidate_updated`。
3. **AI 必要性彈窗判定**：score 完看 top1 是否 `ai_necessity=low` 連續 ≥2 輪、未 warned 過 — 是的話 publish `ai_necessity_warning`、patch `pending_ai_necessity_decision=True` + `ai_necessity_warned=True`（避免再彈）。然後仍然繼續走 `converge_check`（讓 stage 該推進就推）。
4. **`converge_check`**（`nodes.py:431`）：判 stage 是否要遞進；遞進時 publish `stage_changed`；同時偵測 cold（2 連否定 → set `mode=cold`、publish `cold_exit`）與 stage 5 stuck（連 3 輪未選 → publish `stage5_stuck`、patch `pending_stage5_decision=True`）。
5. **`after_converge` 七分支**（`subgraph.py:53-72`，**優先序由上到下**）：
   1. `pending_ai_necessity_decision=True` → END（不產 agent reply，等 modal endpoint 接手）。
   2. `pending_stage5_decision=True` → END（同上）。
   3. `mode=cold` → END。
   4. `ready_to_handoff=True` → `emit_dual_output`。
   5. scored + stage≥4 + `needs_divergent_question=True` → `discovery_loop`（出新角度題）。
   6. scored + stage≥4 + 其他 → `acknowledge_and_guide`（承接 + 引 BU 看候選卡）。
   7. else → `discovery_loop`（一般往下一階段問）。
6. **三個輸出節點**都 LLM stream + publish `agent_reply_delta×N` + `agent_reply_done`：`discovery_loop`（題庫種子 + LLM 改寫）、`acknowledge_and_guide`、`emit_dual_output`（後者另外 publish `handoff_ready`）。
7. **輔助判斷器 `needs_divergent_question`**（`nodes.py:95`）：兩個觸發條件 — A：BU 上句含 DISSATISFIED_KEYWORDS（其他 / 再來幾個 / 不太對 / 太表面 等）；B：上輪剛跑過 `acknowledge_and_guide`、BU 沒選候選也沒提到候選。命中就把第 5 分支推上，避免一直在 stage 5 卡死。

**為什麼 7 分支前兩個是 pending flag**：deferred-reply pattern — graph 在彈窗期間不能搶話（會兩條訊息打架），必須先讓 BU 點 modal 後 endpoint 接手回應。詳 L1.3。

---

## L1.2 — Consult Subgraph `11_consult_subgraph.mmd`

**這張圖在說什麼**：Consult 模式的 LangGraph 拓樸。`entry` 看 `mode` + `brd_outline` 狀態做四分支，覆蓋 Step 1（建大綱）、Step 2（訪談）、quality_gate（送 BA 前最後一關）、build_deliverables（產 BRD 與 summary）。

**逐步講解**

1. **`entry`**（`subgraph.py:42-53`）四個分支：
   1. `mode='submit'`（service 層在「送 BA」時 set 的）→ `build_deliverables`。
   2. `brd_outline` 空（首進 `consult_step1`）→ `load_template_node`。
   3. 仍有 `needs_round2` 章節 → `section_loop`。
   4. 全部章節都不是 `needs_round2` → `quality_gate`。
2. **Step 1 兩節點同 super-step 相連**：
   - `load_template_node`（`nodes.py:127`）：讀 `templates/brd/{bu}_{type}.yaml`，找不到 fallback 到 `default.yaml`。
   - `auto_fill_outline`（`nodes.py:167`）：LLM structured output（`SectionDraftListOutput`）一次產出所有章 draft + 初始 status；publish `outline_ready`，再 set `mode='consult_step2'` + `current_section_idx`，**同 super-step 直接連到 `section_loop` 出第一題**（不必等 BU 再送一次訊息）。
3. **`section_loop`**（`nodes.py:314`）：對當前 `needs_round2` 章 LLM stream 一道訪談題（`section_question.j2`），publish `agent_reply_delta×N` + `agent_reply_done`，event payload 帶 `section_id`。
4. **`quality_gate`**（`nodes.py:510`）：所有章不在 `needs_round2` 才會跑；LLM 跨章節 conflict 檢查（M3 mock 永遠 pass，命中時 publish `conflict_detected`）。
5. **`build_deliverables`**（`nodes.py:552`）：用 outline 拼 BRD markdown、組 `summary.json`（trace + selected candidate + ai_necessity_triage）、組 `flag_for_ba_review`（flagged 章節清單），最後 publish `deliverables_ready`（`nodes.py:596`）。
6. **外部 service 入口**（圖中虛線）：
   - 對 chat 回 BU reply：`run_turn` 後呼叫 `_integrate_bu_answer_to_section`（`session_service.py:203`）把 BU 答案 LLM-merge 進當前章 draft，然後 ainvoke graph 繼續。
   - inline edit / Accept-Refine-Skip-Flag：`edit_section`（`session_service.py:305`）/ `section_action`（`session_service.py:345`），可能不需要 graph，也可能 ainvoke 走下一章（詳 S08）。
   - 點 strip 切章：`select_section`（`session_service.py:419`），把該章 reset 為 `needs_round2` 後 ainvoke（詳 S09）。
   - 送 BA：`submit_session`（`session_service.py:477`）`aupdate_state mode='submit'` + ainvoke（詳 S10）。

---

## L1.3 — Deferred-Reply Pattern `12_deferred_reply_pattern.mmd`

**這張圖在說什麼**：兩個彈窗（AiNecessityWarning / Stage5Stuck）共用的 state machine 設計。**為什麼存在**：graph 在彈窗期間如果繼續產 agent reply，BU 會看到「兩個訊息同時來」（modal 一個 + chat 一個），體驗很爛。所以引入兩個 transient flag 鎖住 graph，等 modal endpoint 接手才放出回應。

**逐步講解**

1. **Idle**：session 初始狀態，兩個 pending flag 都是 False，graph 自由跑。
2. **Idle → AiPending**：`score_candidates` 偵測 top1 `ai_necessity=low` 連續 ≥2 輪 + 未 warned → 同時 patch `pending_ai_necessity_decision=True` 與 `ai_necessity_warned=True` + publish `ai_necessity_warning`。
3. **AiPending → AiPending（self loop）**：在 BU 點 modal 之前如果還有任何事情觸發 `after_converge`，第一分支會看到 flag 直接 END，不產 agent reply。輸入框前端也 disabled。
4. **AiPending → Idle**：BU 點任一選項（acknowledge / override / explain）→ `POST /sessions/{id}/ai-necessity/{kind}` → `_run_ai_necessity_decision`（`session_service.py:616`）三段式：
   1. `_record_bu_option_choice` — 把 BU 選項固定 label 寫進 history、publish `bu_turn_recorded`。
   2. `_stream_agent_reply` — 用對應 prompt（`acknowledge_ai_necessity.j2` / `override_ai_necessity.j2` / `explain_solution_class.j2`）LLM stream 回應。
   3. clear `pending_ai_necessity_decision=False`（`override` 額外 patch `bu_overrode_ai_necessity=True`）。
5. **Idle → S5Pending**：`converge_check` 偵測 stage=5 連 3 輪未選、未 acked → patch `pending_stage5_decision=True` + publish `stage5_stuck`。
6. **S5Pending → Idle（dismiss）**：BU 點「再聊一下」 → `POST /stage5/dismiss` → `dismiss_stage5_stuck`（`session_service.py:752`）三段式同上，prompt 用 `stage5_keep_talking.j2`，最後 patch `stage_5_stuck_acked=True` + clear pending。
7. **S5Pending → ReadyHandoff（quick_handoff）**：BU 點「先用 #N 試試 BRD」 → `POST /stage5/quick-handoff` → `quick_handoff`（`session_service.py:822`）：record BU label、patch `selected_candidate=N` + `ready_to_handoff=True` + `stage_5_stuck_acked=True` + clear pending，**不 stream agent reply**，直接 ainvoke 觸發 `emit_dual_output`。
8. **ReadyHandoff → [*]**：`emit_dual_output` publish `handoff_ready`，BU 在 `HandoffConfirmModal` 確認後進 Consult。

**Reload 防呆**（圖中右側 note）：
- `SessionFullState` 把 `ai_necessity_warned` / `pending_ai_necessity_decision` / `stage_5_stuck_acked` / `pending_stage5_decision` 都 expose 出來。
- 前端 SSE handler 用 `qc.getQueryData<SessionFullState>` 同步讀 react-query cache：`warned && !pending` → SKIP（已決策），`warned && pending` → 仍要彈（沒選就重整），`!warned` → 第一次正常彈。
- 額外 cleanup `useEffect` 兜底：如果 useQuery settle 後 `acked && !pending`，但 modal state 還沒清，強制 `setStage5Stuck(null)`。

---

## L1.4 — SSE Event 全圖 `13_sse_event_flow.mmd`

**這張圖在說什麼**：所有 SSE event 從哪個 backend node 發出、流經 SessionBus（含 256 events ring buffer）、到哪個 frontend handler。是 backend / frontend / SSE bus 三方整合的對照表。

**逐步講解**

1. **左欄 Backend Publishers**：
   - Explore：`discovery_loop` / `acknowledge_and_guide` / `emit_dual_output` / `extract_signals` / `score_candidates` / `converge_check`。
   - Consult：`auto_fill_outline` / `section_loop` / `quality_gate`。
   - Service 層：`session_service.py`（含 `run_turn` / `confirm_handoff` / `reset_explore` / `edit_section` / `section_action` / `select_section` / `_record_bu_option_choice` / `_stream_agent_reply` / `_run_ai_necessity_decision`）。
2. **中欄 SSE Bus**（`events.py:SessionBus`）：
   - `publish(session_id, event_type, data)`：寫 ring buffer（HISTORY_LIMIT=256）+ 發給所有 subscriber。
   - `subscribe(session_id, last_event_id)`：建一條 queue，先把 ring buffer 內 ≥`last_event_id` 的事件 replay 過去，之後接收實時事件。
3. **17 個 content event + heartbeat**：
   - **對話骨幹**：`bu_turn_recorded` / `agent_reply_delta` / `agent_reply_done` / `turn_done`（最後這個是 `run_turn` 結尾無條件發、做 `setAwaitingAgent(false)` 兜底）
   - **Explore 邏輯**：`pain_signal_added` / `candidate_updated` / `stage_changed` / `ai_necessity_warning` / `stage5_stuck` / `cold_exit` / `handoff_ready` / `mode_changed`
   - **Consult 邏輯**：`outline_ready` / `section_updated` / `current_section_changed` / `conflict_detected` / `deliverables_ready`
   - **基礎建設**：`heartbeat`（每 25s）
4. **右欄 Frontend Handler**（`page.tsx` switch case 約 88-245）：每個 content event 對應一個動作，例如 `agent_reply_delta` → 累加 streaming text + `setAwaitingAgent(false)`、`ai_necessity_warning` → `setAiNecessityWarn(payload)` 並做 cache-read guard。
5. **顏色分群**：
   - 綠（一般 SSE）：對話 / pipeline 事件。
   - 黃（deferred-reply）：`ai_necessity_warning` / `stage5_stuck` — 帶 reload 防呆邏輯。
   - 紅（cold）：`cold_exit`。
6. **`stage_changed` 特例**：在 `KNOWN_EVENTS` 但前端目前沒寫專屬 handler；保留是為將來要做 stage 推進視覺提示時可以直接接。

---

## L1.5 — LLM 多後端路由 `14_llm_routing.mmd`

**這張圖在說什麼**：M4 多 LLM 後端的全貌 — 從前端模型選單到 backend 怎麼挑 backend / 怎麼快取 / 怎麼 fallback。

**逐步講解**

1. **Frontend / New Session 頁**：
   - 進頁 `api.listModels()` → `GET /api/v1/models`。
   - 拿到清單後渲染下拉，OpenAI / Gemini 分組，缺對應 key 的選項自動 disabled，預設選中 `DEFAULT_MODEL`。
   - 送出 `createSession` 帶 `{bu, sme_role, raw_hint, llm_model}`。
2. **Backend `GET /api/v1/models`**（`main.py:list_models`）→ `models_catalog.list_chat_models()`：
   - 並行打 OpenAI `GET /v1/models`（Bearer key）與 Gemini `GET /v1beta/models?key=...`。
   - 過濾：`_is_openai_chat_model` 排除 image / tts / transcribe / embedding / moderation / sora / instruct / babbage / davinci / deep-research / computer-use / realtime-translate；`_is_gemini_chat_model` 排除 image / tts / embedding / imagen / veo / lyria / robotics / native-audio / gemma / aqa / nano-banana / computer-use / deep-research。
   - **5 分鐘 in-memory cache**（`_cached(kind, fetcher)`）：避免每開一次 New Session 都打外部 API。
   - **Fallback**：兩家都掛時用 `.env` 的 `ALLOWED_MODELS` CSV 白名單；任一邊掛仍給對方完整清單 + `failures` array 標哪邊掛了。
3. **`POST /sessions`** → `create_session`（`session_service.py:24`）：驗 `chosen_model`，空值用 `settings.default_model`，寫入 `sessions.llm_model`（migration 0002 加的欄位）。
4. **節點呼叫 LLM**：所有 graph node 都用 `get_llm(state.llm_model)` 拿 backend，不要寫死。`get_llm` 內部：
   - 先 `_resolve_backend(model)` 依前綴決定 kind：`gpt-/o1/o3/o4/chatgpt-/chat-latest` → OpenAI；`gemini-` → Gemini；其他 / `LLM_MODE=mock` / 對應 key 缺 → Mock。
   - 用 `(kind, model)` 當 cache key 從 `clients` dict 拿（沒命中才 instantiate ChatOpenAI / ChatGoogleGenerativeAI）。
5. **三個 backend**：
   - `_OpenAIBackend`：langchain-openai ChatOpenAI、temperature=0.3。
   - `_GeminiBackend`：langchain-google-genai ChatGoogleGenerativeAI、temperature=0.3。
   - `_MockBackend`：依 stage 回固定罐頭題，給離線 dev / 沒 key 場景用。
6. **`.env` 影響範圍**（圖中虛線標）：`LLM_MODE` 影響 resolve；`OPENAI_API_KEY` / `GEMINI_API_KEY` 各自影響對應 fetch 與 backend；`DEFAULT_MODEL` 在 service 層當預設；`ALLOWED_MODELS` 是 list 全失敗時的 fallback。

**為什麼 session-level 綁定**：BRD 草擬橫跨 explore + consult，如果中途換 model 文風會漂移；在 `sessions.llm_model` 凍結一個 model 整段用同一顆 LLM。

---

## L1.6 — Session Mode 狀態機 `15_session_mode_states.mmd`

**這張圖在說什麼**：`mode` 欄位在 session 整個生命週期內怎麼轉換。**重點**：mode 切換**不在 graph 內部做**，全部由 service layer 用 `aupdate_state` 推 — 這是刻意設計，graph 只專心跑 LLM 邏輯，狀態切換由 endpoint handler 承擔。

**逐步講解**

1. **[*] → explore**：`create_session`（`session_service.py:24`）建 session 時 set `mode='explore'`、`stage=1`。
2. **explore → cold**：`converge_check` 偵測 BU 連續 2 輪否定，設 `mode='cold'` + publish `cold_exit`。
3. **explore → consult_step1**：BU 在 `HandoffConfirmModal` 點「進入 Consult mode」 → `confirm_handoff`（`session_service.py:157`）`aupdate_state mode='consult_step1'` + publish `mode_changed`。
4. **consult_step1 → consult_step2**：`auto_fill_outline`（`consult/nodes.py:167`）末端 set `mode='consult_step2'` + `current_section_idx`，**同 super-step 直接進 `section_loop` 出第一題**（沒有 BU interaction 中斷）。
5. **consult_step2 → consult_step2（self loop）**：BU 訊息 / inline edit / `section_action` / `select_section` 都在 step2 處理 `needs_round2` 章節。
6. **consult_step2 → submit**：BU 點「送 BA」 → `submit_session`（`session_service.py:477`）`aupdate_state mode='submit'` 觸發 `build_deliverables`。
7. **submit → done**：`build_deliverables` 完成（`consult/nodes.py:552`）寫 deliverables 表 + `session.status='done'`。
8. **逃生路徑 consult_step1 / consult_step2 → explore**：`reset_explore`（`session_service.py:853`，**C3 escape hatch**）— BU 點「重新探索」清掉 candidates / outline / history / pain_signals / pending flags，回 explore mode 重起，publish `mode_changed`。
9. **末端**：`cold` → BU 回 sessions list（圖中標 `[*]`）；`done` → 跳 `/sessions/[id]/done`。

**圖中兩個 note 提醒**：
- explore 內部有 stage 1→5 與三個彈窗，遇彈窗時 graph 暫停 pending，BU 點選項後仍留在 explore（不切 mode）。
- consult_step2 內 BU 可任意章節 inline edit / Accept / Refine / Skip / Flag / 切到別章重訪；只有全部章節都不在 `needs_round2` 時才會推進到 `quality_gate`。

---

## S01 — 建立 Session（含模型選擇）`20_seq_create_session.mmd`

**User action**：BU 在 `/sessions/new` 填表 + 選模型 + 送出。

**逐步講解**

1. **進頁就抓模型**：FE → API `GET /api/v1/models` → `models_catalog.list_chat_models()`。
2. **並行打 OpenAI + Gemini**：分別過濾出 chat 模型；5 分鐘 cache（後續同一個瀏覽器 / 容器 5 分鐘內不會再打外部 API）。
3. **回應 JSON**：`{models, default, backends_available, source='live'}`，前端拿來渲染下拉，缺 key 的分組 disabled。
4. **BU 填表 + 送出**：FE → API `POST /api/v1/sessions {bu, sme_role, raw_hint, llm_model}`。
5. **Service `create_session`**：驗 `chosen_model` + fallback 到 `settings.default_model`；INSERT 一筆 sessions row（`mode='explore'`、`stage=1`、`status='active'`、帶 `llm_model`）。
6. **背景跑首輪 graph**：API 端 `_spawn(_run_turn_bg(sid, None))`、回 201 給前端。前端 `router.push('/sessions/[id]')` 進對話頁。
7. **Background：首輪 kickoff**：
   - `run_turn(db, session, bu_text=None)`（`session_service.py:50`）。
   - 首次 `ainvoke({})`，graph 從 START 進 `entry_router`，看 history 空 → `discovery_loop`（`nodes.py:124`）。
   - 用 `get_llm(state.llm_model).chat_stream` + `explore_question.j2` 出第一題。
   - Streaming：每個 chunk → publish `agent_reply_delta` → SSE → 前端對話區累加。
   - 結尾 publish `agent_reply_done` + `turn_done`，前端 `setAwaitingAgent(false)`。
8. 進頁時 SSE 連線已建好（前端在切到 `/sessions/[id]` 時就 subscribe），第一題出現在對話區。

---

## S02 — Resume Session + SSE Replay 防呆 `21_seq_resume_session.mmd`

**User action**：F5 重整、或從 sessions list 點進舊 session。**重點**：SSE ring buffer 會 replay 過去事件（含過去的彈窗 event），需要前端做防呆避免重彈過。

**逐步講解**

1. **並行**：
   - FE → API `GET /api/v1/sessions/{id}` → 讀 PostgresSaver 的 GraphState 還原 → 回 `SessionFullState`（含 5 個彈窗旗標：`ai_necessity_warned` / `pending_ai_necessity_decision` / `stage_5_stuck_acked` / `pending_stage5_decision` / `ready_to_handoff`）→ 前端 useQuery cache 寫入 `['session', sessionId]`。
   - FE → API `GET /api/v1/sessions/{id}/events`（EventSource，無 Last-Event-ID）→ Bus subscribe `last_event_id=0` → 從 ring buffer 把所有歷史事件 replay 過去。
2. **SSE 收到舊的 `ai_necessity_warning`**：handler 在 `page.tsx` 約 line 180：
   - 先 `cur = qc.getQueryData<SessionFullState>(['session', sessionId])`。
   - `warned && !pending` → SKIP（BU 已決策過、不要再彈）。
   - `warned && pending` → 仍要彈（BU 沒選就重整，要讓他完成決策）。
   - `!warned` → 第一次正常彈（理論上 reload 不會走到這支，因為已 publish 過必 warned 過，但邏輯保留）。
3. **SSE 收到舊的 `stage5_stuck`**：同形 cache-read guard，看 `stage_5_stuck_acked && !pending_stage5_decision` → 已 ack 就 skip，否則 `setStage5Stuck(...)`。
4. **兜底 cleanup useEffect**（`page.tsx` 約 line 70-90）：監聽 `data.stage_5_stuck_acked` + `pending_stage5_decision` 變化；如果 useQuery settle 後 `acked && !pending` 但 modal state 還在，強制 `setStage5Stuck(null)`。AI 必要性同款邏輯。
5. **對話區渲染**：`liveMessages` 空時用 `historyToMessages(data)` 從 `SessionFullState.history` 還原舊訊息；之後 SSE replay 的 `bu_turn_recorded` / `agent_reply_done` 會被 append（用 `turn_id` dedupe）。

**為什麼三層防呆（cache-read + cleanup useEffect + dedupe）**：因為 EventSource 沒有 Last-Event-ID 支援、ring buffer 也會 replay 全部過去事件，重整一次 modal 可能觸發 setState 兩次（react-query refetch + SSE replay）。三層保險才能穩。

---

## S03 — Explore 送訊息一輪 `22_seq_send_message_explore.mmd`

**User action**：BU 在對話區送一則訊息（Explore 階段 1-5 任一）。

**逐步講解**

1. **送出**：BU 輸入 + 送出 → FE `setAwaitingAgent(true)` 鎖輸入框 → `POST /sessions/{id}/messages {text}`。API 立刻 `_spawn(_run_turn_bg(sid, text))`、回 202。
2. **`run_turn`**（`session_service.py:50`，背景跑）：
   - `aget_state` 拿既有 GraphState。
   - `aupdate_state {history: history + [bu_trace]}`（注意：**replace semantics**，不是 `operator.add` reducer）。
   - publish `bu_turn_recorded {turn_id, text}` → 前端 append BU 泡泡。
3. **`ainvoke({})` 從 START 跑一個 super-step**：
   - `entry_router`（`subgraph.py:30`）看 history 含 BU reply → `extract_signals`。
   - `extract_signals` LLM structured `PainSignalListOutput` → publish `pain_signal_added × N`。
   - `cluster_pain_points` no-op。
   - `score_candidates` LLM structured `CandidateListOutput` → publish `candidate_updated`。前端工作區候選卡更新。
4. **AI 必要性彈窗判定**：score 後若 top1 `ai_necessity=low` 連續 ≥2 + 未 warned → publish `ai_necessity_warning` + patch `ai_necessity_warned=True` + `pending_ai_necessity_decision=True`。前端 `setAiNecessityWarn(...)`（後續見 S05）。
5. **`converge_check`**（`nodes.py:431`）：推進 stage、偵測 cold / stuck。
   - stage=5 + 未選 + `stage_5_rounds≥3` + 未 acked → publish `stage5_stuck` + patch `pending_stage5_decision=True`（見 S06）。
   - 2 連否定 → set `mode='cold'` + publish `cold_exit`。
6. **`after_converge` 七分支（按優先序）**：
   - `pending_ai_necessity_decision` 或 `pending_stage5_decision` → END（不產 agent 回覆，等 modal endpoint 接手）。
   - `mode=cold` → END。
   - stage≥4 + `needs_divergent_question` → `discovery_loop` LLM stream（含 meta 問題承接最高優先規則）。
   - stage≥4 + 其他 → `acknowledge_and_guide`（承接 + 引 BU 看候選卡）。
   - 一般 → `discovery_loop`（下一階段 seed 改寫）。
7. **無論走哪條**，最後 `run_turn` 結尾 publish `turn_done`（兜底）→ 前端 `setAwaitingAgent(false)` 解鎖輸入。

---

## S04 — 點候選卡 → handoff_ready `23_seq_select_candidate.mmd`

**User action**：BU 在工作區點某張候選卡片。

**逐步講解**

1. **前端立刻 UI 反應**：`setSelectedRank(N)` + `setGeneratingHandoff(true)`（顯示 loading）→ `POST /sessions/{id}/candidates/select {rank: N}`。
2. **Service `select_candidate`**（`session_service.py:897`）：
   - `aupdate_state {selected_candidate: N}`。
   - `aget_state` 取最新 state。
3. **判斷是否觸發 handoff**：
   - `scored_candidates` 非空 + 還沒 `ready_to_handoff` → `aupdate_state {ready_to_handoff: True}` + `ainvoke({})` 推進 graph。
   - 候選清單還沒形成（極早期就點，不太會發生）→ 只記錄 `selected_candidate` 不觸發 handoff。
4. **觸發 handoff 路徑**：
   - graph `entry_router` 看 `ready_to_handoff=True` → `emit_dual_output`（`nodes.py:551`）。
   - 組 structured JSON：含 `ai_necessity_triage`（`selected_solution_class` / `selected_ai_necessity` / `selected_rationale` / `bu_overrode`）+ `candidates`（含 rubric） + `selected_candidate`。
   - LLM stream `emit_paragraph.j2` 寫 200-400 字段落。
   - publish `handoff_ready {paragraph, structured}`。
5. **前端**：API 回 202 → 收到 SSE `handoff_ready` → `setHandoff({paragraph})` + `setGeneratingHandoff(false)` → `HandoffConfirmModal` 顯示 paragraph 給 BU 確認（後續 S07）。

**設計重點**：BU 可以**不必走完 stage 5** 就早早選候選卡 — 只要候選清單已形成就觸發。如果一開始就有強訊號 BU 可以早早 handoff。

---

## S05 — AiNecessityWarningModal 三選一 `24_seq_modal_ai_necessity.mmd`

**User action**：BU 在 AI 必要性彈窗點 acknowledge / override / explain。

**逐步講解**

1. **前置**：score_candidates 已 publish `ai_necessity_warning` + patch `pending_ai_necessity_decision=True` 鎖住 graph，輸入框 disabled、agent 不搶話。
2. **BU 點選項**：FE `setAwaitingAgent(true)` + `setAiNecessityWarn(null)`（modal 立刻關，避免雙擊）→ `POST /sessions/{id}/ai-necessity/{kind}`（kind ∈ {acknowledge, override, explain}）→ API `_spawn(_ai_necessity_decision_bg(sid, kind))`，回 202。
3. **Service `_run_ai_necessity_decision`**（`session_service.py:616`，三個 endpoint 共用）：
   - `aget_state` → 用 `_find_top1_candidate`（`session_service.py:523`）拿 top1。
   - 防呆：top1 為 None 時直接 `aupdate_state {ai_necessity_warned=True, pending_ai_necessity_decision=False}` 結束。
   - 正常路徑（三段式）：
     1. **`_record_bu_option_choice`**（`session_service.py:548`）：寫一個固定 label 進 history。`acknowledge` → 「我了解了，讓我繼續想想」；`override` → 「我有理由，還是想用 AI 試試看」；`explain` → 「想了解 {solution_class} 跟 AI 的差別」。`aupdate_state {history: history + [bu_trace]}` + publish `bu_turn_recorded`。
     2. **`_stream_agent_reply`**（`session_service.py:575`）：依 kind 選對應 prompt（`acknowledge_ai_necessity.j2` / `override_ai_necessity.j2` / `explain_solution_class.j2`），注入 top1 / pain_signals / last_bu_text；`get_llm(state.llm_model).chat_stream`，每個 chunk publish `agent_reply_delta`，前端 `setAwaitingAgent(false)` 解鎖；LLM 失敗時用 `fallback_text` 安全句兜底。最後 publish `agent_reply_done`。
     3. **Patch state**：`aupdate_state {history: history + [agent_trace], ai_necessity_warned=True, pending_ai_necessity_decision=False [+ bu_overrode_ai_necessity=True if override]}`。
4. **後續 reload**：useQuery 抓到 `warned=True && pending=False`，SSE replay 的 `ai_necessity_warning` 會被 cache-read guard skip，不重彈。

**第四選項「換個角度重新發想」**：走 `reset_explore`（詳 S11 Path A），不走這條 endpoint。

---

## S06 — Stage5StuckModal 三選一 `25_seq_modal_stage5_stuck.mmd`

**User action**：BU 在 stage 5 卡關彈窗點選項。三個選項中兩個走這個圖，第三個（換個角度重新發想）見 S11。

**逐步講解**

1. **前置**：`converge_check` 已 publish `stage5_stuck` + patch `pending_stage5_decision=True` 鎖住 graph。

**選項 1：再聊一下我想想（dismiss）**

2. BU 點「再聊一下」→ FE `setAwaitingAgent(true)` + `setStage5Stuck(null)` → `POST /sessions/{id}/stage5/dismiss` → API `_spawn(_stage5_dismiss_bg(sid))`，回 202。
3. Service `dismiss_stage5_stuck`（`session_service.py:752`）：
   - `aget_state` + 取 top3 candidates 給 prompt。
   - `_record_bu_option_choice` label = 「再聊一下，我想想」+ publish `bu_turn_recorded`。
   - render `stage5_keep_talking.j2`（注入 top3_candidates / pain_signals / last_bu_text / stage_5_rounds）。
   - `_stream_agent_reply`：80-150 字承接「換切角」內容。
   - `aupdate_state {history: history+[agent_trace], stage_5_stuck_acked=True, pending_stage5_decision=False}`。

**選項 2：先用 #N 試試 BRD（quick_handoff）**

4. BU 點「先用 #N 試試 BRD」→ FE `setStage5Stuck(null)` + `setSelectedRank(N)` + `setGeneratingHandoff(true)` → `POST /sessions/{id}/stage5/quick-handoff {rank: N}`。
5. Service `quick_handoff`（`session_service.py:822`）：
   - `_record_bu_option_choice` label = 「先用 #N 試試 BRD」+ publish `bu_turn_recorded`。
   - `aupdate_state {selected_candidate=N, ready_to_handoff=True, stage_5_stuck_acked=True, pending_stage5_decision=False}`。
   - **不 stream agent reply**，直接 `ainvoke({})` → `entry_router` 看 `ready_to_handoff` → `emit_dual_output` 組 structured JSON + LLM 寫 paragraph → publish `handoff_ready`。
   - 前端 `setHandoff({paragraph})` → 跳 HandoffConfirmModal（見 S07）。

6. **Reload 防呆**：useQuery 看到 `acked=True && pending=False` → SSE replay 的 `stage5_stuck` 被 skip。

---

## S07 — HandoffConfirmModal 兩選一 `26_seq_modal_handoff.mmd`

**User action**：BU 在 `emit_dual_output` 後彈出的 HandoffConfirmModal 點選項。

**逐步講解**

**前置**：`emit_dual_output` 已 publish `handoff_ready`，FE `setHandoff({paragraph})` 顯示 200-400 字段落描述。

**選項 1：進入 Consult mode**

1. BU 點「進入 Consult mode」 → `POST /sessions/{id}/handoff/confirm`。
2. Service `confirm_handoff`（`session_service.py:157`）：
   - `aupdate_state {mode: 'consult_step1'}` + publish `mode_changed {from:'explore', to:'consult_step1'}`。
   - `ainvoke({})` 推進 graph。
3. **Consult subgraph entry**（`subgraph.py:42`）：`brd_outline` 空 → `load_template`。
   - `load_template_node`（`consult/nodes.py:127`）：讀 `templates/brd/{bu}_{type}.yaml`，fallback `default.yaml`。
   - **同 super-step 連到 `auto_fill_outline`**（`consult/nodes.py:167`）：LLM structured `auto_fill_outline.j2` → `SectionDraftListOutput` → publish `outline_ready {sections}`。
   - **同 super-step 設 `mode='consult_step2'` + `current_section_idx`，再連到 `section_loop`**：`section_question.j2` LLM stream 第一道訪談題，publish `agent_reply_delta×N` + `agent_reply_done {section_id}`。
4. 前端 SSE 收 `outline_ready` → 渲染大綱樹；收 `mode_changed` → refetch session；收 `agent_reply_delta` → 對話區累加。最後 `setHandoff(null)` + UI 換成 `ConsultFullscreenLayout`。

**選項 2：再討論一下**

5. BU 點「再討論一下」 → `POST /sessions/{id}/handoff/dismiss`。
6. Service `dismiss_handoff`（`session_service.py:194`）：`aupdate_state {ready_to_handoff: False}`；不切 mode，不重啟 graph。
7. 前端 `setHandoff(null)` 留在 Explore，BU 可繼續對話或重選候選卡。

---

## S08 — Consult Step 2 章節 inline edit + Accept/Refine/Skip/Flag `27_seq_section_edit_action.mmd`

**User action**：BU 在某章 markdown editor 改文字、或點 Accept / Refine / Skip / Flag 任一按鈕。

**逐步講解**

**前置**：BU 在 Consult Step 2，agent 已對某章提問或 BU 已看到 draft。

**Action 1：Inline Edit**

1. BU 編輯某章 markdown → debounce 800ms → `PATCH /sessions/{id}/sections/{sid} {content}`。
2. Service `edit_section`（`session_service.py:305`）：
   - `aget_state` 拿 outline，把該 sid 章 `draft_content` 換新值，set `last_edit_by='bu'`。
   - `aupdate_state {brd_outline: 新 outline}`。
   - publish `section_updated {section_id, section}`。
3. API 回 200 SectionState；前端 `qc.invalidateQueries` refetch session。

**Action 2：Accept / Refine / Skip / Flag**

4. BU 點按鈕 → `POST /sessions/{id}/sections/{sid}/action {action, payload?}`。
5. Service `section_action`（`session_service.py:345`）：
   - `aget_state` 拿 outline。
   - 用 `status_map` 把 action 翻成 status：`accept→accepted` / `skip→skipped` / `flag→flagged_for_ba` / `refine→needs_round2`。不在這四個內 raise ValueError → API 400。
   - 找下一個 `needs_round2` 章節（next_idx），沒有就 None。
   - `aupdate_state {brd_outline: 更新後, current_section_idx: next_idx}` + publish `section_updated`。
   - 若 next_idx 非 None 還 publish `current_section_changed {section_id: 下一章}`，前端 `SectionInlineHeader` 立刻跳下一章（不必等 LLM 出題）。
   - `ainvoke({})` 推進 graph：有 `needs_round2` → `section_loop` 對下一章提問；都不在 → `quality_gate` 跑跨章衝突檢查。
   - graph 流程結尾 publish `agent_reply_delta×N` + `done`，或 `conflict_detected`。

---

## S09 — 點 strip 切章 + RevisitSection 防呆 `28_seq_select_section.mmd`

**User action**：BU 在 ConsultFullscreenLayout 的 strip 點某章切過去。

**逐步講解**

1. BU 點某章 strip → 前端 `handleSelect` 偵測該章 status。
2. **status ∈ {accepted, skipped, flagged_for_ba}** → 開 `RevisitSectionConfirmModal` 防呆（提示「會 reset 為 needs_round2 並重新訪談」），**不先切 `localSelectedId`**（避免 BU 取消時 UI 已跳掉）。
   - 點「取消」→ `setRevisitTarget(null)`、保持原章顯示。
   - 點「確認」→ 進下一步。
3. **status='placeholder'** → 前端守門：不發 select_section 請求（backend 也會 raise ValueError 回 400 兜底）。
4. **其他狀態（含確認 RevisitSection）**：
   - FE `setLocalSelectedId(sectionId)` + `setAwaitingAgent(true)` → `POST /sessions/{id}/sections/{sid}/select`。
5. Service `select_section`（`session_service.py:419`）：
   - `aget_state` → outline。
   - 該章 status='placeholder' → 400；找不到 sid → 404。
   - 該章 status != `needs_round2` → 把該章 reset 為 `needs_round2` + publish `section_updated`。
   - `aupdate_state {current_section_idx: idx, brd_outline: new_outline}` + publish `current_section_changed {section_id}`。前端 `SectionInlineHeader` 立刻同步顯示。
   - `ainvoke({})` 推進 graph → `section_loop` 對該章重新提問（`section_question.j2` LLM stream），publish `agent_reply_delta×N {section_id}` + `agent_reply_done {section_id}`。
6. API 回 202；前端 `qc.invalidateQueries`。

**設計重點**：RevisitSection 的雙層防呆（前端 modal + backend ValueError）— 即使前端被繞過去，backend 也會擋掉 placeholder。

---

## S10 — 送 BA `29_seq_submit_ba.mmd`

**User action**：BU 在 BrdLivePreview 點「送 BA」。

**逐步講解**

1. BU 點「送 BA review」 → 前端 confirm dialog（「送出後就無法再修改 BRD」）→ BU 確認。
2. FE → API `POST /sessions/{id}/submit`。
3. Service `submit_session`（`session_service.py:477`）：
   - `aupdate_state {mode: 'submit'}`。
   - `ainvoke({})` → `entry_router` 看 `mode='submit'` → `build_deliverables`（`consult/nodes.py:552`）。
4. **`build_deliverables`** 三件事：
   - **BRD markdown**：從 outline 拼整份 markdown（章節順序 + draft_content）。
   - **summary.json**：trace（dialogue history） + selected candidate + ai_necessity_triage（含 solution_class、selected_ai_necessity、selected_rationale、bu_overrode）。
   - **flag_for_ba_review**：所有 status=flagged_for_ba 的章節清單（給 BA 接手時看哪裡需要重點審）。
   - publish `deliverables_ready`（`consult/nodes.py:596`）。
5. **DB 寫入**：
   - `SELECT * FROM deliverables WHERE session_id=...`。已存在 → UPDATE 套新 payload；不存在 → INSERT。
   - `UPDATE sessions SET mode='done', status='done'`。
6. API 回 200 `{brd_doc_ref, summary_json, flag_for_ba_review}`。
7. 前端 `router.push('/sessions/[id]/done')` → 完成畫面顯示 summary + BRD 連結 + BA handle。

---

## S11 — Reset Explore + Cold Exit `30_seq_reset_and_cold.mmd`

**這張圖把兩個「例外路徑」合併**：Path A 是 BU 主動重新探索，Path B 是 graph 被動偵測 BU 沒興趣。

### Path A — `reset_explore`（C3 escape hatch）

**觸發點**：
- Consult Step 1 期間頂部按鈕「重新探索」。
- AiNecessityWarningModal 第四選項「換個角度重新發想」。
- Stage5StuckModal 第三選項「換個角度重新發想」。

**逐步講解**

1. BU 點任一觸發按鈕 → 前端 confirm dialog（不可逆提醒，且關閉現有 modal）→ BU 確認。
2. FE → API `POST /sessions/{id}/explore/reset`。
3. Service `reset_explore`（`session_service.py:853`）：
   - `aupdate_state` 一次清掉幾乎所有 explore state：`mode='explore'`、`stage=1`、`selected_candidate=None`、`ready_to_handoff=False`、`candidate_directions=[]`、`scored_candidates=[]`、`structured_json=None`、`paragraph_description=None`、`brd_outline=[]`、`history=[]`、`pain_signals=[]`、`pending_question=None`、`current_section_idx=None`。
   - **保留** `ai_necessity_warned` / `stage_5_stuck_acked`：同 session 不再彈相同警示，避免 reset 後又踩到一樣的 trigger。
   - `session.mode='explore', stage=1` + `db.commit()`。
   - publish `mode_changed {from:'consult_step1', to:'explore', reason:'user_reset'}` → 前端 refetch。
   - `ainvoke({})` 重啟 explore graph：history 空 → `discovery_loop` 出新第一題（LLM stream `explore_question.j2`） → publish `agent_reply_delta×N` + `done`。
4. API 回 202；前端 UI 切回 Explore layout，對話區只剩 agent 新第一題。

### Path B — Cold Exit（被動）

**觸發**：BU 連續 2 輪含否定關鍵字（converge_check 偵測）。

**逐步講解**

5. BU 送訊息（含「不太對」「沒想法」「no」等）→ `POST /sessions/{id}/messages`（同 S03 流程）。
6. graph 進到 `converge_check`（`nodes.py:431`）：歷史最後 2 個 BU turn 都含否定關鍵字 → 設 `mode='cold'` + publish `cold_exit {reason}`。前端 refetch session。
7. `after_converge` 看到 `mode=cold` → END（不產 agent reply）。
8. Service 端：`session.status='cold'` + `db.commit()` + publish `turn_done`（兜底解鎖）。
9. 前端 UI 顯示「建議離線找 BA」（ColdExitModal 或 banner），BU 可回 sessions list（圖中標 `[*]`）。

**設計差異**：Path A 是 BU 主動，graph state 全清；Path B 是 graph 被動偵測，state 不清，只把 mode 鎖在 cold。
