# Auth

M0–M2 走 `AUTH_MODE=mock`：HTTP header `X-User-Id` 帶測試帳號（預設 `dev-bu-001`）。
真實部署改 `AUTH_MODE=sso` 並填 `OIDC_*` 變數；`middleware.current_user` 會自動切換實作。

替換步驟：
1. 填 `.env` 的 `OIDC_*` 群組
2. 在 `app/auth/oidc.py` 實作 token 驗證（尚未提供）
3. `current_user` 會優先讀 `Authorization: Bearer <jwt>`，退而讀 mock header
