# BU Agent — 技術設計文件 (Technical Design Document)

> 版本：v0.3
> 撰寫日期：2026-05-13
> 依據來源：
> - `Plan_bu_agent/bu_agent_overview.md` v0.3（整體規劃）
> - `Plan_bu_agent/bu_agent_user_stories_and_flow.md` v0.1（User Stories 與 Phase 展開）
> - `Plan_bu_agent/frontend_platform_comparison.md` v0.1（前端平台決策背景）
> 範圍：BU Agent 階段（Explore mode + Consult mode）的技術實作藍圖。BA Agent 僅在交接介面處點到為止
> 定位：主 PRD（待撰寫）的**工程對應版**。Overview 回答「要做什麼」，本文回答「怎麼做、用什麼做、檔案怎麼切、資料怎麼流」

> **Last updated 2026-05-25** — 同步至 code 現況。本次主要變更：
> - §1 Tech Stack：LLM 改為「Gemini 2.5 Pro / OpenAI GPT-4o / GPT-4.1（auto 路由）」
> - §3.3 GraphState：補 7 個彈窗相關欄位（4 ai_necessity + 3 stage5）
> - §3.5 LLM Integration：補 `_OpenAIBackend` / `get_llm(model)` 工廠 / `models_catalog` 動態清單
> - §3.7 REST API：補 `/api/v1/models`、`/ai-necessity/{acknowledge,override,explain}`、`/stage5/{dismiss,quick-handoff}`、`/health/llm?model=`
> - §3.8 SSE 事件：補 `ai_necessity_warning` / `stage5_stuck` / `bu_turn_recorded`
> - §3.6 Prompts：補 `acknowledge_ai_necessity.j2` / `override_ai_necessity.j2` / `explain_solution_class.j2` / `stage5_keep_talking.j2`
> - §5 DB schema：補 `sessions.llm_model` 欄位（migration `20260525_0002`）
> - §6 認證 / env：補 `OPENAI_API_KEY` / `OPENAI_MODEL` / `ALLOWED_MODELS` / `DEFAULT_MODEL` / `LLM_MODE=auto`

> **v0.2 修訂重點**（2026-05-12 跟 overview v0.3 放寬內網假設同步）：
> - §1 Tech stack：`Deployment` 欄改為 cloud 預設（GCP / AWS / Azure 擇一），on-prem 列為備援
> - §2 架構圖重畫：邊界從「Cathay 內網」改為「Cathay-controlled cloud VPC」；新增對外 SSO / Gemini API 流入流出箭頭
> - §6 認證：Cathay SSO (OIDC) 不再預設走內部 AD；加入 cloud IdP / Auth0 / Entra ID 選項
> - §7 部署：重寫環境表與拓撲，對齊 overview §10.6 的 A/B/C 三方案
> - §9 合規：改寫資料落地原則，區分 cloud-first / on-prem-备援 兩種情境的 DLP / PII 處理差異
> - §14 Open Questions：加入 Q15（部署拓撲）、Q16（LLM 呼叫路徑）兩條對映 overview v0.3 新增問題
> - 不改動：§3 後端 graph / schema / API、§4 前端 component / state、§5 DB schema、§10–12 測試 / 觀測 / 錯誤處理

---

## 目錄 (Table of Contents)

