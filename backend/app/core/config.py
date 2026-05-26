from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["local", "dev", "staging", "prod"] = "local"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://bu_agent:bu_agent@localhost:5432/bu_agent"
    langgraph_checkpoint_url: str = (
        "postgresql://bu_agent:bu_agent@localhost:5432/bu_agent"
    )

    # llm_mode 留作 fallback / 強制 mock 之用；正式選模由前端傳的 llm_model 決定。
    # - "auto"：依 model id 前綴（gpt-* → openai；gemini-* → gemini；其他 → mock）
    # - "gemini" / "openai"：強制走該後端
    # - "mock"：強制離線罐頭
    llm_mode: Literal["auto", "gemini", "openai", "mock"] = "auto"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # 前端模型選單白名單（CSV）。若為空,fallback 內建預設清單。
    allowed_models: str = ""
    default_model: str = "gpt-4o-mini"

    @property
    def allowed_model_list(self) -> list[str]:
        items = [m.strip() for m in self.allowed_models.split(",") if m.strip()]
        if items:
            return items
        return ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gemini-2.5-pro"]

    auth_mode: Literal["mock", "sso"] = "mock"
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = "http://localhost:3000/auth/callback"

    # PoC：REST 走 same-origin Next.js proxy 不會用到 CORS；SSE 用 EventSource
    # 不帶 cookie，配 "*" 對 IP 部署夠安全。上 SSO / domain 時收緊到實際 origin。
    cors_origins: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
