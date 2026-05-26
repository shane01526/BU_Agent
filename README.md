# BU Agent

> **Last updated 2026-05-25** — 同步至 code 現況。本次主要變更：
> - LLM 多後端：`LLM_MODE=auto/gemini/openai/mock`、`OPENAI_API_KEY` / `OPENAI_MODEL` / `ALLOWED_MODELS` / `DEFAULT_MODEL` 加入 `.env`
> - 新 endpoint：`GET /api/v1/models`（動態抓供應商可用模型 + 過濾）、`/health/llm?model=` 可指定
> - 前端 New Session 頁加模型選單；session 級綁定模型
> - DB migration 0002：`sessions.llm_model` 欄位
> - AI 必要性彈窗 + Stage 5 收斂彈窗採 deferred-reply pattern；BU 選項標籤寫進 history、reload 後不重彈
> - `docker-compose.yml` 改 `env_file: - .env`（避開 host shell env 蓋過 .env）
> - M4 完成；M3 全功能可走

BU 端 BRD 草擬助手：Explore（發想）→ Consult（建 BRD 初稿）→ 交接 BA Agent。

依據文件：
- [`Plan_bu_agent/bu_agent_overview.md`](Plan_bu_agent/bu_agent_overview.md) v0.3 — 整體規劃
- [`Plan_bu_agent/bu_agent_user_stories_and_flow.md`](Plan_bu_agent/bu_agent_user_stories_and_flow.md) v0.1 — User Stories
- [`Plan_bu_agent/bu_agent_technical_design.md`](Plan_bu_agent/bu_agent_technical_design.md) v0.2 — 技術設計
- [`Plan_bu_agent/agent_dialog_logic.md`](Plan_bu_agent/agent_dialog_logic.md) — 對話 / 彈窗邏輯
- [`Plan_bu_agent/agent_prompting_rules.md`](Plan_bu_agent/agent_prompting_rules.md) v0.2 — Prompt 規則

---

## Repo Layout

```
BU_Agent/
├── Plan_bu_agent/          # 規劃與設計文件（不是 code）
├── past/                   # 舊三姊妹架構 PRD 參考
├── backend/                # FastAPI + LangGraph 服務
├── frontend/               # Next.js web app
├── shared/                 # 前後端共用 schema（Pydantic ↔ TypeScript）
├── infra/                  # docker-compose、Alembic migration、seed
├── .gitignore
├── .env.example
└── docker-compose.yml
```

---

## 環境建置

### 0. 前置需求

| 工具 | 最低版本 | 驗證 | 備註 |
| --- | --- | --- | --- |
| Docker Desktop | 4.20+ | `docker --version` | Windows 建議開 WSL2 backend |
| Node.js | 20.x | `node --version` | 建議用 `nvm` / `fnm` 管理 |
| pnpm | 9.x | `pnpm --version` | `npm i -g pnpm` |
| Python | 3.11+ | `python --version` | 建議用 `uv` / `pyenv` 管理 |
| uv（選配） | 0.4+ | `uv --version` | 比 pip 快很多 |

### 1. 取得 repo 與環境變數

```bash
# 在 BU_Agent/ 目錄下
cp .env.example .env
# 按註解填寫；最小啟動三選一：
#   1. 設 OPENAI_API_KEY + LLM_MODE=auto（或 openai）
#   2. 設 GEMINI_API_KEY + LLM_MODE=auto（或 gemini）
#   3. 不設任何 key + LLM_MODE=mock（離線開發、罐頭回應）
# LLM_MODE=auto 會依 model id 前綴自動選後端；對應 key 缺時 fallback 到 mock
```

### 2. 啟動 infra（Postgres）

```bash
docker compose up -d postgres
# 驗證
docker compose ps
```

### 3. Backend 起動（開發模式）

```bash
cd backend
# 安裝依賴
python -m venv .venv
# Windows: .venv\Scripts\activate
# *nix:    source .venv/bin/activate
pip install -e ".[dev]"

# 跑 migration
alembic upgrade head

# 建測試使用者
python -c "from app.core.db import SessionLocal; from app.models.db import User; \
db=SessionLocal(); \
[db.add(User(user_id=i, display_name=n, email=e, bu=b, role=r)) for i,n,e,b,r in \
 [('dev-bu-001','Dev BU 001（產險 SME）','dev-bu-001@example.local','產險','bu_sme'), \
  ('dev-bu-002','Dev BU 002（壽險 SME）','dev-bu-002@example.local','壽險','bu_sme')] \
 if db.get(User, i) is None]; \
db.commit(); print('seeded')"

# 起 dev server
uvicorn app.main:app --reload --port 8000
```

