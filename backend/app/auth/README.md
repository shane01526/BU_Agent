# Auth

## 目前模式（M0–M4 PoC）

`AUTH_MODE=mock`：HTTP header `X-User-Id` 帶測試帳號（預設 `dev-bu-001`）。

- Frontend 登入頁把選定的 user_id 存 cookie `x-dev-user-id`，後續每個 request 帶 `X-User-Id` header
- Backend `app/auth/middleware.py` 的 `current_user` dependency 從 header 撈 user_id 對 DB

切換其他測試使用者：在瀏覽器 DevTools → Application → Cookies 改 `x-dev-user-id`。

## Seed 測試帳號

容器啟動時 `backend/scripts/entrypoint.sh` 會冪等 seed 三筆：

| user_id | display_name | bu | role | 用途 |
| --- | --- | --- | --- | --- |
| `dev-bu-001` | Dev BU 001（產險 SME） | 產險 | `bu_sme` | 預設登入帳號 |
| `dev-bu-002` | Dev BU 002（壽險 SME） | 壽險 | `bu_sme` | 切 BU 測試 |
| `dev-ba-001` | Dev BA 001 | — | `ba` | BA Agent 後續流程預留 |

本機 host 跑 `alembic` 的話，README §3 有對應的 Python 一行 seed 指令。

## 真實部署：`AUTH_MODE=sso`（尚未實作）

- 填 `.env` 的 `OIDC_*` 群組（`OIDC_ISSUER` / `OIDC_CLIENT_ID` / `OIDC_CLIENT_SECRET` / `OIDC_REDIRECT_URI`）
- 在 `app/auth/oidc.py` 實作 token 驗證（**目前尚未提供，目錄下只有 `__init__.py` + `middleware.py` + 本檔**）
- `current_user` 會優先讀 `Authorization: Bearer <jwt>`，退而讀 mock header

最終要綁 Cathay SSO 還是另外的 IdP、cookie 還是 JWT 策略，是 open question — 詳見 [`Plan_BU_Agent/bu_agent_overview.md`](../../../Plan_BU_Agent/bu_agent_overview.md) §8 Q10。
