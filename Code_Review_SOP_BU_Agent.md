# BU Agent — 專案專屬 Code Review 補充

> 本檔是 [`Code_Review_SOP.md`](Code_Review_SOP.md)（通用 SOP）的**專案補充**。通用 SOP 講「人 vs 工具」、五大層面（Functionality / Architecture / Security & Performance / Readability / Tests）的審查框架；本檔列出 BU Agent 的**獨特陷阱**，補進那五大層面之上。
>
> 使用方式：reviewer 開 PR 時，先跑通用 SOP 的 CI 與五層面，再對照本檔對應段落確認 PR 沒踩本專案常見地雷。最後一節有 mini-checklist，PR 描述可直接貼。

---

## A. LangGraph state & subgraph

LangGraph 的 PostgresSaver checkpoint + 多 subgraph routing 有幾個本專案踩過的雷。

- **State 欄位用 replace semantics，不要 `operator.add` reducer**
  - `app/graph/shared/state.py`：`history`、`pain_signals` 等 list 欄位需要 reducer 時，節點顯式 read-then-concat，不要在 schema 上掛 `Annotated[list, operator.add]`
  - 原因：PostgresSaver round-trip + Pydantic 反序列化下，某些版本 reducer 會 double-add 造成翻倍
- **`after_converge` 七分支的優先序不可隨意調整**
  - `app/graph/explore/subgraph.py`：前兩個分支 `pending_ai_necessity_decision` / `pending_stage5_decision` 必須最先 check，看到 flag 直接 END，不再產 agent 回覆
  - 新增分支時：先想清楚是發生在彈窗前還後，再決定插在哪
- **新 graph node 必須 JSON 可序列化**
  - 寫進 state 的物件要能 `model_dump()` 或 plain dict；裡面不要塞 LLM client、SQLAlchemy session、檔案 handle
  - PostgresSaver checkpoint 反序列化失敗會讓 session 整個壞掉，且難復原
- **改 candidate / pain_signal 結構要追下游**
  - `cluster_pain_points` / `score_candidates` / `emit_dual_output` 三者結構耦合很緊
  - 多加欄位時：(1) prompt 模板有沒有用到、(2) `dual_output` JSON schema 有沒有對應、(3) 前端候選卡片有沒有顯示、(4) DB checkpoint 既有 row 的 schema 兼容性

## B. 多 LLM 後端（M4）

- **新增模型 prefix → 同步更新 `get_llm` 路由**
  - `app/graph/shared/llm.py` 用 model id 前綴決定走哪個 backend；新模型（例如 `claude-*`）要加 `_AnthropicBackend` + 路由規則 + cache key
  - cache key 是 `(kind, model)` tuple，不要漏 kind 否則跨後端互蓋
- **`models_catalog` 改邏輯時必查三件事**
  - 5 分鐘 in-memory cache（dev 改 key 後要重啟 backend 才生效）
  - 任一供應商失敗仍要回另一邊的清單，不能整個 raise
  - 全失敗 fallback 到 `.env` `ALLOWED_MODELS` 白名單
- **新 prompt 模板要考慮 OpenAI vs Gemini 風格差**
  - `app/graph/*/prompts/*.j2`：兩家對「角色」、system message、JSON output 的接受度不同
  - 寫完跑 `GET /health/llm?model=gpt-4o-mini` 與 `?model=gemini-2.5-pro` 各驗一次
- **節點呼叫 LLM 走 session 綁定模型**
  - 不要在節點裡寫死 `get_llm("gpt-4o-mini")`，要 `get_llm(state.llm_model)`
  - 整段 BRD 草擬用同一顆 LLM 是刻意決定（避免風格漂移）
- **`.env` 改了 → docker container 必須 recreate**
  - `docker compose restart backend` **不會**重讀 `.env`；要 `docker compose up -d backend` 才會（這個踩過好幾次）

## C. SSE / streaming

- **新增 SSE event type 要動三個地方**
  1. `app/services/sse_bus.py` 的 payload schema
  2. `frontend/src/lib/sse.ts` 的 handler 與 type
  3. Ring buffer replay 的防呆（reload 後 react-query cache 要能比對出「已處理過」）
