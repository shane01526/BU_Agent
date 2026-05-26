#!/usr/bin/env bash
set -e

# 等 Postgres 可用
python - <<'PY'
import os, time, psycopg
url = os.environ.get("DATABASE_URL", "").replace("+psycopg", "")
for i in range(30):
    try:
        with psycopg.connect(url, connect_timeout=2) as _:
            break
    except Exception as e:
        print(f"waiting for db ({i}) ... {e}")
        time.sleep(1)
else:
    raise SystemExit("Postgres not reachable after 30s")
PY

alembic upgrade head

# Seed 測試使用者（冪等；已存在則 no-op）
python - <<'PY'
from app.core.db import SessionLocal
from app.models.db import User

rows = [
    ("dev-bu-001", "Dev BU 001（產險 SME）", "dev-bu-001@example.local", "產險", "bu_sme"),
    ("dev-bu-002", "Dev BU 002（壽險 SME）", "dev-bu-002@example.local", "壽險", "bu_sme"),
    ("dev-ba-001", "Dev BA 001",              "dev-ba-001@example.local", None,   "ba"),
]
with SessionLocal() as db:
    for uid, name, email, bu, role in rows:
        if db.get(User, uid) is None:
            db.add(User(user_id=uid, display_name=name, email=email, bu=bu, role=role))
    db.commit()
print("seeded users OK")
PY

# 只在 APP_ENV=local 時掛 --reload（dev 用）；prod / EC2 都不掛，避免容器內檔案
# 變動觸發 reload 而把 LangGraph PostgresSaver session 連線打斷。
if [ "${APP_ENV:-prod}" = "local" ]; then
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
else
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi
