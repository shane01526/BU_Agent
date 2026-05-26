# BU Agent — 前端平台選項比較（GPTs / Slack / 自建前端）

> 版本：v0.2
> 撰寫日期：2026-05-12
> 依據來源：`BU_Agent/Plan_bu_agent/bu_agent_overview.md` v0.3、`bu_agent_user_stories_and_flow.md` v0.1
> 目的：針對三個可能的前端配置方式，逐項分析使用者體驗、API 設計、對話 threads 設計等面向，作為前端平台選型決策的參考文件
> 備註：overview v0.3 §1.1 已否決 Slack、§1.2 已否決 GPTs，本文把兩者作為「假設可選」情境重新檢討，呈現各自的設計壓力與取捨

> **Last updated 2026-05-25** — 同步至 code 現況。本次主要變更：
> - 新增 §3.5「LLM provider 選擇 UX」(自建前端優勢之一)：模型選單放新建 session 頁、按 provider 分組、缺 key disabled、session-level 綁定
>
> **v0.2 修訂**（2026-05-12 同步 overview v0.3 放寬內網假設）：
> - GPTs 的否決順位調整：**UX deal-breaker（雙欄 layout 不可行）改為第一理由**；資料離境 / 合規調為次要
> - 「自建前端」小節的「合規：內網」論點改寫為「cloud / on-prem 兩種拓撲皆可支援，cloud 須通過個案 review」
> - §4 對照總表「合規」列相應調整

---

## 目錄