驗證：
- `GET http://localhost:8000/health` → `{"status":"ok","env":"local","llm_mode":"auto"}`
- `GET http://localhost:8000/health/llm?model=gpt-4o-mini` → 戳一次指定模型驗連線（不帶 query 用 `DEFAULT_MODEL`）；回 `{"status":"ok","backend":"openai","model":"gpt-4o-mini","sample":"OK"}` 表示 key + 模型可用
- `GET http://localhost:8000/api/v1/models` → 動態抓 OpenAI / Gemini 可用 chat 模型清單（5 分鐘 cache，前端 New Session 頁靠這個）

### 4. Frontend 起動

```bash
cd frontend
pnpm install
pnpm dev
```

開 <http://localhost:3000>，應自動導到 `/login`。

### 5. 全部用 docker-compose 起動（推薦 smoke test）

```bash
cp .env.example .env
docker compose up --build
# 前端 http://localhost:3000；後端 http://localhost:8000
# backend container 的 entrypoint 會自動跑 alembic + seed 測試使用者
```

**環境變數策略**：`docker-compose.yml` 用 `env_file: - .env` 把整份 `.env` 直接灌進 backend container（不再用 `${VAR:-default}` 注入）。
原因：避開 Windows host shell env 蓋過 `.env` 的雷 —— 例如開發者系統環境變數已有舊的 `OPENAI_API_KEY`，
`${OPENAI_API_KEY:-}` 規則「shell env 優先於 .env」會拿到舊 key；改用 `env_file` 後 `.env` 是 single source of truth。
驗證 container 實際讀到的值：

```bash
docker compose exec backend bash -lc 'echo "OPENAI head=${OPENAI_API_KEY:0:11}; LLM_MODE=$LLM_MODE"'
```

### 6. 上 AWS EC2 部署（PoC：直接用 IP + port）

預期：把整個 `BU_Agent/` 丟進 EC2 → 填 LLM key → `docker compose up`，瀏覽器開 `http://<ec2-public-ip>:3000` 即可。前端 SSE 在 runtime 從 `window.location.hostname` 自動推 backend URL，不需 build-time 知道 EC2 IP。

**步驟**

```bash
# 1. 把整包送上 EC2（rsync 比 scp 快；或乾脆 git clone）
rsync -avz --exclude .git --exclude node_modules --exclude .next --exclude .venv \
  ./ ec2-user@<ec2-public-ip>:~/BU_Agent/

# 2. SSH 進去
ssh ec2-user@<ec2-public-ip>
cd BU_Agent

# 3. 準備 .env（填 LLM API key）
cp .env.example .env
vim .env   # 至少填 OPENAI_API_KEY 或 GEMINI_API_KEY

# 4. 全套起來
docker compose up --build -d
docker compose ps    # postgres healthy + backend Up + frontend Up
```

開瀏覽器：`http://<ec2-public-ip>:3000` → 登入 `dev-bu-001（產險 SME）` → 開新諮詢。

**EC2 必備設定**

| 項目 | 設定 |
| --- | --- |
| Instance | `t3.medium`（4GB RAM）以上；`t3.small` 跑得動但會吃緊 |
| Disk | 20GB+（pgdata + docker images） |
| Security Group inbound | TCP **3000**（前端，使用者瀏覽器） + **8000**（後端，瀏覽器 SSE 直連） + **22**（SSH） |
| Outbound | 預設 all |
| Elastic IP | 強烈建議（不然重啟 EC2 後 IP 會變、網址跟著改） |
| Docker | 必須安裝 docker + docker compose plugin（Amazon Linux 2023 預設已有） |

**Docker daemon 預設不會開機自啟；EC2 重啟後**：

```bash
sudo systemctl enable --now docker
```

`docker-compose.yml` 三個 service 都有 `restart: unless-stopped`，docker daemon 起來後 container 會自動恢復。

**Troubleshoot**

| 症狀 | 解法 |
| --- | --- |
| 瀏覽器開頁面 OK 但對話沒回覆、Network tab 看 `:8000/events` 連不上 | Security Group 沒開 8000；SSE 是瀏覽器**直連** backend，不走 Next.js proxy |
| `docker compose up` 卡在 frontend build | EC2 RAM 不夠（Next build 吃 ~1.5GB），升級 instance 或加 swap |
| `:8000/health` 401 Incorrect API key | host shell env 蓋過 `.env`：`docker compose exec backend bash -lc 'echo ${OPENAI_API_KEY:0:11}'` 比對 |

