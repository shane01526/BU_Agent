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

    llm_mode: Literal["gemini", "mock"] = "mock"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-pro"

    auth_mode: Literal["mock", "sso"] = "mock"
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = "http://localhost:3000/auth/callback"

    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