- **彈窗（modal）一律走 deferred-reply pattern**
  - 後端：在 graph 內偵測到觸發條件 → 設 `pending_*_decision=True` → routing 看到 flag END
  - 前端：BU 點選項 → 對應 endpoint record BU 選項標籤到 history → 發 `bu_turn_recorded` SSE → backend 才開始 stream agent reply → clear flag
  - 三個現有彈窗（HandoffConfirm / AiNecessity / Stage5Stuck）都這樣，新加的也照辦
- **瀏覽器 SSE 直連 `:8000`，不要誤放到 `/api` proxy**
  - REST 走 Next.js 同源 `/api` proxy，但 SSE 是瀏覽器直接打 backend
  - 新增 streaming endpoint 要確認 EC2 Security Group 開了 8000

## D. DB migration

- **每個 migration 要寫 downgrade**
  - 即使是 PoC 階段；至少寫一個 `op.drop_column` 對應每個 add
- **新欄位要 nullable + default**
  - 既有 row 不會炸；之後再用一個資料 migration 補值
  - `sessions.llm_model` 就是這樣（migration 0002）
- **本地驗 upgrade + downgrade**
  - `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head`
  - 來回一次再 commit，避免別人 pull 壞掉

## E. 前端 build-time / runtime config

- **Next.js `output: 'standalone'` + rewrites destination 是 build-time bake**
  - `next.config.mjs` 的 `rewrites()` destination 在 build 階段就被序列化進 `.next/routes-manifest.json` 與 `server.js`
  - 改了 destination 或 backend internal URL：要在 `frontend/Dockerfile` builder stage 用 `ARG`/`ENV` 注入，**不能只靠 docker-compose 的 runtime env**
  - 這個踩過 — 詳見 README.md「⚠️ 改 backend 內部連線方式時要 rebuild frontend image」段
- **`NEXT_PUBLIC_*` 是 build-time 注入到 client bundle**
  - 改 `NEXT_PUBLIC_*` 也要 rebuild image 才生效
  - 想 runtime 切換的東西（例如 EC2 IP 變動下的 SSE 目標）→ 走 `window.location` 推導，不要用 `NEXT_PUBLIC_*`
- **REST 走同源 proxy、SSE 直連 backend**
  - 新增 endpoint：先想清楚走哪條路，再決定要不要動 `next.config.mjs`

## F. 文件同步

每個 PR 改 code 時自問：

- 改 endpoint → [`Plan_BU_Agent/bu_agent_technical_design.md`](Plan_BU_Agent/bu_agent_technical_design.md) §3.7 同步？
- 改 graph routing 或彈窗邏輯 → [`Plan_BU_Agent/agent_dialog_logic.md`](Plan_BU_Agent/agent_dialog_logic.md) 同步？
- 新增 prompt → [`Plan_BU_Agent/agent_prompting_rules.md`](Plan_BU_Agent/agent_prompting_rules.md) 列出？
- 改 `.env.example` → [`README.md`](README.md) §1 對應指引同步？
- 改 graph 拓樸或新 SSE 事件 → [`Plan_BU_Agent/system_flow.md`](Plan_BU_Agent/system_flow.md) 對應 Mermaid 更新？

doc drift 比 code bug 還難發現，因為下個人會直接信任 doc。

---

## Mini-checklist（PR 描述可貼）

```
## BU Agent code review checklist
- [ ] 通用 SOP 的 CI 全綠（ruff / mypy / pytest / eslint / tsc）
- [ ] LangGraph state 改動：用 replace semantics、checkpoint 可序列化
- [ ] 改 LLM 路由 / prompt：兩家 backend 都驗過
- [ ] 新 SSE event：sse_bus + sse.ts + replay 防呆三處同步
- [ ] DB migration：upgrade + downgrade 雙向跑過、新欄位 nullable
- [ ] 動 next.config / 環境變數：判斷 build-time vs runtime、必要時 rebuild image
- [ ] 對應的 Plan_BU_Agent/*.md 已同步
- [ ] `.env` 沒被誤 commit
```
