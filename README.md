# BU Agent

BU 端 BRD 草擬助手：Explore（發想）→ Consult（建 BRD 初稿）→ 交接 BA Agent。

依據文件：
- [`Plan_bu_agent/bu_agent_overview.md`](Plan_bu_agent/bu_agent_overview.md) v0.3 — 整體規劃
- [`Plan_bu_agent/bu_agent_user_stories_and_flow.md`](Plan_bu_agent/bu_agent_user_stories_and_flow.md) v0.1 — User Stories
- [`Plan_bu_agent/bu_agent_technical_design.md`](Plan_bu_agent/bu_agent_technical_design.md) v0.2 — 技術設計

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
# 按註解填寫；最小啟動只需要 GEMINI_API_KEY 或設 LLM_MODE=mock
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

驗證：<http://localhost:8000/health> 應回 `{"status":"ok"}`

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

### 6. End-to-end smoke（Explore mode）

1. 瀏覽器開 <http://localhost:3000> → 自動導到 `/login`
2. 選 `Dev BU 001（產險 SME）` → 進入
3. 點「開始新諮詢」→ 填 BU=產險、角色簡述任意
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

---

## 里程碑進度

- [x] M0 — Monorepo 骨架 + README
- [x] M1 — Backend skeleton + DB migration + SSE heartbeat
- [x] M2 — Explore mode 端到端可走（對話→雙輸出→handoff modal→cold exit→reset escape hatch）
- [x] M3 — Consult mode 端到端可走（auto-fill outline → section_loop 訪談 → quality_gate → 送 BA → done 畫面）
- [~] M4 — Gemini 接入（核心節點完成；UX 打磨 / observability 留待後續）
- [ ] M5 — Beta 推出準備（load test、合規 review、playbook）

細節見 `Plan_bu_agent/bu_agent_technical_design.md` §13。

### M3 已實裝功能

- **Explore mode**：題庫 5 階段、候選方向 + 5 維 rubric heatmap、pain signals timeline、cold exit 保護、雙輸出（structured JSON + 段落描述）
- **交接 modal**：「進入 Consult mode」 / 「再討論一下」 / Step 1 期間「重新探索」escape hatch
- **Consult mode**：BRD 模板（產險/壽險/分類 + default fallback）、auto_fill_outline 預填、section_loop 對 needs_round2 章節提問、章節 inline edit、Accept/Refine/Skip/Flag、quality_gate（M3 mock 永遠 pass）
- **送 BA**：deliverables（BRD markdown + summary.json + flag_for_ba_review）寫入 DB、跳轉 `/sessions/[id]/done` 完成畫面、列印/PDF 匯出

### M3 已知技術決策

- LLM 已接 Gemini 2.5 Pro（`LLM_MODE=gemini`）；7 個節點走 prompts/*.j2 + structured output。失敗時退 heuristic / template seed。`/health/llm` 可即時驗證連線
- LangGraph state schema 中 `history` / `pain_signals` 使用 **replace semantics**（非 `operator.add` reducer）；節點顯式 read-then-concat。原因：PostgresSaver round-trip + Pydantic 反序列化下 `operator.add` 在某些版本會 double-add 造成翻倍累積
- SSE 透過原生 `EventSource` + module-level reference counting 處理 React StrictMode mount/unmount race
- 瀏覽器 SSE 直連 backend `:8000`（跳過 Next.js dev rewrites buffer）；REST 仍走 Next 同源 `/api` proxy