**回到本機 dev**：把 `.env` 的 `APP_ENV=prod` 改 `local`，並改用 host-side `pnpm dev` / `uvicorn ... --reload` 而非 docker-compose（image 是 prod build，不適合 hot reload）。

---

### 7. End-to-end smoke（Explore mode）

1. 瀏覽器開 <http://localhost:3000> → 自動導到 `/login`
2. 選 `Dev BU 001（產險 SME）` → 進入
3. 點「開始新諮詢」→ 填 BU=產險、角色簡述任意，並從「LLM 模型」下拉挑一個（OpenAI / Gemini 分組，缺 key 的選項自動 disabled）
4. 對話區應在 1–2 秒後出現第一題（stage 1）
5. 輸入回應（隨意幾句字）送出 → 工作區右側應出現候選卡片
6. 繼續對話 3–5 輪；點選中一張候選卡片 → agent 繼續進到 stage 5
7. 進到 stage 5 且 `selected_candidate` 已選 → 工作區應彈 **交接 modal** 顯示段落描述
8. 點「進入 Consult mode」 → progress bar 推進（M3 前工作區會提示未實作）

---

## 開發流程

1. 開 branch：`feat/<milestone>-<short-desc>`
2. Backend 變更後跑 `pytest`；Frontend 變更跑 `pnpm test`
3. PR 須附 smoke test 畫面（如涉及 UI）

### Mock Auth（M0–M2 PoC 階段）

尚未接 Cathay SSO 前，後端以 `X-User-Id` header 辨識使用者；Frontend 登入頁會存一個固定 user_id 到 cookie。

- 預設測試使用者：`dev-bu-001`（在 `infra/seed.sql` 建立）
- 切換其他測試使用者：Frontend 開發工具改 cookie `x-dev-user-id`

上 prod / 串 Cathay SSO 時，見 `backend/app/auth/README.md`。

### LLM Mock Mode

沒有 `GEMINI_API_KEY` 時設 `LLM_MODE=mock`；會回罐頭問答，可離線開發 UI。

---

## Troubleshooting

| 症狀 | 解法 |
| --- | --- |
| Windows 下 `pip install` 抓 C 擴充失敗 | 安裝 VS Build Tools，或 `uv pip install` |
| `alembic upgrade head` 連不到 DB | 確認 `docker compose ps` 中 postgres 已 healthy；`.env` 的 `DATABASE_URL` 主機名 local 為 `localhost`、container 內為 `postgres` |
| SSE 一直斷線 | 確認前端 dev server 沒擋 `Accept: text/event-stream`；Windows 防毒可能攔 long polling |
| pnpm 裝不起來 | `corepack enable` 後 `corepack prepare pnpm@latest --activate` |
| `/health/llm` 回 `OPENAI 401` 或 `Incorrect API key` | (1) 直接 `curl -H "Authorization: Bearer $key" https://api.openai.com/v1/models` 驗 key 對不對；(2) 若 key 對但容器仍 401，多半是 host 系統環境變數蓋過 `.env`：`docker compose exec backend bash -lc 'echo ${OPENAI_API_KEY:0:11}'` 比對是否跟 `.env` 一致；不一致就是 host shell env 衝突，已用 `env_file:` 修但要重新 `docker compose up -d --force-recreate backend` 才生效 |
| 前端模型選單空白 / 一直 loading | 檢查 `GET http://localhost:8000/api/v1/models` 是否回 200；若回 `source: "fallback"` 表示後端打 OpenAI / Gemini list-models 都失敗，看 backend logs `models_catalog.fetch_failed`；常見：`OPENAI_API_KEY` 是 project key 但帳號沒對應權限、或 5 分鐘 cache 還沒到期但 key 才剛換 → 重啟 backend 立即生效 |

---

## 里程碑進度

- [x] M0 — Monorepo 骨架 + README
- [x] M1 — Backend skeleton + DB migration + SSE heartbeat
- [x] M2 — Explore mode 端到端可走（對話→雙輸出→handoff modal→cold exit→reset escape hatch）
- [x] M3 — Consult mode 端到端可走（auto-fill outline → section_loop 訪談 → quality_gate → 送 BA → done 畫面）
- [x] M4 — **多 LLM 後端（Gemini + OpenAI + auto 路由）+ 動態模型清單 + deferred-reply 彈窗 pattern**（AI 必要性 + Stage 5 收斂）+ SSE replay 防呆
- [ ] M5 — Beta 推出準備（load test、合規 review、playbook）

細節見 `Plan_bu_agent/bu_agent_technical_design.md` §13。

