"""動態列出 OpenAI / Gemini 帳號可用的「對話 / 多模態 chat」模型。

過濾策略寫死在這檔,方便日後微調:
- 排除純 image / tts / transcribe / embedding / moderation / search / sora / veo / imagen ...
- 保留可以走 chat/responses (含 reasoning: o1/o3/o4/gpt-5*) + 多模態語言模型 (gemini-*)
- 結果 in-memory cache 5 分鐘,避免每次前端進 New Session 都打外部 API

list-models API 失敗時 fallback 到 settings.allowed_model_list。
"""

from __future__ import annotations

import time

import httpx

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

_CACHE_TTL_SEC = 300  # 5 min
_cache: dict[str, tuple[float, list[str]]] = {}


# ---- OpenAI ----

# 字串子串/前綴比對：命中即排除。寬鬆且明確,日後加新類別只要在這加一行。
_OPENAI_EXCLUDE_SUBSTRINGS = (
    "embedding",
    "moderation",
    "transcribe",
    "tts",
    "-image",
    "image-",
    "-search",
    "search-",
    "babbage",
    "davinci",
    "instruct",
    "sora",
    "deep-research",
    "computer-use",
    "realtime-translate",
    "realtime-whisper",
)
# 必須以這些前綴開頭才視為 chat/reasoning 模型
_OPENAI_INCLUDE_PREFIXES = (
    "gpt-",
    "o1",
    "o3",
    "o4",
    "chatgpt-",
    "chat-latest",
)


def _is_openai_chat_model(model_id: str) -> bool:
    if not any(model_id.startswith(p) for p in _OPENAI_INCLUDE_PREFIXES):
        return False
    if any(s in model_id for s in _OPENAI_EXCLUDE_SUBSTRINGS):
        return False
    # gpt-image / chatgpt-image 等已被 -image 攔下;gpt-audio 是 chat 模型,留
    return True


# ---- Gemini ----

_GEMINI_EXCLUDE_SUBSTRINGS = (
    "embedding",
    "tts",
    "image",  # gemini-*-image-* / imagen / nano-banana-pro 等
    "imagen",
    "veo",
    "lyria",
    "robotics",
    "native-audio",
    "computer-use",
    "deep-research",
    "gemma",
    "aqa",
    "nano-banana",
)


def _is_gemini_chat_model(name: str, methods: list[str]) -> bool:
    base = name.replace("models/", "")
    if not base.startswith("gemini-"):
        return False
    if "generateContent" not in methods:
        return False
    if any(s in base for s in _GEMINI_EXCLUDE_SUBSTRINGS):
        return False
    return True


# ---- fetchers ----


async def _fetch_openai_models() -> list[str]:
    if not settings.openai_api_key:
        return []
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        )
        r.raise_for_status()
        data = r.json().get("data", [])
    ids = [x["id"] for x in data if isinstance(x, dict) and "id" in x]
    return sorted({m for m in ids if _is_openai_chat_model(m)})


async def _fetch_gemini_models() -> list[str]:
    if not settings.gemini_api_key:
        return []
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": settings.gemini_api_key},
        )
        r.raise_for_status()
        models = r.json().get("models", [])
    out: list[str] = []
    for m in models:
        name = m.get("name", "")
        methods = m.get("supportedGenerationMethods", []) or []
        if _is_gemini_chat_model(name, methods):
            # 統一去掉 "models/" 前綴,langchain-google-genai 接受兩種
            out.append(name.replace("models/", ""))
    return sorted(set(out))


async def _cached(kind: str, fetcher) -> list[str]:
    now = time.time()
    cached = _cache.get(kind)
    if cached and now - cached[0] < _CACHE_TTL_SEC:
        return cached[1]
    try:
        result = await fetcher()
        _cache[kind] = (now, result)
        return result
    except Exception as e:
        log.warning("models_catalog.fetch_failed", kind=kind, error=str(e))
        # fetch 失敗:若有舊 cache 就回舊的;沒有就 raise
        if cached:
            return cached[1]
        raise


async def list_chat_models() -> dict:
    """回傳 {models, default, backends_available, source}。

    source ∈ {"live", "fallback"}：fallback 表示動態抓失敗,用 .env 白名單。
    """
    openai_models: list[str] = []
    gemini_models: list[str] = []
    failures: list[str] = []

    if settings.openai_api_key:
        try:
            openai_models = await _cached("openai", _fetch_openai_models)
        except Exception:
            failures.append("openai")
    if settings.gemini_api_key:
        try:
            gemini_models = await _cached("gemini", _fetch_gemini_models)
        except Exception:
            failures.append("gemini")

    combined = openai_models + gemini_models

    # 兩邊都失敗 / 兩邊都沒設 key → fallback 到 .env 的白名單
    if not combined:
        return {
            "models": settings.allowed_model_list,
            "default": settings.default_model,
            "backends_available": {
                "openai": bool(settings.openai_api_key),
                "gemini": bool(settings.gemini_api_key),
            },
            "source": "fallback",
            "failures": failures,
        }

    # default 仍以 settings.default_model 為主;若不在 combined 內則用第一個 OpenAI / 第一個 Gemini
    default = settings.default_model
    if default not in combined:
        default = openai_models[0] if openai_models else gemini_models[0]

    return {
        "models": combined,
        "default": default,
        "backends_available": {
            "openai": bool(settings.openai_api_key),
            "gemini": bool(settings.gemini_api_key),
        },
        "source": "live",
        "failures": failures,
    }