- [0. 使用說明](#0-使用說明)
- [1. 技術棧總覽 (Tech Stack Overview)](#1-技術棧總覽-tech-stack-overview)
- [2. 系統架構 (System Architecture)](#2-系統架構-system-architecture)
- [3. 後端設計 (Backend)](#3-後端設計-backend)
  - [3.1 Repo / 模組切分](#31-repo--模組切分)
  - [3.2 LangGraph Subgraph 設計](#32-langgraph-subgraph-設計)
  - [3.3 Graph State Schema](#33-graph-state-schema)
  - [3.4 雙輸出 Pydantic Schema](#34-雙輸出-pydantic-schema)
  - [3.5 LLM Integration（Gemini 2.5 Pro）](#35-llm-integrationgemini-25-pro)
  - [3.6 BRD 模板 (YAML config)](#36-brd-模板-yaml-config)
  - [3.7 REST API 表](#37-rest-api-表)
  - [3.8 SSE / Streaming 事件表](#38-sse--streaming-事件表)
  - [3.9 PostgresSaver 與 Checkpoint](#39-postgressaver-與-checkpoint)
- [4. 前端設計 (Frontend)](#4-前端設計-frontend)
  - [4.1 框架選型建議](#41-框架選型建議)
  - [4.2 路由 (Routing)](#42-路由-routing)
  - [4.3 Page / Component Tree](#43-page--component-tree)
  - [4.4 State Management](#44-state-management)
  - [4.5 SSE Client 設計](#45-sse-client-設計)
  - [4.6 BRD Editor 技術選型](#46-brd-editor-技術選型)
  - [4.7 UX 細節（對齊 User Stories）](#47-ux-細節對齊-user-stories)
- [5. 資料庫 Schema](#5-資料庫-schema)
- [6. 認證與授權](#6-認證與授權)
- [7. 部署與環境 (Deployment)](#7-部署與環境-deployment)
- [8. 非功能性需求 (Non-Functional Requirements)](#8-非功能性需求-non-functional-requirements)
- [9. 安全與合規 (Security & Compliance)](#9-安全與合規-security--compliance)
- [10. 測試策略](#10-測試策略)
- [11. 觀測性 (Observability)](#11-觀測性-observability)
- [12. 錯誤處理與降級 (Error Handling)](#12-錯誤處理與降級-error-handling)
- [13. 實作里程碑 (Implementation Milestones)](#13-實作里程碑-implementation-milestones)
- [14. Open Questions 對本文影響](#14-open-questions-對本文影響)

---

## 0. 使用說明

- 本文是**實作參考**，非需求規格。凡 overview §8 Open Questions 尚未決議的項目，本文採「**推薦方案 + 備選方案**」呈現，並在 §14 集中列出決議前應凍結的實作範圍
- 本文用詞約定：
  - **Backend**：Python FastAPI + LangGraph 服務
  - **Frontend**：自建 web app
  - **Session**：一場 BU 諮詢（Explore → Consult 全程），對應一筆 DB row 與一個 LangGraph `thread_id`
  - **Turn**：單一對話輪次（BU 一次輸入 + agent 一次輸出）
  - **Mode**：`explore` / `consult_step1` / `consult_step2` / `done` / `cold` 之一
- 寫實作 PR 時，建議先 link 到本文的具體段落（例：`impl §3.2 explore_subgraph`）再鋪陳變更

---

## 1. 技術棧總覽 (Tech Stack Overview)

| 層 | 技術 | 版本 / 備註 | 決策依據 |
| --- | --- | --- | --- |
| LLM | **多後端（auto 路由）**：Google Gemini 2.5 Pro / OpenAI GPT-4o / GPT-4o-mini / GPT-4.1 系列 / o1·o3·o4-mini reasoning 模型 | 由 `LLM_MODE` 控制：`auto`（依 model id 前綴自動分流）/ `gemini` / `openai` / `mock`；每個 session 在新建時綁定一個模型，全程使用，避免風格漂移 | overview §10.3、本文 §3.5 |
| Agent framework | LangGraph | 最新穩定版；採 subgraph 架構 | overview §10.3；舊架構延用 |
| Persistence | PostgresSaver (LangGraph) | PostgreSQL 15+ | overview §10.4 |
| Backend server | FastAPI | Python 3.11+ | 舊架構延用、與 LangGraph Python SDK 契合 |
| Real-time | Server-Sent Events (SSE) | Phase 1 首選；WebSocket 列為升級路徑 | frontend_comparison §3.2 建議 |
| Frontend framework | **Next.js (React)**（推薦）| App Router + TypeScript | §4.1 |
| Frontend editor | **TipTap**（推薦） | ProseMirror-based；支援 inline edit、mention、custom marks | §4.6 |
| Styling | Tailwind CSS + shadcn/ui | 與 Next.js 生態契合 | §4.1 |
| Auth | Cathay SSO (OIDC)；底層 IdP 為 AD / cloud IdP / Entra ID 之一 | overview §10.5 §8 Q10 | §6 |
| DB migration | Alembic | — | §5 |
| Testing (BE) | pytest + pytest-asyncio | — | §10 |
| Testing (FE) | Vitest + Playwright | — | §10 |
| Deployment | **Cloud 預設（GCP / AWS / Azure）**；Cathay private cloud / on-prem 為備援（待 §8 Q15 決議） | overview §10.6 | §7 |
| CI | GitLab CI（Cathay 內部）| 視內部基礎建設 | §7 |
| Observability | LangSmith（若允許）+ OpenTelemetry | — | §11 |

**推薦 vs 備選**
- Frontend framework：推薦 Next.js；備選 Vite + React SPA（若不需要 SSR）
- Real-time：推薦 SSE；備選 WebSocket（BA Agent 階段若需雙向協作再升級）
- BRD editor：推薦 TipTap；備選 Slate.js（較多 flexibility 但學習曲線高）

---

## 2. 系統架構 (System Architecture)

### 2.1 Component Diagram

```
                                                    ┌──────────────┐
                                                    │ Cathay SSO   │
                                                    │ (OIDC IdP)   │
                                                    └──────┬───────┘
                                                           │ OIDC
                                                           │
┌──────────────────────────────────────────────────────────┼─────────┐
│            Cathay-controlled Cloud VPC（預設部署拓撲）   │         │
│                                                          │         │
│  ┌──────────────┐         ┌─────────────────────────────▼───┐    │
│  │  Frontend    │◀──SSE──▶│   Backend (FastAPI)              │    │
│  │  Next.js     │◀──REST─▶│                                  │    │
│  │  (React +    │         │   ┌──────────────────────┐       │    │
│  │   TipTap)    │         │   │  LangGraph App       │       │    │
│  └──────┬───────┘         │   │   ├─ explore_subgraph│       │    │
│         ▲                 │   │   └─ consult_subgraph│       │    │
│         │                 │   └──────────┬───────────┘       │    │
│         │ HTTPS           │              │                   │    │
│         │                 │   ┌──────────▼───────────┐       │    │
│         │                 │   │  PostgresSaver       │       │    │
│         │                 │   │  (checkpoint)        │       │    │
│         │                 │   └──────────────────────┘       │    │
│         │                 └──────┬───────────────────────┬───┘    │
│         │                        │                       │        │
│         │                        ▼                       │        │
│         │            ┌────────────────────┐              │        │
│         │            │  PostgreSQL 15+    │              │        │
│         │            │  (managed / HA)    │              │        │
│         │            │  ├─ langgraph_*    │              │        │
│         │            │  ├─ sessions       │              │        │
│         │            │  └─ ...            │              │        │
│         │            └────────────────────┘              │        │
│         │                                                │        │
└─────────┼────────────────────────────────────────────────┼────────┘
          │                                                │
          │ (public internet, TLS)                         │ HTTPS
          │                                                ▼
   ┌──────┴───────┐                              ┌──────────────────┐
   │  BU 使用者    │                              │  Gemini 2.5 Pro  │
   │  (browser)   │                              │  (cloud API /    │
   └──────────────┘                              │   Vertex AI /    │
                                                  │   proxy，§Q16)   │
                                                  └──────────────────┘

備援拓撲（on-prem）：把整個 VPC 邊界換成 Cathay 內網 / private cloud；
SSO / Gemini 路徑改走 Cathay API gateway / DLP proxy。細節見 §7.2。
```

### 2.2 主要資料流

1. **BU 登入**：Frontend → AD/SSO（OIDC）→ 取 `user_id` → Backend `GET /sessions?user_id=`
2. **開場**：`POST /sessions`（開場 metadata）→ Backend 建 session + 啟 LangGraph thread → SSE 推第一題
3. **Explore 對話輪**：`POST /sessions/{id}/messages` → LangGraph `resume(interrupt_value)` → 更新 state、LLM 呼叫 → SSE 推 `candidate_updated` / `agent_reply` → Frontend 更新對話區與工作區
4. **Mode 切換**：Explore 終止條件達成 → Backend 產雙輸出 → SSE 推 `handoff_ready` → Frontend 彈 modal → BU 確認 → `POST /sessions/{id}/handoff/confirm` → LangGraph 進 consult_subgraph
5. **Consult Step 1**：auto；LLM 填章節 → SSE 推 `outline_ready` → Frontend 渲染 BRD 大綱樹
6. **Consult Step 2**：逐章節互動（對話區 + 工作區 inline edit）→ 每次決策走 `POST /sessions/{id}/sections/{sid}/action`
7. **送 BA**：`POST /sessions/{id}/handoff` → 後端產交付物 → 通知 BA → 前端切完成畫面

---

## 3. 後端設計 (Backend)

### 3.1 Repo / 模組切分

```
bu_agent/
├── app/
│   ├── main.py                         # FastAPI 入口
│   ├── api/
│   │   ├── v1/
│   │   │   ├── sessions.py             # REST endpoints
│   │   │   ├── messages.py
│   │   │   ├── sections.py
│   │   │   ├── handoff.py
│   │   │   └── sse.py                  # SSE event stream
│   │   └── deps.py                     # DI (auth, db, graph)
│   ├── auth/
│   │   ├── oidc.py                     # Cathay SSO integration
│   │   └── middleware.py
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── main_graph.py               # 父 graph；路由到 explore/consult
│   │   ├── explore/
│   │   │   ├── subgraph.py
│   │   │   ├── nodes.py                # discovery_loop / cluster_pain / score / converge
│   │   │   ├── question_bank.py        # 5 階段題庫
│   │   │   └── rubric.py               # 5 維度 rubric 評分
│   │   ├── consult/
│   │   │   ├── subgraph.py
│   │   │   ├── nodes.py                # load_template / auto_fill / section_loop / quality_gate
│   │   │   ├── template_loader.py
│   │   │   └── section_logic.py
│   │   └── shared/
│   │       ├── state.py                # GraphState Pydantic model
│   │       ├── llm.py                  # Gemini 2.5 Pro client
│   │       └── prompts/                # Jinja2 templates
│   ├── models/
│   │   ├── db.py                       # SQLAlchemy models
│   │   └── schemas.py                  # Pydantic API models
│   ├── services/
│   │   ├── session_service.py
│   │   ├── handoff_service.py          # 產 summary.json / trace / BRD export
│   │   └── notification_service.py     # in-app + email
│   ├── templates/
│   │   └── brd/                        # YAML 模板（依 BU / project_type）
│   │       ├── 產險_分類.yaml
│   │       ├── 壽險_分類.yaml
│   │       └── ...
│   └── core/
│       ├── config.py
│       ├── logging.py
│       └── db.py
├── migrations/                         # Alembic
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── pyproject.toml
└── docker-compose.yml
```

### 3.2 LangGraph Subgraph 設計

採父 graph + 兩個 subgraph 架構。父 graph 只做路由與 mode 狀態機，實際對話邏輯下放到 subgraph，與 overview §3 流程圖一致。

#### 3.2.1 父 Graph (`main_graph.py`)

```
        ┌──────────────┐
        │  entry       │
        └──────┬───────┘
               ▼
        ┌──────────────┐
        │  route_mode  │─── explore ──▶ explore_subgraph ──┐
        └──────────────┘                                     │
               ▲                                             │
               │                                             │
               │         consult_step1/2 ──▶ consult_subgraph
               │                                             │
               └────────── on resume / handoff ──────────────┘
```

- `route_mode` 讀 `state.mode`，決定派送哪個 subgraph
- Subgraph 完成後回父 graph；由 `route_mode` 再判斷是進下一個 mode 還是進 `END`

#### 3.2.2 Explore Subgraph (`explore/subgraph.py`)

沿用舊 `Explore_agent/explore_agent.md` v0.1 核心節點，改寫為新 state schema：

```
  START
    │
    ▼
  ┌──────────────────────┐
  │ discovery_loop       │◀──┐
  │ (題庫 1→5 階段分派)  │   │
  └───────┬──────────────┘   │ interrupt() → BU reply
          │                   │
          ▼                   │
  ┌──────────────────────┐   │
  │ extract_signals      │   │
  │ (pain + context)     │   │
  └───────┬──────────────┘   │
          │                   │
          ▼                   │
  ┌──────────────────────┐   │
  │ cluster_pain_points  │   │
  └───────┬──────────────┘   │
          │                   │
          ▼                   │
  ┌──────────────────────┐   │
  │ score_candidates     │   │
  │ (5 維度 rubric)      │   │
  └───────┬──────────────┘   │
          │                   │
          ▼                   │
  ┌──────────────────────┐   │
  │ converge_check       │───┘ 未達終止條件回 discovery_loop
  └───────┬──────────────┘
          │ 終止條件達成
          ▼
  ┌──────────────────────┐
  │ emit_dual_output     │  → (A) 結構化 JSON (B) 段落描述
  └───────┬──────────────┘
          │
          ▼
  ┌──────────────────────┐
  │ handoff_confirm      │ interrupt() → BU 在 modal 決定
  │                      │
  └───────┬──────────────┘
          │
          ▼
         END (回父 graph；mode→consult_step1)
```

**節點責任對照**（詳細邏輯在主 PRD / 舊 Explore PRD 定義；本文只列工程介面）：

| 節點 | 輸入 (state 欄位) | 輸出 (state mutation) | 是否 interrupt |
| --- | --- | --- | --- |
| `discovery_loop` | `stage`, `history` | 產問題 → `pending_question` | ✅ 等 BU reply |
| `extract_signals` | 最新 BU reply | append `pain_signals`, `context` | ❌ |
| `cluster_pain_points` | `pain_signals` | `candidate_directions` | ❌ |
| `score_candidates` | `candidate_directions` | `scored_candidates[]` | ❌ |
| `converge_check` | `scored_candidates`, `stage` | `stage++` 或 `ready_to_handoff=True` | ❌ |
| `emit_dual_output` | `scored_candidates`, `selected_candidate`, `trace` | `structured_json`, `paragraph_description` | ❌ |
| `handoff_confirm` | `paragraph_description` | 等 BU modal 選擇 | ✅ |

#### 3.2.3 Consult Subgraph (`consult/subgraph.py`)

```
  START
    │
    ▼
  ┌──────────────────────┐
  │ load_template        │  依 bu + project_type 載 YAML
  └───────┬──────────────┘
          │
          ▼
  ┌──────────────────────┐
  │ auto_fill_outline    │  LLM 填 auto_filled / 標 needs_round2
  └───────┬──────────────┘
          │
          ▼ mode → consult_step2
  ┌──────────────────────┐
  │ section_loop         │◀──┐
  │ (僅 needs_round2)    │   │ interrupt() → BU reply / action
  └───────┬──────────────┘   │
          │                   │
          ▼                   │
  ┌──────────────────────┐   │
  │ handle_action        │───┘ Accept / Refine / Skip / Flag
  └───────┬──────────────┘
          │ 所有 needs_round2 完成
          ▼
  ┌──────────────────────┐
  │ quality_gate         │
  └───────┬──────────────┘
          │ pass
          ▼
  ┌──────────────────────┐
  │ await_submit         │ interrupt() → BU 按「送 BA」
  └───────┬──────────────┘
          │
          ▼
  ┌──────────────────────┐
  │ build_deliverables   │ v1.0 BRD / summary.json / trace
  └───────┬──────────────┘
          │
          ▼
         END
```

| 節點 | 輸入 | 輸出 | 是否 interrupt |
| --- | --- | --- | --- |
| `load_template` | `state.bu`, `state.project_type` | `state.brd_outline`（章節骨架） | ❌ |
| `auto_fill_outline` | `structured_json`, `paragraph_description`, `brd_outline` | 每章節 status + draft | ❌ |
| `section_loop` | `brd_outline`, `current_section_idx` | `pending_question` | ✅ |
| `handle_action` | action type + payload | 章節狀態更新（accepted / refined / skipped / flagged） | ❌ |
| `quality_gate` | 全部章節 | `conflicts[]` 或 pass | ❌ |
| `await_submit` | — | — | ✅ |
| `build_deliverables` | 全 state | `summary_json`, `conversation_trace`, `brd_doc` | ❌ |

#### 3.2.4 Reducer 與 Concurrency

- `pain_signals` / `trace` 用 `Annotated[list, operator.add]` reducer 累加
- `candidate_directions` / `brd_outline` 為整體替換（非 append）
- 單 session 序列化處理；不支援同 session 並行 turn（前端需 disable 輸入直到 agent 回覆完）

### 3.3 Graph State Schema

```python
# graph/shared/state.py

from typing import Literal, Annotated
from operator import add
from pydantic import BaseModel, Field

class PainSignal(BaseModel):
    turn_id: int
    raw_text: str
    source: Literal["bu_explicit", "agent_reframe"]
    tags: list[str] = []

class CandidateDirection(BaseModel):
    rank: int
    direction: str
    process_target: str
    project_type: str
    score_5d: dict[str, int]        # rule_repeat / data_avail / reversibility / scale_roi / gap
    pain_signals: list[str]

class TraceEntry(BaseModel):
    turn_id: int
    mode: str
    role: Literal["agent", "bu", "system"]
    raw_text: str
    agent_reframe_flag: bool = False
    bu_choice_flag: bool = False
    linked_candidate_id: int | None = None
    timestamp: str

class SectionState(BaseModel):
    section_id: str
    title: str
    status: Literal["auto_filled", "needs_round2", "placeholder", "accepted", "skipped", "flagged_for_ba"]
    draft_content: str = ""
    last_edit_by: Literal["agent", "bu"] | None = None

class GraphState(BaseModel):
    # identifiers
    session_id: str
    user_id: str
    thread_id: str

    # mode state
    mode: Literal["explore", "consult_step1", "consult_step2", "done", "cold"]
    stage: int = 1                   # Explore 題庫階段 1-5

    # onboarding metadata
    bu: str
    sme_role: str
    raw_hint: str | None = None
    # 該 session 全程綁定的 LLM 模型 id（前端建 session 時挑一次，中途不換）
    # [已實作於 2026-05-25] 對應 sessions.llm_model 欄位（migration 0002）
    llm_model: str | None = None

    # explore state
    # [實作偏差於 2026-05-14] history / pain_signals 改用「replace semantics」
    # （非 operator.add reducer），原因見 §3.2.4 與 state.py 檔頭註解
    history: list[TraceEntry] = []
    pain_signals: list[PainSignal] = []
    candidate_directions: list[CandidateDirection] = []
    scored_candidates: list[CandidateDirection] = []
    selected_candidate: int | None = None
    ready_to_handoff: bool = False

    # [新增於 2026-05-25] Stage 5 卡關偵測（converge_check 觸發 stage5_stuck modal）
    # - stage_5_rounds：在 stage 5 已跑過幾輪 discovery_loop
    # - stage_5_stuck_acked：BU 已在 stuck modal 點過任一選項，本 session 不再彈
    # - pending_stage5_decision：modal 已發、等 BU 選項；期間 graph 不產 agent 回覆
    stage_5_rounds: int = 0
    stage_5_stuck_acked: bool = False
    pending_stage5_decision: bool = False

    # [新增於 2026-05-25] AI 必要性 triage（score_candidates 觸發 ai_necessity_warning）
    # - low_ai_necessity_streak：top1 候選連續被 LLM 標 ai_necessity=low 的次數
    # - ai_necessity_warned：已彈過 warning modal，本 session 不再彈
    # - bu_overrode_ai_necessity：BU 看過警示仍堅持用 AI（會寫進 BRD structured JSON）
    # - pending_ai_necessity_decision：modal 已發、等 BU 選項；期間 graph 不產 agent 回覆
    low_ai_necessity_streak: int = 0
    ai_necessity_warned: bool = False
    bu_overrode_ai_necessity: bool = False
    pending_ai_necessity_decision: bool = False

    # dual output
    structured_json: dict | None = None
    paragraph_description: str | None = None

    # consult state
    brd_outline: list[SectionState] = []
    current_section_idx: int | None = None
    conflicts: list[str] = []

    # deliverables (Phase 5)
    summary_json: dict | None = None
    conversation_trace: list[TraceEntry] = []
    brd_doc_ref: str | None = None

    # misc
    cold_exit_reason: str | None = None
```

### 3.4 雙輸出 Pydantic Schema

對應 overview §4.1.4 與 user stories C4。

```python
# models/schemas.py

from pydantic import BaseModel

class ExploreStructuredOutput(BaseModel):
    """(A) 給 Consult mode 機讀"""
    exploration_id: str
    bu: str
    sme_role: str
    candidates: list[CandidateDirection]
    selected_candidate: int
    predicted_consult_fields: dict       # bu / process_target / project_type / one_line_goal
    trace: list[TraceEntry]

class ExploreParagraphOutput(BaseModel):
    """(B) 給 BU 在交接 modal 確認"""
    text: str                            # 200-400 字
    highlights: list[dict]               # {text_span, type: "bu_explicit" | "agent_reframe"}
    char_count: int
```

> Schema 細節以 overview §8 Q5 決議為準；本文採 v0.2 草案作為實作起點。

### 3.5 LLM Integration（多後端：Gemini + OpenAI）

> [改寫於 2026-05-25] 原 §3.5 只設計 `GeminiClient`；現已實作多後端工廠 + 動態模型清單。

#### 3.5.1 多後端工廠 + 統一介面

```python
# graph/shared/llm.py

class LLMClient:
    """統一介面;真實後端由 _GeminiBackend / _OpenAIBackend 提供, mock 由 _MockBackend 提供。"""
    def __init__(self, kind: str, model: str): ...
    async def chat_stream(self, messages: list[dict]) -> AsyncIterator[str]: ...
    async def chat_structured(self, messages: list[dict], schema: type[BaseModel]) -> BaseModel: ...


def _resolve_backend(model: str | None) -> tuple[str, str]:
    """依 settings.llm_mode + model id 前綴決定 backend kind:
    - llm_mode=mock   → 全部 mock
    - llm_mode=gemini → 強制 Gemini
    - llm_mode=openai → 強制 OpenAI
    - llm_mode=auto   → 看 model id 前綴:
        gpt-* / o1 / o3 / chatgpt-* / chat-latest → openai
        gemini-*                                  → gemini
        其他                                       → mock
    對應 backend 的 API key 缺時 fallback 到 mock + warning。
    """

# 按 (kind, model) 快取,避免每次 get_llm 都重建 LangChain client
def get_llm(model: str | None = None) -> LLMClient: ...
```

- 三個 backend：`_GeminiBackend`（用 `langchain-google-genai`）、`_OpenAIBackend`（用 `langchain-openai`）、`_MockBackend`（離線罐頭）
- 每個 session 在新建時綁定一個 `llm_model`（前端 `/sessions/new` 模型選單），全程使用，所有節點呼叫 `get_llm(state.llm_model)`
- Retry / token budget 仍由各 LangChain client 內建處理；錯誤時 service handler 用 fallback_text 補齊 UI

#### 3.5.2 動態模型清單（`models_catalog.py`）

```python
# services/models_catalog.py

async def list_chat_models() -> dict:
    """回傳 {models, default, backends_available, source ('live'|'fallback'), failures}。

    - 同時打 OpenAI v1/models 與 Gemini v1beta/models API
    - 過濾出可走 chat / 多模態語言任務的模型(排除 image / tts / transcribe /
      embedding / moderation / sora / imagen / veo / lyria / robotics 等)
    - 5 分鐘 in-memory cache;某個供應商失敗只報 failures、其餘照給
    - 兩邊都失敗 → fallback 到 .env 的 ALLOWED_MODELS 白名單
    """
```

過濾規則（寫死在 `_OPENAI_EXCLUDE_SUBSTRINGS` / `_GEMINI_EXCLUDE_SUBSTRINGS`）：
- OpenAI 保留：`gpt-*`、`o1`、`o3`、`o4`、`chatgpt-*`、`chat-latest`；排除 `embedding` / `moderation` / `transcribe` / `tts` / `-image` / `-search` / `babbage` / `davinci` / `instruct` / `sora` / `deep-research` / `computer-use` / `realtime-translate` / `realtime-whisper`
- Gemini 保留：`gemini-*` 且支援 `generateContent`；排除 `embedding` / `tts` / `image` / `imagen` / `veo` / `lyria` / `robotics` / `native-audio` / `computer-use` / `deep-research` / `gemma` / `aqa` / `nano-banana`

#### 3.5.3 Prompt 組織

採 Jinja2 模板放在 `graph/shared/prompts/`（**所有 prompt 都已扁平化、不分 explore / consult 子目錄**）：

```
prompts/
├── system_explore.j2                # Explore agent persona
├── system_consult.j2                # Consult agent persona
├── _knowledge_card.j2               # BU 別 KC 共用片段
├── explore_question.j2              # discovery_loop 提問（含 meta 問題承接規則）
├── extract_signals.j2
├── score_candidates.j2              # 5 維度評分 structured output
├── emit_paragraph.j2                # 段落描述生成
├── acknowledge_and_guide.j2         # stage 4-5 承接 + 引導去看候選卡
├── auto_fill_outline.j2
├── section_question.j2
├── apply_section_answer.j2
├── quality_gate.j2
├── acknowledge_ai_necessity.j2      # [新增] BU 點「我了解了」時的 agent 回應
├── override_ai_necessity.j2         # [新增] BU 點「還是想試試 AI」時的 agent 回應
├── explain_solution_class.j2        # [新增] BU 點「想了解差別」時的 7 類 cheat sheet 比較
└── stage5_keep_talking.j2           # [新增] BU 點「再聊一下」時的換切角承接
```

- Prompt 版本化：檔頭加 `{# v1.0 2026-05-25 #}` 註解；變更時 bump
- Few-shot 與 grounding context（例：BU 別特有術語）由 KC YAML 提供

### 3.6 BRD 模板 (YAML config)

對應 overview §4.2.3 Step 1 第 1 點、§7.2「template_configs YAML 直接搬入」。

```yaml
# templates/brd/產險_分類.yaml
template_id: property_insurance_classification_v1
bu: 產險
project_type: 分類

sections:
  - id: sec_bg
    title: 需求背景
    owner: bu
    default_status: needs_round2
    extract_from_explore:
      - pain_signals
      - process_target
    questions:
      - 這件事目前是怎麼做的?誰做?多常做?
      - 目前痛點主要出現在哪個環節?

  - id: sec_req_analysis
    title: 需求分析
    owner: bu
    default_status: needs_round2
    ...

  - id: sec_exec
    title: 執行方式（不含 API 格式）
    owner: bu
    ...

  - id: sec_user_cases
    title: User Cases
    owner: bu
    ...

  - id: sec_exception
    title: 例外處理
    owner: bu
    ...

  - id: sec_ai_approach
    title: AI 方法建議
    owner: ai_team
    default_status: placeholder

  - id: sec_data_spec
    title: 資料規格
    owner: ai_team
    default_status: placeholder

  # ... 3 H1 + 1 H2 placeholder 依舊 Consult PRD §3.6 canonical list
```

- Loader 於 `load_template` 節點讀取；不在 code 內 hard-code 章節結構
- 若 BU/project_type 組合無對應模板，fallback 到 `default.yaml`

### 3.7 REST API 表

所有 endpoint 皆在 `api/v1/` 下，需 SSO 驗證（§6）。

| Method | Path | 功能 | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/sessions` | 列使用者 sessions | query: `status?` | `[SessionSummary]` |
| POST | `/sessions` | 建 session（Phase 0.3）| `{bu, sme_role, raw_hint?, llm_model?}` | `{session_id, mode}` |
| GET | `/sessions/{id}` | 取 session 完整 state（resume）| — | `SessionFullState`（含 5 個彈窗旗標：`ai_necessity_warned` / `pending_ai_necessity_decision` / `bu_overrode_ai_necessity` / `stage_5_stuck_acked` / `pending_stage5_decision`） |
| DELETE | `/sessions/{id}` | 刪 session（僅 soft delete）| — | 204 |
| POST | `/sessions/{id}/messages` | BU 一輪回覆（Explore / Consult Step 2）| `{text}` | 202 accepted；實際 agent reply 走 SSE |
| POST | `/sessions/{id}/handoff/confirm` | C1 BU 點「進入 Consult mode」| — | `{mode: "consult_step1"}` |
| POST | `/sessions/{id}/handoff/dismiss` | C1 BU 點「再討論一下」 | — | 202 |
| POST | `/sessions/{id}/explore/reset` | C3 重新探索 | `{reason?}` | `{mode: "explore"}` |
| GET | `/sessions/{id}/sections` | 取 BRD 大綱（Consult）| — | `[SectionState]` |
| PATCH | `/sessions/{id}/sections/{sid}` | E3 inline edit | `{content}` | `SectionState` |
| POST | `/sessions/{id}/sections/{sid}/action` | E2 Accept/Refine/Skip/Flag | `{action, payload?}` | `SectionState` |
| POST | `/sessions/{id}/sections/{sid}/select` | BU 主動切某章 → reset 為 needs_round2 + 重訪 | — | 202 |
| POST | `/sessions/{id}/candidates/select` | BU 在工作區點選候選卡 | `{rank}` | 202 |
| POST | `/sessions/{id}/submit` | F1「送 BA」| — | `{deliverables: {...}}` |
| GET | `/sessions/{id}/deliverables` | 取交付物（BA 端 / 匯出）| — | `Deliverables` |
| GET | `/sessions/{id}/events` | **SSE endpoint**（§3.8） | — | `text/event-stream` |
| **[新增 2026-05-25] AI 必要性彈窗 endpoints** | | | | |
| POST | `/sessions/{id}/ai-necessity/acknowledge` | BU 點「我了解了，讓我繼續想想」 | — | 202；agent 透過 SSE stream 帶脈絡承接 |
| POST | `/sessions/{id}/ai-necessity/override` | BU 點「我有理由，還是想用 AI 試試看」 | — | 202；agent 承接決定不勸退、邀補理由；另設 `bu_overrode_ai_necessity=True` |
| POST | `/sessions/{id}/ai-necessity/explain` | BU 點「想了解 [solution_class] 跟 AI 的差別」 | — | 202；agent stream 7 類 cheat sheet 比較 |
| **[新增 2026-05-25] Stage 5 卡關彈窗 endpoints** | | | | |
| POST | `/sessions/{id}/stage5/dismiss` | BU 點「再聊一下，我想想」 | — | 202；agent stream 換切角承接 |
| POST | `/sessions/{id}/stage5/quick-handoff` | BU 點「先用 #N 試試 BRD」 | `{rank}` | 202；不 stream agent，直接走 emit_dual_output 進 handoff |
| **[新增 2026-05-25] Misc** | | | | |
| GET | `/api/v1/models` | 前端模型選單來源（動態抓 OpenAI/Gemini list-models + 過濾 + 5min cache） | — | `{models[], default, backends_available, source ('live'\|'fallback'), failures[]}` |
| GET | `/health/llm` | 戳一次 LLM 驗連線 | query: `model?` | `{status, llm_mode, backend, model, sample}` |

#### 3.7.1 錯誤碼

| HTTP | Code | 意義 |
| --- | --- | --- |
| 400 | `INVALID_MODE_TRANSITION` | 例：consult 期間嘗試 POST messages 到 explore stage |
| 401 | `UNAUTHENTICATED` | AD token 無效 |
| 403 | `SESSION_NOT_OWNED` | 使用者嘗試存取他人 session |
| 404 | `SESSION_NOT_FOUND` / `SECTION_NOT_FOUND` | — |
| 409 | `SESSION_BUSY` | 該 session 正有 turn 處理中（concurrency guard） |
| 422 | `VALIDATION_ERROR` | Pydantic validation |
| 500 | `LLM_ERROR` / `GRAPH_ERROR` | 後端內部錯 |

### 3.8 SSE / Streaming 事件表

Endpoint：`GET /sessions/{id}/events`（per-session 長連線）。

| Event type | Payload | 觸發時機 | Frontend 反應 |
| --- | --- | --- | --- |
| `agent_reply_delta` | `{turn_id, text_delta}` | LLM streaming chunk | 對話區逐字渲染 |
| `agent_reply_done` | `{turn_id, full_text}` | LLM 完成 | 對話區 finalize，解 disabled |
| `bu_turn_recorded` | `{turn_id, text}` | backend 寫入 BU TraceEntry 後 | 對話區 append BU 訊息（彈窗選項標籤等） |
| `candidate_updated` | `{candidates: [...]}` | `score_candidates` 後 | 工作區候選卡片更新 |
| `pain_signal_added` | `{signal: PainSignal}` | `extract_signals` 後 | 工作區 timeline 加一筆 |
| `stage_changed` | `{stage: int}` | `converge_check` stage++ | progress bar 內部刻度 |
| `handoff_ready` | `{paragraph: str, structured: dict}` | `emit_dual_output` 完成 | 彈 modal（C1） |
| `mode_changed` | `{from, to}` | `route_mode` 切換 | progress bar 推進、工作區換版面 |
| `outline_ready` | `{sections: [...]}` | `auto_fill_outline` 完成 | 渲染大綱樹 |
| `section_updated` | `{section_id, section: SectionState}` | `handle_action` 或 LLM fill | 工作區對應章節更新 |
| `current_section_changed` | `{section_id}` | BU 主動切章 / accept 後跳下一章 | 對話區 SectionInlineHeader 同步 |
| `conflict_detected` | `{conflicts: [...]}` | `quality_gate` fail | 提示衝突點 |
| `cold_exit` | `{reason}` | B6 觸發 | 顯示「建議離線找 BA」畫面 |
| `stage5_stuck` **[新增 2026-05-25]** | `{rounds, candidates: top3}` | `converge_check` 在 stage 5 連 3 輪未選 candidate | 彈 Stage5StuckModal；並 set `pending_stage5_decision=True` 暫停 graph |
| `ai_necessity_warning` **[新增 2026-05-25]** | `{solution_class, rationale, top_candidate, candidates: top3}` | `score_candidates` 在 top1 ai_necessity=low 連續 ≥ 2 次 | 彈 AiNecessityWarningModal；並 set `pending_ai_necessity_decision=True` 暫停 graph |
| `turn_done` | `{mode, stage, history_len}` | `process_bu_message` 結束（兜底） | 解 `awaitingAgent`，輸入框可再輸入 |
| `deliverables_ready` | `{summary, trace, brd_url}` | `build_deliverables` 完成 | 切完成畫面（F5）|
| `agent_error` | `{message, retry: bool}` | LLM / graph 錯誤 | 對話區紅字錯誤卡 |
| `heartbeat` | `{ts}` | 每 25 秒 | 客戶端重連偵測 |

**實作重點**
- 用 `sse-starlette` 套件
- 每個 session 一條連線；多頁面開啟同 session 時後端 broadcast 到所有 active SSE streams（SessionBus）
- 斷線重連：client 帶 `Last-Event-ID` header，server 從事件 log 中補送
- **[新增 2026-05-25] SessionBus ring buffer 256 events / session**：reload 後 SSE 重連會 replay 全部歷史事件，前端 `ai_necessity_warning` / `stage5_stuck` handler 必須做防彈（見 §3.8.1）

#### 3.8.1 Deferred-reply 彈窗 pattern（[新增於 2026-05-25]）

`ai_necessity_warning` 與 `stage5_stuck` 兩個彈窗採用同一個 pattern：**graph publish 完彈窗 SSE event 後立刻停**，不對「觸發彈窗的那則 BU 訊息」做即時 agent 回覆。BU 在 modal 點選項後，後端對應 endpoint 才負責：

1. 寫一則 `role="bu"` 的 TraceEntry（內容是寫死的選項標籤字串），publish `bu_turn_recorded` 進對話區
2. Render 對應 prompt（含 top1 候選 / pain signals / 最後一則 BU 訊息）
3. LLM stream agent reply（quick_handoff 例外，直接走 emit_dual_output 不 stream）
4. 寫 agent TraceEntry + clear `pending_*_decision` flag

實作骨架：
- State：`pending_ai_necessity_decision` / `pending_stage5_decision`
- Subgraph：`after_converge` 看 flag 直接 `END`
- Service helpers：`_record_bu_option_choice` / `_stream_agent_reply` / `_run_ai_necessity_decision`（三段式共用主流程）

#### 3.8.2 SSE replay 防彈（[新增於 2026-05-25]）

reload 後 SessionBus 會 replay 過去 256 events，包括 `ai_necessity_warning` / `stage5_stuck`。前端**雙重保險**：

1. SSE handler 用 `qc.getQueryData<SessionFullState>` 同步讀 react-query cache，看到 `warned && !pending`（已決策）就略過
2. Cleanup `useEffect`：useQuery settle 後若旗標已 `acked && !pending`，強制關掉殘留 modal
3. 三個 ai handler + 兩個 stuck handler 點完 `qc.invalidateQueries` 縮短 stale 窗口

差異化：`pending=true` 表「上次離開時 BU 還沒選」，reload 後仍要彈讓他完成決策；`pending=false` 表「已選過」，replay 時略過。

### 3.9 PostgresSaver 與 Checkpoint

- 使用 LangGraph 官方 `PostgresSaver`
- `thread_id = session_id`
- Checkpoint 時機：
  - **每個 `interrupt()` 之前**（原生行為）
  - **Inline edit 完成後**（手動觸發 `graph.update_state()`）
  - **每章節 action 完成後**
  - 不做「每輪對話末自動 save」以外的時機，避免 Q6 尚未決議就過度實作
- Retention：保留所有 checkpoint；只在 `DELETE /sessions/{id}` 時 soft-delete
- Recovery：`GET /sessions/{id}` 走 `graph.get_state(thread_id)` 讀最新 checkpoint，組 `SessionFullState` 回前端（Phase R）

---

## 4. 前端設計 (Frontend)

### 4.1 框架選型建議

**推薦**：Next.js 14+ (App Router) + TypeScript + Tailwind CSS + shadcn/ui

理由：
- Cathay 內部 React 人力較多，學習成本最低
- App Router 路由天然契合 §4.2 多頁結構
- Server Components 可做 SSO session 驗證（認證 token 不外洩）
- shadcn/ui 提供 accessible primitives（Dialog / Tabs / Tooltip），省去自己搓 modal
- 與 TipTap、SSE、React Query 生態皆成熟

**備選**：Vite + React SPA
- 若不需要 SSR，部署更單純
- 但 SSO 整合要額外繞一層

**不推薦**：Vue / Svelte
- 團隊熟悉度與 Cathay 內部其他專案一致性考量

### 4.2 路由 (Routing)

```
/                               → 自動 redirect /sessions
/login                          → SSO 觸發頁
/sessions                       → Sessions 列表（Phase 0.2）
/sessions/new                   → 開場表單 modal（Phase 0.3）
/sessions/[id]                  → 主要工作介面（split layout）
/sessions/[id]/done             → 完成畫面（Phase 5 之後）
/admin                          → 後台（視需求；v1.0 可選）
```

### 4.3 Page / Component Tree

```
app/
├── layout.tsx                        # RootLayout（含 AuthProvider）
├── login/page.tsx
├── sessions/
│   ├── page.tsx                      # SessionsListPage
│   ├── new/page.tsx                  # OnboardingForm
│   └── [id]/
│       ├── layout.tsx                # SessionLayout（split + ProgressBar）
│       ├── page.tsx                  # SessionWorkspace
│       └── done/page.tsx             # DoneScreen
└── components/
    ├── layout/
    │   ├── TopBar.tsx
    │   ├── ProgressBar.tsx           # G1；3 節點
    │   └── SplitLayout.tsx
    ├── chat/
    │   ├── ChatPanel.tsx             # 左欄
    │   ├── MessageList.tsx
    │   ├── MessageItem.tsx           # agent / bu / system
    │   ├── StreamingMessage.tsx      # G2 SSE 逐字渲染
    │   ├── ChatInput.tsx             # 輸入框
    │   └── ActionButtons.tsx         # Accept / Refine / Skip / Flag
    ├── workspace/
    │   ├── WorkspacePanel.tsx        # 右欄 dispatcher (mode-aware)
    │   ├── explore/
    │   │   ├── CandidateCards.tsx    # B2
    │   │   ├── RubricHeatmap.tsx     # B2
    │   │   └── PainTimeline.tsx      # B3
    │   ├── consult/
    │   │   ├── OutlineTree.tsx       # D2
    │   │   ├── SectionNode.tsx       # + status badge
    │   │   ├── BrdLivePreview.tsx    # E4
    │   │   └── SectionEditor.tsx     # E3 TipTap
    │   └── done/
    │       └── CompletionSummary.tsx # F5
    ├── modal/
    │   ├── HandoffConfirmModal.tsx   # C1
    │   ├── ResetExploreModal.tsx     # C3
    │   └── ColdExitModal.tsx         # B6
    └── common/
        ├── ErrorBoundary.tsx
        └── Toast.tsx                  # F4 通知提示
```

### 4.4 State Management

| 狀態類型 | 工具 | 範圍 |
| --- | --- | --- |
| Server state (sessions / messages / sections) | **TanStack Query (React Query)** | 快取、自動重新驗證 |
| Local UI state（modal 開關、輸入框草稿）| `useState` / `useReducer` | Component 內 |
| SSE 事件分發 | 自訂 `useSessionEventBus` hook | Session 層級 |
| Cross-component global（目前 mode / progress）| `SessionContext` (React Context) | `/sessions/[id]` 子樹 |

> 不引入 Redux；shadcn/ui + Context 夠用。

### 4.5 SSE Client 設計

```ts
// hooks/useSessionEventBus.ts
function useSessionEventBus(sessionId: string) {
  // 1. 建 EventSource；自動加 Last-Event-ID 重連
  // 2. Parse 每個 event.data JSON
  // 3. 依 event type 分派到不同 handler（或 React Query cache 更新）
  // 4. 回傳 { connected, lastEventId }
}
```

- EventSource 建議包 `EventSourcePolyfill` 以支援 header（帶 Auth token）
- 斷線 > 5 秒 → Toast「連線中斷，正在重連…」；成功後隱藏
- 遇 `agent_reply_delta` 不走 React Query，直接 push 到 streaming message state，避免 re-render 過重

### 4.6 BRD Editor 技術選型

**推薦**：TipTap 2.x

- 原生支援 heading / list / table / mention / custom marks
- 可序列化為 HTML / JSON / markdown（三向可逆）
- 支援 collaborative editing extension（BA Agent 階段若需要即時共編）
- 可擴充 status badge、section anchor 等 custom node

**備選**：Slate.js
- 較多彈性但要自己搓 toolbar、normalize 規則
- 學習曲線較陡

**不推薦**：ContentEditable 硬刻
- 跨瀏覽器地雷多；章節 inline edit 需求下工時會爆

**資料流**
- Server 存 markdown（BRD 的 source of truth）
- Frontend load 時 markdown → TipTap JSON
- Inline edit save 時 TipTap JSON → markdown → `PATCH /sessions/{id}/sections/{sid}`
- `GET /sections` 回 markdown；前端 debounce（800ms）送 PATCH

### 4.7 UX 細節（對齊 User Stories）

| Story | Component / 行為 |
| --- | --- |
| A1 單一入口 | SessionsListPage 只有「開始新諮詢」CTA |
| A2 開場表單 | OnboardingForm（shadcn Form + zod） |
| A3 Resume | SessionsList 點選 → `/sessions/[id]` → `GET /sessions/{id}` 還原 |
| B2 候選卡片 | CandidateCards + RubricHeatmap（5 格 0–5 分） |
| B3 視覺標記 | MessageItem 對 reframe 段落用不同 badge 樣式 |
| B6 Cold exit | ColdExitModal，內文依 §3.3.6 template |
| C1 交接 modal | HandoffConfirmModal；2 按鈕 |
| C2 不可逆 | progress bar 推進後禁用「回 Explore」；只保留 C3 escape hatch |
| C3 重新探索 | OutlineTree 右上角按鈕 → ResetExploreModal |
| D2 章節徽章 | SectionNode 用 shadcn Badge；三種顏色 |
| E2 按鈕 | ActionButtons 在對話區 agent 當前章節 draft 訊息下方 |
| E3 inline edit | SectionEditor（TipTap）以 popover 或原位編輯 |
| E4 Live 預覽 | BrdLivePreview 接 `section_updated` SSE 事件 |
| E5 flag | ActionButtons 多一顆「標給 BA」 |
| E6 衝突提示 | Toast + 對話區紅字訊息 + 衝突章節 anchor scroll |
| F1 送 BA | BrdLivePreview 頂部 sticky CTA；未通過 gate 時 disabled |
| F5 完成畫面 | `/sessions/[id]/done` 獨立頁，顯示 summary / BRD 連結 / BA handle |
| G1 progress bar | ProgressBar in SessionLayout 頂部 |
| G2 streaming | StreamingMessage 配 `agent_reply_delta` |

---

## 5. 資料庫 Schema

PostgreSQL 15+，除 LangGraph 內建 checkpoint 表外，另設下列 application 表：

```sql
-- 使用者（對應 AD 帳號）
CREATE TABLE users (
    user_id TEXT PRIMARY KEY,             -- AD sAMAccountName 或 employee id
    display_name TEXT NOT NULL,
    email TEXT NOT NULL,
    bu TEXT,                              -- 預設所屬 BU
    role TEXT,                            -- 'bu_sme' | 'ba' | 'admin'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 諮詢 session（1:1 對應 LangGraph thread_id）
CREATE TABLE sessions (
    session_id UUID PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    bu TEXT NOT NULL,
    sme_role TEXT NOT NULL,
    raw_hint TEXT,
    llm_model TEXT,                       -- [新增於 2026-05-25] 該 session 全程綁定的 LLM 模型 id；migration 0002
    mode TEXT NOT NULL,                   -- explore / consult_step1 / consult_step2 / done / cold
    stage INT,
    status TEXT NOT NULL DEFAULT 'active', -- active / done / cold / abandoned
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_sessions_user_updated ON sessions(user_id, updated_at DESC);
CREATE INDEX idx_sessions_status ON sessions(status) WHERE deleted_at IS NULL;

-- 雙輸出（§4.1.4 A+B）快取表（也可直接放 GraphState，但查詢方便獨立）
CREATE TABLE exploration_outputs (
    session_id UUID PRIMARY KEY REFERENCES sessions(session_id),
    structured_json JSONB NOT NULL,
    paragraph_description TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- BRD 章節（取自 GraphState.brd_outline；獨立表便於直接 SQL 查）
CREATE TABLE brd_sections (
    section_id TEXT NOT NULL,
    session_id UUID NOT NULL REFERENCES sessions(session_id),
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    content_md TEXT NOT NULL DEFAULT '',
    last_edit_by TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (session_id, section_id)
);

-- 對話 trace（即使 GraphState 有，額外物化到此表供 BA 查）
CREATE TABLE conversation_traces (
    trace_id BIGSERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES sessions(session_id),
    turn_id INT NOT NULL,
    mode TEXT NOT NULL,
    role TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    agent_reframe_flag BOOL DEFAULT FALSE,
    bu_choice_flag BOOL DEFAULT FALSE,
    linked_candidate_id INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_trace_session_turn ON conversation_traces(session_id, turn_id);

-- 交付物（Phase 5）
CREATE TABLE deliverables (
    session_id UUID PRIMARY KEY REFERENCES sessions(session_id),
    brd_doc_ref TEXT NOT NULL,           -- markdown content or external URL (§8 Q4)
    summary_json JSONB NOT NULL,
    flag_for_ba_review JSONB NOT NULL,
    handed_off_at TIMESTAMPTZ,
    handed_off_to TEXT                    -- BA user_id
);

-- 通知 log
CREATE TABLE notifications (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID REFERENCES sessions(session_id),
    channel TEXT NOT NULL,                -- in_app / email / teams
    recipient TEXT NOT NULL,
    status TEXT NOT NULL,                 -- pending / sent / failed
    payload JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Migration 策略**
- 用 Alembic；每個 schema 變動一個 migration script
- 生產資料庫不允許 `DROP COLUMN`；改用 soft deprecate

---

## 6. 認證與授權

對應 overview §10.5 §8 Q10。

**推薦**：Cathay SSO（OIDC 標準）

IdP 底層可選：
- (a) Cathay 內部 AD（on-prem 部署時首選）
- (b) Cathay 企業雲端 IdP（Entra ID / Okta 類；cloud 部署時首選）
- (c) PoC 階段退為 Email + magic link（Q10 選項 c）

三者對應用程式碼幾乎無差異 —— 只換 OIDC discovery URL 與 client credentials。

**流程**
1. Frontend `/login` → redirect 至 SSO IdP
2. IdP 驗證完 callback 帶 `id_token` 回 Next.js API route
3. Backend 驗 id_token → 查或建 `users` row → 發 JWT access token（15 min） + refresh token（8h, HttpOnly cookie）
4. 後續 REST / SSE 請求帶 `Authorization: Bearer <access_token>`
5. SSE 斷線重連時以 refresh token 換新 access token

**授權**
- 每個 session endpoint 檢查 `user_id = token.user_id`（除 BA 視角，見 BA Agent 文件）
- Admin 角色可存取所有 session（僅觀察，不改動）
- Rate limit：每 user 每分鐘 60 次 API 呼叫（防呆，不是防攻擊）

**cloud 部署補強**
- CORS 白名單只允許正式 frontend domain
- CSRF：refresh cookie 帶 `SameSite=Strict`；state-changing REST 走 bearer + double-submit token
- Session revocation：JWT 黑名單存 Redis，logout 即刻失效

### 6.1 環境變數（[新增於 2026-05-25]）

對應 `backend/app/core/config.py` 的 `Settings`：

| 變數 | 用途 | 預設 / 範例 |
| --- | --- | --- |
| `DATABASE_URL` | Postgres connection string | `postgresql+psycopg://bu_agent:bu_agent@localhost:5432/bu_agent` |
| `LANGGRAPH_CHECKPOINT_URL` | LangGraph PostgresSaver 同 DB | 同上（不帶 `+psycopg`） |
| **LLM 多後端**（[新增 2026-05-25]） | | |
| `LLM_MODE` | `auto` / `gemini` / `openai` / `mock` | `auto` |
| `GEMINI_API_KEY` | Gemini key（缺 → fallback mock） | — |
| `GEMINI_MODEL` | Gemini 預設 model id | `gemini-2.5-pro` |
| `OPENAI_API_KEY` | OpenAI key（缺 → fallback mock） | — |
| `OPENAI_MODEL` | OpenAI 預設 model id | `gpt-4o-mini` |
| `ALLOWED_MODELS` | 前端模型選單白名單（fallback 用 CSV，動態抓失敗時生效） | `gpt-4o-mini,gpt-4o,gpt-4.1-mini,gemini-2.5-pro` |
| `DEFAULT_MODEL` | 新建 session 時若 BU 沒選的 fallback 模型 | `gpt-4o-mini` |
| **Auth** | | |
| `AUTH_MODE` | `mock` (PoC) / `sso` | `mock` |
| `OIDC_ISSUER` / `OIDC_CLIENT_ID` / `OIDC_CLIENT_SECRET` / `OIDC_REDIRECT_URI` | SSO mode 必填 | — |
| **App** | | |
| `APP_ENV` | `local` / `dev` / `staging` / `prod` | `local` |
| `LOG_LEVEL` | `INFO` / `DEBUG` | `INFO` |
| `CORS_ORIGINS` | 前端 domain 白名單（CSV） | `http://localhost:3000` |

`docker-compose.yml` 改用 `env_file: - .env`（取代過去的 `${VAR:-default}` 注入）以避開 Windows host shell env 蓋過 .env 的雷（例：開發者系統有舊 `OPENAI_API_KEY` 蓋過 .env 內新 key）。

---

## 7. 部署與環境 (Deployment)

> 對應 overview §10.6。v0.2 假設以 **cloud 為預設**；on-prem 列備援。兩者 application code 相同，差在 infra / network。

### 7.1 環境分層

| 環境 | 用途 | DB | LLM | 部署 |
| --- | --- | --- | --- | --- |
| local | 開發者機器 | Docker Compose Postgres | Gemini（個人 key）或 mock | docker-compose |
| dev | 團隊共用開發 | Cloud dev Postgres（managed） | Gemini dev quota | cloud |
| staging | UAT | Cloud staging Postgres（定期 reset） | Gemini prod quota | cloud |
| prod | 正式 | Cloud prod Postgres（HA / backup） | Gemini prod quota | cloud（或 on-prem 備援） |

### 7.2 部署拓撲

#### 方案 A — Cloud（預設）

- **Cloud provider**：GCP / AWS / Azure 擇一；**首選 GCP**（與 Gemini API 同供應商，latency 與 quota 管理最順）
- **Frontend**：Next.js standalone build → 託管 service（Cloud Run / Vercel / App Service）；或靜態資產走 CDN
- **Backend**：Docker container 多副本（≥2）於 Cloud Run / ECS / AKS；前置 managed load balancer
- **Database**：managed PostgreSQL（Cloud SQL / RDS / Azure DB）；啟 read replica 與 automated backup
- **Secrets**：provider 內建 secret manager（GCP Secret Manager / AWS Secrets Manager 等）；**禁止** 進 git
- **Network**：服務於同一 VPC；DB 僅開內部 subnet，不對 internet
- **TLS**：全站 HTTPS；managed cert
- **LLM**：Gemini API 直連（§Q16 a）或 Vertex AI（§Q16 b）

#### 方案 B — Cathay private cloud / on-prem（備援）

- 若 cloud review 未過，退回 Cathay 內部部署；與舊架構部署位置一致
- **Backend**：Docker container 多副本於 Cathay private cloud；前置 nginx / internal load balancer
- **Frontend**：Next.js 走 container 或 Nginx 靜態 + API proxy
- **Database**：Cathay 託管 PostgreSQL；streaming replica 可選
- **Secrets**：Cathay vault / k8s secrets
- **LLM**：走 Cathay API gateway / DLP proxy（§Q16 c）或 Cathay-controlled Vertex AI project（§Q16 b）
- **Auth**：強制內部 AD SSO

#### 方案 C — Hybrid（候選）

- 前端於 cloud（使用者體驗）+ 後端 + DB 於 on-prem（資料落地）
- 走 VPN / private link；複雜度最高，僅在 A 與 B 都有障礙時採用

### 7.3 CI/CD

- 單一 monorepo 或雙 repo 皆可；推薦 monorepo（`backend/` + `frontend/` + `shared/schemas/`）以共用 Pydantic ↔ TypeScript schema（用 `datamodel-code-generator` 生成）
- CI：lint → unit test → integration test → build image → push registry（雲端 registry 或 Cathay 內部 registry，依拓撲）
- CD：staging 自動；prod 需人工 approve
- Infra as Code：方案 A 用 Terraform；方案 B 用既有 Cathay k8s helm chart

---

## 8. 非功能性需求 (Non-Functional Requirements)

| 面向 | 目標 |
| --- | --- |
| 同時在線 BU | 初期 20；半年內擴至 100 |
| 每 session LLM 呼叫成本 | Explore < $0.5 / Consult < $2（預估，待實測） |
| 單 turn agent reply 延遲 | First token < 3s；full reply < 30s |
| SSE 連線穩定 | 自動重連；斷線 < 5s 使用者無感 |
| Resume 還原延遲 | < 2s |
| 瀏覽器支援 | Chrome / Edge 最近兩版；不支援 IE |
| 可及性 | WCAG 2.1 AA（鍵盤導航、螢幕閱讀器基本支援） |

---

## 9. 安全與合規 (Security & Compliance)

> v0.2：對映 overview v0.3 假設，區分 cloud-first 與 on-prem 備援兩種情境。

### 9.1 資料落地

- **Cloud-first（方案 A）**：
  - BU 對話、BRD 內容、trace 皆落在 Cathay-controlled cloud project（同一 VPC）
  - DB、物件儲存、LLM 推論皆指定落地區域（建議亞太就近區域 / 或符合 Cathay 政策的區域）
  - **上線前提**：必須通過 Cathay 資料分級 review（保單號、險種代碼、潛在客戶資料等欄位分級）與法遵審查；未通過前不得進 prod
- **On-prem 備援（方案 B）**：資料不出 Cathay 邊界；LLM 呼叫走內部 gateway / proxy
- **Hybrid（方案 C）**：以後端 / DB 所在環境為準

### 9.2 LLM 傳輸

- Cloud：Gemini 2.5 Pro 呼叫走 TLS；建議走 Vertex AI with CMEK（customer-managed encryption key），並確認 Google Enterprise agreement 狀態
- On-prem：走 Cathay API gateway / DLP proxy（Q16 c）或 Cathay-controlled Vertex AI project（Q16 b）
- 無論哪種拓撲：**禁止** 將 BU 對話送入模型供應商用於訓練（API-level opt-out 或合約條款確保）

### 9.3 PII / 敏感資料

- BU 在對話中可能提及客戶姓名、保單號；系統層面：
  - Prompt 前段加「避免記錄具體客戶 PII」指引
  - 寫輕量 detector 偵測身分證 / 信用卡號格式，hit 則紅字警告 BU 並拒絕落庫
- cloud 部署情境下額外加 DLP 掃描（GCP DLP / AWS Macie / Presidio 之一）於交付物產出前跑一次

### 9.4 Audit / Trace

- **Audit log**：所有 session CRUD、handoff、deliverables 匯出皆記 immutable log（append-only table + periodic 送 SIEM）
- **Trace 可見性**（§8 Q8 未決議前）：預設 BA 可看全部 trace；等決議後加 `private` 標記

### 9.5 資安 / 合規 review 檢核點（v0.2 新增）

在 prod 上線前須與資安 / 法遵確認（cloud-first 情境）：
- [ ] BU 對話資料分級與 cloud 區域是否匹配
- [ ] LLM 模型供應商合約（data retention、training opt-out、sub-processor 清單）
- [ ] VPC network ACL / firewall / egress 白名單
- [ ] SSO IdP 與 Cathay 帳號生命週期綁定（離職即收回）
- [ ] 備份保留週期與 GDPR-like 刪除權對應
- [ ] 事件通報路徑（incident response playbook）

---

## 10. 測試策略

| 層 | 範圍 | 工具 |
| --- | --- | --- |
| 單元測試 | 每個 graph node（mock LLM）、Pydantic schema、API route | pytest + pytest-asyncio（BE）、Vitest（FE） |
| 整合測試 | 完整 subgraph 跑流程（mock LLM 或 Gemini dev）、REST endpoint + DB | pytest + testcontainers |
| E2E | 模擬 BU 完整走 Phase 0→5 | Playwright（FE 驅動真後端 + Gemini dev）|
| 黃金路徑驗證 | Explore 5 題 → 雙輸出 → Consult Step 1 → Step 2 兩章節 → 送 BA | 手動 smoke + Playwright record |
| LLM 品質評估 | 題庫遵循率、雙輸出結構合規率、章節一致性 | 離線 batch；標註資料 |

**注意**
- 不 mock DB；整合測試用 testcontainers 起真 Postgres
- LLM 呼叫部分 mock、部分走真 dev quota 以抓 prompt regression

---

## 11. 觀測性 (Observability)

- **Logging**：structured JSON（session_id / turn_id / mode 為必備欄位）；Python 用 `structlog`、Next.js 用 `pino`
- **Tracing**：OpenTelemetry；每個 REST 呼叫一個 trace，SSE 事件為 span
- **LLM tracing**：若合規允許，啟 LangSmith；否則自建 `llm_calls` 表記 input/output/tokens/cost
- **Metrics**：
  - `bu_agent_session_created_total{bu,status}`
  - `bu_agent_turn_latency_seconds{mode,percentile}`
  - `bu_agent_llm_tokens_total{model,stage}`
  - `bu_agent_handoff_total{status}`（done / cold / abandoned）
- **Alert**：SSE 斷線率 > 5%、LLM 錯誤率 > 3%、session 平均超時

---

## 12. 錯誤處理與降級 (Error Handling)

| 場景 | 後端處理 | 前端表現 |
| --- | --- | --- |
| LLM timeout / 500 | 退避重試 3 次；失敗推 `agent_error` | 紅字「agent 暫時無法回應，請重試」；保留上輪輸入 |
| LLM 結構化輸出 schema 不合規 | 重試 1 次（修 prompt hint）；再失敗記 log 並用最小 fallback 回應 | 同上 |
| DB 寫失敗 | 不回 200；事務回滾 | Toast 錯誤，輸入保留 |
| SSE 斷線 | 客戶端自動重連 | Toast「連線中斷」；連上後自動消失 |
| Graph state corruption | 記 critical log；提供 admin reset session 機制 | 要求 BU 從 sessions 列表重開 |
| 用戶並發 turn（雙 tab）| 第二 tab 拒絕 `POST /messages` with 409 | 提示「另一視窗正在對話中」 |

> 遵循 CLAUDE 基本原則：不為不可能情境寫防禦 code；只在系統邊界（LLM、DB、SSE）做處理。

---

## 13. 實作里程碑 (Implementation Milestones)

建議以「最小可用 Explore → 打通 Consult → UX 打磨」三層推進，每層各有 exit criteria。

### M0 — 前置（1 週）

- 搭 monorepo（backend / frontend / shared）
- 設 CI / lint / pre-commit
- Docker Compose local 環境跑起來（空 FastAPI + 空 Next.js + Postgres）
- SSO 流程最小 POC（可用 mock IdP）

### M1 — Backend Skeleton（2 週）

- 資料庫 schema + Alembic migration 建立
- LangGraph 父 graph + 兩 subgraph 空殼
- Gemini client 封裝
- REST API skeleton（僅 `POST /sessions` / `GET /sessions/{id}` 能跑）
- SSE endpoint 能回 heartbeat

**Exit**：後端可建 session、retrieve state、斷開重連 SSE

### M2 — Explore Mode 可用（3 週）

- Explore subgraph 5 節點邏輯落地（題庫、rubric 評分）
- 題庫 YAML 化
- 雙輸出 `emit_dual_output` 實作
- 前端 split layout + ChatPanel + CandidateCards + RubricHeatmap
- SSE streaming agent reply
- HandoffConfirmModal

**Exit**：BU 可從登入走完 Explore → 看到段落描述 modal

### M3 — Consult Mode 可用（3 週）

- BRD 模板 YAML（先做 1-2 個 BU/project_type 組合）
- `load_template` + `auto_fill_outline` + `section_loop` + `quality_gate` 節點
- OutlineTree + SectionEditor（TipTap）+ BrdLivePreview
- Accept/Refine/Skip/Flag 按鈕串 REST + SSE

**Exit**：BU 可從 Explore 完整走到送 BA（BA 端僅收到 API payload，不需 UI）

### M4 — UX 打磨 + Non-Functional（2 週）

- Cold exit、Resume、重新探索 escape hatch
- SSE 斷線重連、streaming 優化
- 結構化錯誤處理與 toast
- 對話一致性檢查 quality_gate 強化
- Observability 接起

**Exit**：10 位 BU 內部 alpha 可用 2 週不當掉

### M5 — Beta 推出準備（2 週）

- Load test（20 同時在線）
- 合規 review / 資安掃描
- Playbook / on-call 準備
- 使用者文件

**Exit**：產品 alpha 穩定 → 打入 prod

> 總計約 13 週工程週期；不含需求凍結前的 PRD 撰寫時間。

---

## 14. Open Questions 對本文影響

下列 overview §8 問題在未決議前，本文以「草案 / 推薦」記錄；決議後須回頭更新相關段落。

| Open Q | 本文影響範圍 | 決議前凍結 |
| --- | --- | --- |
| Q1 Mode 切換自動度 | §3.2.2 `handoff_confirm` node interrupt 設計 | 不凍結；以「BU modal 明確確認」為當前實作預設 |
| Q2 Refine ≤ 3 輪 | §3.2.3 `section_loop`、§4.7 E2 | 以舊 Consult §F-2.2.2 為預設 |
| Q3 段落描述長度 | §3.4 Schema、LLM prompt | 暫定 200–400 字 hard cap |
| Q4 v1.0 BRD 載體 | §5 `deliverables.brd_doc_ref`、§3.7 匯出 endpoint | **凍結 Google Doc 整合**；先做 markdown only |
| Q5 JSON schema 細節 | §3.4 | 實作以 v0.2 草案 Pydantic model 為準 |
| Q6 Save 粒度 | §3.9 Checkpoint | 暫採 interrupt + action 時機 save；不做 per-round |
| Q7 推翻方向 UX | §4.7 C3 | 先做按鈕；natural language detect 延後 |
| Q8 Trace 權限 | §9、§3.7 deliverables endpoint | 預設全可見；`private` 標記延後 |
| Q9 前端框架 | §4 全部 | **Next.js 先鋪**；若決議改 Vue/Svelte 需重做 §4 |
| Q10 Auth | §6 | Cathay SSO (OIDC) 為預設；IdP 底層視 Q15 決議 |
| Q11 Real-time | §3.8 §4.5 | SSE；WebSocket 延後 |
| Q12 通知機制 | §3.1 `notification_service`、§5 notifications | in-app + email；Teams 延後 |
| Q13 BA Agent 共用前端 | §4 component 切分 | 推薦共用；需為 BA view 保留路由空間 `/ba/...` |
| Q14 Trace 傳遞形式 | §3.7 deliverables endpoint、BA Agent 協議 | 先做 API endpoint；共用 DB 直讀延後 |
| Q15 部署拓撲（v0.2 新增） | §2 架構圖、§7 部署、§9 合規 | **Cloud（首選 GCP）**為預設；on-prem 方案保留於 §7.2 方案 B |
| Q16 LLM 呼叫路徑（v0.2 新增） | §3.5 LLM client、§9 LLM 傳輸 | Cloud-first：Gemini API 直連 or Vertex AI；on-prem：Cathay gateway / DLP proxy |

---

## 15. 附錄 (Appendix)

### 15.1 術語對照

| 英文 | 中文 / Cathay 內部用語 |
| --- | --- |
| Business Unit | BU（業務單位） |
| Subject Matter Expert | SME |
| Business Analyst | BA |
| Business Requirement Document | BRD（業務需求書） |
| Single Sign-On | SSO |
| Server-Sent Events | SSE |
| Large Language Model | LLM |
| Retrieval Augmented Generation | RAG（本專案目前不使用） |

### 15.2 與舊架構檔案的映射

| 舊檔 | 本文吸收位置 |
| --- | --- |
| `Explore_agent/explore_agent.md` v0.1 | §3.2.2 Explore subgraph、§3.5 prompts/explore、§3.6 rubric |
| `Consult_agent/consult_agent.md` v0.8 | §3.2.3 Consult subgraph、§3.6 BRD 模板、§10 quality_gate 測試 |
| `BU_Agent_v2_題庫.md` | §3.2.2 `discovery_loop` + `graph/explore/question_bank.py` |
| `overview.md` v0.1（舊三姊妹）| — （本文以 v0.2 為準，不回溯舊架構）|

### 15.3 本文變更紀錄

| 版本 | 日期 | 變更摘要 |
| --- | --- | --- |
| v0.1 | 2026-05-12 | 依 overview v0.2 + user stories v0.1 + frontend comparison v0.1 初版 |
| v0.2 | 2026-05-12 | 對齊 overview v0.3 放寬內網假設：§2 架構圖改 cloud VPC、§6 auth IdP 擴充、§7 部署拓撲三方案、§9 合規改 cloud-first / on-prem 雙軌、§14 新增 Q15 / Q16 |
| v0.3 | 2026-05-13 | 實作對映：M0–M3 全部完成；新增 §15.4「實作偏差紀錄」 |

### 15.4 實作偏差紀錄（v0.3）

實作 M0–M3 過程中與 v0.2 設計文件的偏差,記錄於此供之後 PRD / TDD 同步：

| 主題 | 文件設計 | 實作偏差 | 原因 |
| --- | --- | --- | --- |
| `history` / `pain_signals` reducer | §3.3 GraphState 用 `Annotated[list, operator.add]` | 改為 replace semantics,節點顯式 read-then-concat | LangGraph PostgresSaver round-trip + Pydantic 反序列化偶發 double-add,造成 history 翻倍累積 |
| LangGraph `interrupt()` | §3.2 規範用 `interrupt()` 等 BU reply | 改為「graph 跑到 END → service 收到 BU reply → ainvoke({}) 重啟新 super-step」 | M2 階段測試發現 `ainvoke(None)` 對 ended graph 是 noop;改 `{}` 並去掉 reducer 後路徑更直觀 |
| Frontend SSE client | §4.5 規範 fetch + ReadableStream | 改為原生 `EventSource` + 後端支援 `?user_id=` query 補帶身份 | Next.js dev rewrites 對 fetch event-stream 會 buffer;`EventSource` 不能帶 header → 加 query 備援 |
| BU 訊息 optimistic | TDD §4.4 暗示 optimistic UI | 移除 optimistic,等 backend `bu_turn_recorded` SSE 回來才顯示 | StrictMode 雙 mount + dedupe 殺不淨,改成單一來源最簡單 |
| Consult subgraph entry | §3.2.3 一條 graph 跑全程 | 改為「每個節點 → END」,由 service 多次 ainvoke({}) 推進 | 配合 SSE 無 interrupt 設計;mode 切換期間需多次 invoke 才會走完 load_template + auto_fill_outline + section_loop |
| Auth header | §6 規範 JWT Bearer | M2/M3 走 `X-User-Id` header 或 `?user_id=` query;mock mode | PoC 階段未串 Cathay SSO;切換點集中在 `auth/middleware.py::current_user`,M4 接 SSO 時只改這層 |
| Section editor | §4.6 推薦 TipTap | 暫用 textarea | M3 mock 階段不需要 rich-text; M4 接真 LLM 時換 TipTap |

---

*— End of BU Agent Technical Design v0.2 —*