### M3 / M4 已實裝功能

- **Explore mode**：題庫 5 階段、候選方向 + 5 維 rubric heatmap、pain signals timeline、cold exit 保護、雙輸出（structured JSON + 段落描述、含 `ai_necessity_triage`）
- **交接 modal**：「進入 Consult mode」 / 「再討論一下」 / Step 1 期間「重新探索」escape hatch
- **AI 必要性彈窗（M4）**：score_candidates 偵測 top1 連續 2 輪 ai_necessity=low 時彈，三選項（我了解了 / 還是想用 AI / 想了解差別）+ 重新探索 escape；deferred-reply pattern：彈窗期間 graph 暫停、BU 點選項後 agent 才 LLM stream 回應
- **Stage 5 收斂彈窗（M4）**：stage 5 連 3 輪未選 candidate 時彈，2 選項（再聊一下 / 先用 #N 試試 BRD）+ reset；同樣 deferred-reply pattern；quick_handoff 直接走 emit_dual_output 不 stream
- **多 LLM 後端（M4）**：`LLM_MODE=auto` 依 model id 前綴自動選 OpenAI / Gemini / mock；session 級綁定模型；`GET /api/v1/models` 動態抓清單 + 過濾出 chat 模型 + 5 分鐘 cache + fallback 到 `.env` 白名單
- **Consult mode**：BRD 模板（產險/壽險/分類 + default fallback）、auto_fill_outline 預填、section_loop 對 needs_round2 章節提問、章節 inline edit、Accept/Refine/Skip/Flag、quality_gate（M3 mock 永遠 pass）
- **送 BA**：deliverables（BRD markdown + summary.json + flag_for_ba_review）寫入 DB、跳轉 `/sessions/[id]/done` 完成畫面、列印/PDF 匯出

### M3 / M4 已知技術決策

- **多 LLM 後端**：`backend/app/graph/shared/llm.py` 三個 backend（`_GeminiBackend` / `_OpenAIBackend` / `_MockBackend`）；`get_llm(model)` 工廠依 model id 前綴自動分流，按 `(kind, model)` 快取；session 在新建時綁定 `llm_model`（`SessionCreateRequest.llm_model`、`sessions.llm_model` migration 0002），整段 BRD 草擬用同一顆 LLM 避免風格漂移
- **動態模型清單**：`backend/app/services/models_catalog.py` 直接打 OpenAI v1/models 與 Gemini v1beta/models API，過濾出可走 chat 的（排除 image / tts / transcribe / embedding / sora / imagen / veo 等），5 分鐘 in-memory cache；任一供應商失敗仍給對方的清單，全失敗 fallback 至 `.env` 的 `ALLOWED_MODELS`
- **Deferred-reply 彈窗 pattern**：`pending_ai_necessity_decision` / `pending_stage5_decision` 兩個 transient flag 在 `score_candidates` / `converge_check` 觸發彈窗時 set；`subgraph.py:after_converge` 看到 flag 直接 END，graph 不再產 agent 回覆。BU 點 modal 選項後對應 endpoint 才 record BU 選項標籤 trace（寫進 history、發 `bu_turn_recorded` SSE）→ LLM stream agent reply（4 個新 prompt：`acknowledge_ai_necessity.j2` / `override_ai_necessity.j2` / `explain_solution_class.j2` / `stage5_keep_talking.j2`）→ clear flag
- **SSE replay 防呆**：reload 後 SessionBus ring buffer 會 replay 所有歷史事件（含彈窗）。前端 SSE handler 用 `qc.getQueryData<SessionFullState>` 同步讀 react-query cache，看到 `acked && !pending` 略過；額外 cleanup `useEffect` 兜底；handler 點完 `qc.invalidateQueries` 縮短 stale 窗口
- **Meta 問題承接**：`explore_question.j2` 最高優先規則 — BU 問「還有其他方向 / 多給幾個 / 換個角度」時 LLM 第一句承接 ≤ 50 字 + 第二句新探索題、整體 ≤ 110 字
- **LangGraph state schema** 中 `history` / `pain_signals` 使用 **replace semantics**（非 `operator.add` reducer）；節點顯式 read-then-concat。原因：PostgresSaver round-trip + Pydantic 反序列化下 `operator.add` 在某些版本會 double-add 造成翻倍累積
- **SSE 透過原生 EventSource** + module-level reference counting 處理 React StrictMode mount/unmount race
- **瀏覽器 SSE 直連 backend `:8000`**（跳過 Next.js dev rewrites buffer）；REST 仍走 Next 同源 `/api` proxy
