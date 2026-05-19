"""FastAPI 入口。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import sessions as sessions_api
from app.api.v1 import sse as sse_api
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.graph.main_graph import close_graph, get_graph

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log.info("bu_agent.startup", env=settings.app_env, llm_mode=settings.llm_mode)
    # 預熱 graph / checkpointer
    try:
        await get_graph()
    except Exception as e:  # DB 尚未就緒時不阻斷 FastAPI 起動
        log.warning("graph.prewarm_failed", error=str(e))
    yield
    await close_graph()


app = FastAPI(title="BU Agent API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions_api.router, prefix="/api/v1")
app.include_router(sse_api.router, prefix="/api/v1")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "env": settings.app_env, "llm_mode": settings.llm_mode}


@app.get("/health/llm")
async def health_llm() -> dict:
    """戳一次 LLM 確認連線 / API key / 模型可用。"""
    from app.graph.shared.llm import get_llm

    llm = get_llm()
    chunks: list[str] = []
    try:
        async for chunk in llm.chat_stream(
            [
                {"role": "system", "content": "回覆規則:只回 OK 兩個字"},
                {"role": "user", "content": "ping"},
            ]
        ):
            chunks.append(chunk)
            if sum(len(c) for c in chunks) > 64:
                break
    except Exception as e:
        return {
            "status": "error",
            "llm_mode": settings.llm_mode,
            "model": settings.gemini_model,
            "error": f"{type(e).__name__}: {e}",
        }
    return {
        "status": "ok",
        "llm_mode": settings.llm_mode,
        "model": settings.gemini_model,
        "sample": "".join(chunks)[:200],
    }
