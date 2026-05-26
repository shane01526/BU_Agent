"""LLM client 封裝。支援 gemini / openai / mock 三種 backend（technical_design.md §3.5）。

Public：`get_llm(model)`。前端在建 session 時挑模型,下游節點呼叫時帶 `state.llm_model`,
工廠依 model id 前綴自動挑後端、按 (backend, model) 快取 client。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import TypeVar

from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


def _resolve_backend(model: str | None) -> tuple[str, str]:
    """回傳 (backend_kind, model_id)。kind ∈ {gemini, openai, mock}。

    - llm_mode=mock → 全部走 mock
    - 沒帶 model → 用 settings.default_model
    - 帶 model 但對應 key 缺 → fallback 到 mock + warning
    - llm_mode 強制某 backend 時優先生效
    """
    chosen = (model or settings.default_model or "").strip()

    if settings.llm_mode == "mock":
        return "mock", chosen or "mock"

    if settings.llm_mode == "gemini":
        return ("gemini", chosen or settings.gemini_model)
    if settings.llm_mode == "openai":
        return ("openai", chosen or settings.openai_model)

    # auto：看 prefix
    if chosen.startswith("gpt-") or chosen.startswith("o1") or chosen.startswith("o3"):
        kind = "openai"
    elif chosen.startswith("gemini-"):
        kind = "gemini"
    else:
        kind = "mock"

    if kind == "gemini" and not settings.gemini_api_key:
        log.warning("llm.fallback_to_mock", reason="gemini_key_missing", model=chosen)
        return "mock", chosen
    if kind == "openai" and not settings.openai_api_key:
        log.warning("llm.fallback_to_mock", reason="openai_key_missing", model=chosen)
        return "mock", chosen

    return kind, chosen


class LLMClient:
    """統一介面;真實後端由 _GeminiBackend / _OpenAIBackend 提供, mock 由 _MockBackend 提供。"""

    def __init__(self, kind: str, model: str) -> None:
        self.kind = kind
        self.model = model
        if kind == "gemini":
            self._backend: _Backend = _GeminiBackend(model)
        elif kind == "openai":
            self._backend = _OpenAIBackend(model)
        else:
            self._backend = _MockBackend()

    async def chat_stream(self, messages: list[dict]) -> AsyncIterator[str]:
        async for chunk in self._backend.chat_stream(messages):
            yield chunk

    async def chat_structured(self, messages: list[dict], schema: type[T]) -> T:
        return await self._backend.chat_structured(messages, schema)


# ---- backends ----


class _Backend:
    async def chat_stream(self, messages: list[dict]) -> AsyncIterator[str]:
        raise NotImplementedError

    async def chat_structured(self, messages: list[dict], schema: type[T]) -> T:
        raise NotImplementedError


class _MockBackend(_Backend):
    """離線開發用；依 stage / mode 回罐頭題目，能讓 UI 流程跑通。"""

    _STAGE_QUESTIONS = {
        1: "先聊聊你日常工作的樣子——每天 / 每週你花最多時間在哪些事情上？",
        2: "剛剛你提到的流程，哪個環節最耗時或最容易出錯？一個月大約發生幾次？",
        3: "聽下來你最困擾的幾件事中，如果只能先處理一件，會選哪一件？為什麼？",
        4: "這件事如果 AI 給錯答案，下游要花多少成本去救？可接受的錯誤率大概到哪？",
        5: "聽起來方向差不多了——你想先從『理賠文件自動分類』開始嗎？",
    }

    async def chat_stream(self, messages: list[dict]) -> AsyncIterator[str]:
        stage = 1
        for m in messages:
            if m.get("role") == "system" and "stage=" in m.get("content", ""):
                try:
                    stage = int(m["content"].split("stage=")[1].split()[0])
                except (ValueError, IndexError):
                    pass
        text = self._STAGE_QUESTIONS.get(stage, self._STAGE_QUESTIONS[1])
        for chunk in _chunkify(text, size=8):
            await asyncio.sleep(0.03)
            yield chunk

    async def chat_structured(self, messages: list[dict], schema: type[T]) -> T:
        return schema.model_construct()


class _GeminiBackend(_Backend):
    def __init__(self, model: str) -> None:
        from langchain_google_genai import ChatGoogleGenerativeAI

        self._chat = ChatGoogleGenerativeAI(
            model=model or settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=0.3,
        )

    async def chat_stream(self, messages: list[dict]) -> AsyncIterator[str]:
        lc_messages = _to_langchain_messages(messages)
        async for chunk in self._chat.astream(lc_messages):
            text = _coerce_chunk_text(chunk.content)
            if text:
                yield text

    async def chat_structured(self, messages: list[dict], schema: type[T]) -> T:
        lc_messages = _to_langchain_messages(messages)
        structured = self._chat.with_structured_output(schema)
        result = await structured.ainvoke(lc_messages)
        if isinstance(result, schema):
            return result
        return schema.model_validate(result)


class _OpenAIBackend(_Backend):
    def __init__(self, model: str) -> None:
        from langchain_openai import ChatOpenAI

        self._chat = ChatOpenAI(
            model=model or settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.3,
        )

    async def chat_stream(self, messages: list[dict]) -> AsyncIterator[str]:
        lc_messages = _to_langchain_messages(messages)
        async for chunk in self._chat.astream(lc_messages):
            text = _coerce_chunk_text(chunk.content)
            if text:
                yield text

    async def chat_structured(self, messages: list[dict], schema: type[T]) -> T:
        lc_messages = _to_langchain_messages(messages)
        structured = self._chat.with_structured_output(schema)
        result = await structured.ainvoke(lc_messages)
        if isinstance(result, schema):
            return result
        return schema.model_validate(result)


def _coerce_chunk_text(content) -> str:
    """LangChain astream chunk.content 可能是 str 或 list[block]。統一壓平成 str。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                t = block.get("text")
                if isinstance(t, str):
                    parts.append(t)
        return "".join(parts)
    return str(content)


def _to_langchain_messages(messages: list[dict]):
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    mapping = {"system": SystemMessage, "user": HumanMessage, "assistant": AIMessage}
    return [mapping[m["role"]](content=m["content"]) for m in messages]


def _chunkify(text: str, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


# 按 (kind, model) 快取,避免每次 get_llm 都重建 LangChain client
_clients: dict[tuple[str, str], LLMClient] = {}


def get_llm(model: str | None = None) -> LLMClient:
    kind, resolved_model = _resolve_backend(model)
    key = (kind, resolved_model)
    client = _clients.get(key)
    if client is None:
        client = LLMClient(kind, resolved_model)
        _clients[key] = client
    return client