- [1. 用 GPTs（ChatGPT Custom GPTs）](#1-用-gptschatgpt-custom-gpts)
- [2. 用 Slack](#2-用-slack)
- [3. 自建前端（overview v0.2 當前選擇）](#3-自建前端overview-v02-當前選擇)
- [4. 三者對照總表](#4-三者對照總表)
- [5. 結論與建議](#5-結論與建議)

---

## 1. 用 GPTs（ChatGPT Custom GPTs）

### 1.1 使用者體驗

- **進入點**：BU 在 chat.openai.com 側邊欄找 GPT；等同 overview §A1「單一入口」，但無 Sessions 列表頁 → 跨日 Resume（A3）退化為「靠 ChatGPT 自己的歷史對話」，session 命名混亂。
- **Mode 切換**：原本設計的 **Explore / Consult 兩 mode + progress bar + 工作區換版面**（§3.2 Step 4、§10.1）整個做不到。GPTs 只有單一對話流，**mode 切換只能用 system prompt 內部狀態機**，BU 看到的是「agent 自己宣布進 Consult 了」這種黑盒感。
- **雙欄 layout 全失效**：§10 左對話右工作區、候選卡片 heatmap、BRD 大綱樹、live 預覽、inline edit 這些 Epic 全部不成立。只能退回「對話框印 markdown 表格 / 樹狀 bullet」。Story **B2 / D2 / E3 / E4 實質作廢**。
- **BRD 編輯**：GPTs 沒有 canvas 權限控制(即使用 Canvas 也是 OpenAI 託管)→ BU 要 inline edit 只能 copy BRD 出去 Word 改完再貼回來，違反 overview §3.2 Step 6。
- **交付**：只能靠 GPT Action 打回 Cathay 內網 webhook;BU 端無「送 BA」按鈕可視化(F1 退化為「BU 打字說『送出』」)。

### 1.2 API 設計

- **所有 backend 變成 OpenAI Actions（OpenAPI 3.1）**：每個 action 要公開一個 HTTPS endpoint 給 OpenAI 呼叫。
  - `POST /sessions/start` — 建立 session、接開場 metadata
  - `POST /sessions/{id}/explore/turn` — 紀錄一輪對話、回候選卡片 JSON
  - `POST /sessions/{id}/handoff` — 觸發雙輸出產製
  - `POST /sessions/{id}/consult/fill` — 回 BRD 章節草稿
  - `POST /sessions/{id}/submit` — 送 BA
- **致命問題**：無論 backend 部署在 cloud 或 on-prem,只要採 GPTs,對話 context(BU 業務邏輯、險種代碼、潛在客戶資料)都會落在 OpenAI platform → 資料分級上仍是高風險,且 Actions callback 也需公網可達(即便 backend 已 cloud 化,仍等於把 context 複製一份出去);這層風險即使 overview v0.3 放寬內網限制也不會消失。
- **Streaming**：Actions 不支援 SSE 回 GPT（GPT 會等整個 HTTP 回應）→ Story G2（Streaming）做不到。
- **LangGraph 整合**：LangGraph 的 `interrupt()` 要改寫成「每輪都是 stateless HTTP 呼叫，state 全部靠 session_id 從 PostgresSaver 撈」。架構上可做，但把 LangGraph 的 HITL 優勢削掉一半。

### 1.3 對話 thread 設計

- **一個 GPT = 一條 ChatGPT conversation**，但 ChatGPT 不給你 conversation_id（未來才可能開放）→ **無法做 A3 Resume**。只能走「每開啟對話 GPT 先問『要開新諮詢還是接 session X？』→ 用 session_id 走 Action」這種彆扭方式。
- **conversation_trace（F3、機制 1）**：GPTs 本身的對話內容**你拿不到**(OpenAI 不 export 給 GPT creator)→ trace 只能在 Action 呼叫時 agent「自己重述 BU 剛剛講的話」再寫回 backend,資料會失真、也浪費 token。
- **Explore ↔ Consult 切換**：同一 thread 內,用 system prompt 的狀態機 + Action 回傳的 `mode` 欄位讓 GPT 切換 persona。切換點無 UI marker,BU 容易混淆。
- **Cold exit（B6）**：沒有 UI 可以顯示「建議離線找 BA」狀態條,只能讓 GPT 純文字說一次。

### 1.4 其他考量

- **合規**：相對於自建前端,GPTs 仍是三者中資料邊界最模糊的(OpenAI 為第三方 data processor)。雖然 overview v0.3 已把 UX 放在第一否決理由,但本項仍然是次要阻斷點 —— 除非拿到法遵書面核可 opt-out training 與清楚釐清 sub-processor,否則不應推入 prod。
- **開發成本**：看似最低(寫幾個 OpenAPI endpoint 就好),但要把雙輸出、trace、resume、quality gate 全部塞進對話裡、還要繞過 streaming 限制,**實際工時不會比另兩個方案省**。
- **BA Agent 延續**：BA 階段需要「對段落做 suggest / 對章節 diff」,GPTs 完全做不到 → Phase 2 會強迫再換平台一次。

---

## 2. 用 Slack

### 2.1 使用者體驗

- **進入點**：`/brd` slash 或 app mention。overview §A1 要求「不選 slash」→ 可以做到(單一 slash 進入),但要放棄舊架構的 `/brd-explore` `/brd-new` 雙入口。
- **雙欄 layout 不成立**：Slack thread 是單欄 → §10.1 split layout、§10.2 mode-aware 工作區、progress bar、BRD 大綱樹、live 預覽**全部要降級**。替代方案：
  - 候選卡片 → Block Kit section + fields（heatmap 用 emoji 方塊近似）
  - BRD 大綱 → 每章節一則訊息,狀態徽章用 emoji（✅ auto_filled、❓ needs_round2、⏸ placeholder）
  - live 預覽 → 每輪回答後,edit 該章節那則訊息(Slack 允許 bot edit own message)
  - inline edit（E3）→ 只能做 modal 彈窗編輯,無法「點章節就改」
- **Refine/Accept/Skip（E2）**：Block Kit button 可以做,這塊體驗反而還 OK。
- **Resume（A3）**：走 thread_ts ↔ session_id(這是舊 PRD 已驗證的做法,§7.1),但多 session 切換要靠 Slack 搜尋,不如 web sessions 列表直觀。
- **完成畫面（F5）**：Slack 無專屬 view,只能在 thread 底下補一則 summary 訊息 + BRD 連結。

### 2.2 API 設計

- **slack-bolt Python SDK + Slack OAuth**(舊架構已有,`oauth_tokens` 表保留 Slack 欄位)
- **後端觸發路徑**：Slack Events API（`app_mention` / `message.im`）→ FastAPI webhook → LangGraph 節點。
- **交互元件**：
  - `views_open` 開 modal 收開場 metadata（A2）
  - `chat_postMessage` + Block Kit 畫候選卡片、章節預覽
  - `chat_update` 做 live 預覽
  - Action handlers 接 Accept/Refine/Skip button
- **Streaming（G2）**：Slack 不支援 streaming 訊息 → agent reply 必須整段產完才送出,或 fake streaming(先送「思考中…」再 edit)。體驗降級明顯。
- **BRD 輸出**：內部 markdown 不合適在 Slack 預覽 → 必須同時存一份 Google Doc 給 BU 看章節層級 diff(舊 Diff_agent 的 Suggesting mode),等於**強制保留 Google Docs OAuth 與雙工具切換**,就是 overview §1.1 要避免的。

### 2.3 對話 thread 設計

- **每場諮詢 = 1 條 thread**：`thread_ts` 就是 session_id 的外部對應（舊架構已如此）。
- **Explore ↔ Consult 切換**：在同一 thread 內,agent 發一則「已進入 Consult mode」分隔訊息 + 新 Block Kit 版面；mode progress bar 退化為那則訊息本身。
- **`interrupt()` 點**：對應 BU 在 thread 內的下一則 reply 或某顆 button click。這塊 LangGraph 支援度最完整(舊 PRD 已驗證)。
- **conversation_trace**：Slack API 可以撈 thread 全部訊息 → trace 抓取相對乾淨,比 GPTs 好很多。
- **跨日 Resume**：點開舊 thread 就是 resume；但如果使用者另開新 thread,要靠 `/brd-resume` fallback 找回來 → 舊 PRD 的雙層 fallback 還是必要。
- **Cold exit（B6）**：可以明確發訊息「建議離線找 BA」＋把 session 狀態標 cold,體驗接近 web。

### 2.4 其他考量

- **合規**：Slack 是 Cathay 內部工具,資料邊界比 GPTs 清楚很多(企業租戶)。是三者中合規壓力最低的。
- **開發成本**：slack-bolt 與 Block Kit 對「章節密集 UI」本來就不擅長 → 工時會消耗在「怎麼把複雜 UI 壓進 Slack」而不是核心 agent 邏輯。
- **BA Agent 延續**：BA review 需要對章節做 suggesting,Slack 做不到 → 會被迫疊 Google Docs。這是舊架構痛點(§1.1 最後一段)。

---

## 3. 自建前端（overview v0.2 當前選擇）

### 3.1 使用者體驗

- **進入點**：單一 web app CTA（§A1、§10.1 頂部）。
- **雙欄 + progress bar**：§10.1 完整成立 → §B2 候選卡片 heatmap、§D2 大綱樹徽章、§E3 inline edit、§E4 live 預覽全部可做。
- **Mode 切換**：工作區換版面 + progress bar 推進,Story C1~C3 的 modal / 不可逆 / 重新探索按鈕都有對應 UI location。
- **完成畫面（F5）**：獨立路由 / view,可包交付物預覽與 BA handle。
- **最大風險**：前端工作量最高,且要自行解決「表格 / markdown 編輯器」UX（Slate.js / TipTap / ProseMirror 擇一）。

### 3.2 API 設計

- **REST**：
  - `POST /sessions` 建立 session（開場 metadata）
  - `GET /sessions?user_id=` Sessions 列表
  - `GET /sessions/{id}` 還原 state（含對話、工作區、current interrupt point）
  - `POST /sessions/{id}/messages` BU 一輪輸入
  - `PATCH /sessions/{id}/sections/{section_id}` inline edit
  - `POST /sessions/{id}/actions/accept|refine|skip`
  - `POST /sessions/{id}/handoff` 送 BA
  - `POST /sessions/{id}/explore/reset` 重新探索（C3）
- **Real-time（G2、§8 Q11）**：
  - **SSE** 走 server→client 單向 streaming,配 REST POST 做 client→server → 最簡單、適合 agent reply streaming
  - **WebSocket** 如果要做雙向 presence、BA 在另一端同時看(未來 BA Agent 共用前端時)會比較好
  - 建議：**Phase 1 用 SSE + REST,BA Agent 階段再視需要升 WebSocket**
- **認證（§8 Q10）**：Cathay AD / SSO → session cookie or JWT；API 每個呼叫驗 user_id
- **結構化輸出**：後端直接回 JSON(候選卡片、章節草稿、徽章狀態),不需在對話訊息內嵌 code block 再 parse
- **LangGraph 整合**：最原生 —— `interrupt()` 直接對應一個 SSE event type（`awaiting_user_reply` / `awaiting_button_click`）,前端據此切 UI 狀態
- **持久化**：PostgresSaver 就是 source of truth,REST `GET /sessions/{id}` 實作上就是讀 checkpoint

### 3.3 對話 thread 設計

- **Thread 粒度**：`user_id + session_id`,session_id 同時是 LangGraph `thread_id`（§10.4）→ 一場諮詢一條 thread。
- **Explore ↔ Consult 同 thread**：對話紀錄連續,mode 切換只是前端 UI event；對話 log 保留 `mode` 欄位區分段落。
- **Resume**：走 `GET /sessions/{id}` 還原;不需要舊 Slack 的雙層 fallback（§7.1）。
- **conversation_trace**：直接是後端自己的 DB,schema 自行設計,trace 欄位（§4.1.4 A）可以精準存：
  ```
  {turn_id, mode, role, raw_text, agent_reframe_flag, bu_choice_flag, linked_candidate_id}
  ```
- **Explore JSON + 段落雙輸出**：存 session 附屬欄位,Consult Step 1 直接撈（§5.1）。
- **Cold exit**：session.status 改為 `cold`,sessions 列表顯示專屬標籤。

### 3.4 其他考量

- **合規**：自有前端 + 自有 backend,資料邊界完全由 Cathay 控制。overview v0.3 採 cloud-first 部署（§10.6 方案 A）,須通過資料分級 / 法遵個案 review;若未過可退回 on-prem（方案 B）,application code 不變。相較 GPTs 永遠多一層第三方,自建前端在任一拓撲下都是三者中最乾淨的。
- **開發成本**：最高 —— 要處理登入、前端 build、web 元件庫、SSE 重連、inline edit 編輯器、BRD 預覽渲染。
- **BA Agent 延續（§8 Q13）**：同一前端加 BA view 最自然；review / suggesting UI 可與 BU Agent 共用元件。這是 overview 選擇自建的主因之一。

### 3.5 LLM provider 選擇 UX（[新增於 2026-05-25]）

自建前端讓 LLM provider 選擇成為可控的 UX 決策點，這是 GPTs / Slack 都做不到的：

- **模型選單放在新建 session 頁**：BU 在 `/sessions/new` 看下拉，按 provider 分組（OpenAI / Gemini）。模型清單來自 `GET /api/v1/models`（5 分鐘 cache），失敗時 fallback 至 `.env` 的 `ALLOWED_MODELS` 白名單。
- **Session-level 綁定**：模型在 session 建立當下寫入 `sessions.llm_model`，整個 session 全程使用，避免「中途換模型造成風格漂移」。BRD 章節改寫 / quality_gate / handoff paragraph 都用同一顆 LLM。
- **缺 key 自動 disabled**：`backends_available` 旗標讓沒設 OPENAI_API_KEY 的環境直接 disable 掉所有 OpenAI 選項，避免 BU 選了之後 LLM 失敗。
- **後端動態抓 + 過濾**：`models_catalog.list_chat_models()` 直接打 OpenAI / Gemini list-models API，過濾出可走 chat / 多模態語言任務的模型（排除 image / tts / transcribe / embedding / sora / imagen / veo 等）；OpenAI 帳號權限變動或新模型上架不需要改 code。
- **trade-off**：模型選單把 BU 暴露在「要懂模型差別」的負擔下；目前用 `DEFAULT_MODEL` 做 sane default 規避，BU 不選就走預設。

GPTs / Slack 平台模型由平台方決定，無法做這種 session-level 控制。

---

## 4. 三者對照總表

| 面向 | GPTs | Slack | 自建前端 |
| --- | --- | --- | --- |
| 合規 | ❌ 資料經第三方（OpenAI） | ⚠️ Slack 為第三方 + Google Docs 雙工具 | ✅ 邊界完全 Cathay 控制（cloud 或 on-prem 皆可） |
| 雙欄 layout / live 預覽 | ❌ | ⚠️ 勉強 | ✅ |
| Inline edit BRD 章節 | ❌ | ❌（只能 modal） | ✅ |
| Streaming agent reply | ❌ | ⚠️ fake streaming | ✅ SSE/WS |
| Sessions 列表 + Resume | ❌ 靠 ChatGPT 歷史 | ⚠️ 靠 thread 搜尋 + slash fallback | ✅ |
| conversation_trace 完整度 | ❌ 拿不到對話 | ✅ thread API | ✅ 自有 DB |
| LangGraph `interrupt()` 對應 | ⚠️ 退化為 stateless | ✅（舊已驗證） | ✅ 最原生 |
| BA Agent 階段共用 | ❌ 要換平台 | ❌ 要疊 Google Docs | ✅ 同 app 加 view |
| 前端開發成本 | 最低 | 中（Block Kit 拼裝） | 最高 |
| 後端改造幅度 | 中（重寫為 stateless Actions） | 最小（保留舊架構） | 中（新增 REST/SSE 層） |

---

## 5. 結論與建議

Overview v0.2 選自建前端是正確的 —— **只要你要的 UX 包含「左對話右 BRD 即時預覽 + 章節 inline edit」,GPTs 和 Slack 都做不到這件事**,而這正是 BRD 工作相對 free chat 的核心差異。

- **GPTs** 只適合做純諮詢對話的 PoC,而且 §1.2 合規已是 deal-breaker
- **Slack** 適合「輕量通知 + 按鈕」的 Diff_agent 式任務,不適合 BRD 主幹;且會被迫疊 Google Docs 雙工具
- **自建前端** 前期工程成本最高,但 UX 完整度、合規、BA Agent 延續性三個維度都最優,屬唯一可長期延伸的方案

### 後續延伸議題（如需再展開可另立文件）

- 自建前端的 SSE vs WebSocket 選型細節（§8 Q11）
- 自建前端的前端框架選型（§8 Q9：React / Next.js / Vue / Svelte）
- 若因人力 / 時程限制需先做 PoC,Slack 版降級設計可以壓到什麼程度
- BA Agent 階段是否共用同一前端（§8 Q13）與共用元件清單

---

*— End of Frontend Platform Comparison v0.2 —*
