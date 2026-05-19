-- Seed 測試使用者；正式 schema 由 Alembic 管，這份只建 PoC 開發帳號
-- 若 users 表尚不存在（第一次 up docker 時），Alembic 會後補；此檔採 IF EXISTS 安全插入
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'users') THEN
    INSERT INTO users (user_id, display_name, email, bu, role)
    VALUES
      ('dev-bu-001', 'Dev BU 001（產險 SME）', 'dev-bu-001@example.local', '產險', 'bu_sme'),
      ('dev-bu-002', 'Dev BU 002（壽險 SME）', 'dev-bu-002@example.local', '壽險', 'bu_sme'),
      ('dev-ba-001', 'Dev BA 001',             'dev-ba-001@example.local', NULL,   'ba')
    ON CONFLICT (user_id) DO NOTHING;
  END IF;
END $$;
