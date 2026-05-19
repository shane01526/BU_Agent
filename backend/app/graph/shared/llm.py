"""LLM client 封裝。支援 gemini / mock 兩種 mode（technical_design.md §3.5）。"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import TypeVar

from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """統一介面；真實 Gemini 呼叫由 `_GeminiBackend`、mock 由 `_MockBackend` 提供。"""

    def __init__(self) -> None:
        if settings.llm_mode == "gemini" and settings.gemini_api_key:
            self._backend: _Backend = _GeminiBackend()
        else:
            if settings.llm_mode == "gemini":
                log.warning(
                    "llm_mode=gemini but GEMINI_API_KEY empty; falling back to mock"
                )
            self._backend = _MockBackend()

    async def chat_stream(self, messages: list[dict]) -> AsyncIterator[str]:
        async for chunk in self._backend.chat_stream(messages):
            yield chunk

    async def chat_structured(
        self, messages: list[dict], schema: type[T]
    ) -> T:
        return await self._backend.chat_structured(messages, schema)


# ---- backends ----


class _Backend:
    async def chat_stream(self, messages: list[dict]) -> AsyncIterator[str]:
        raise NotImplementedError

    async def chat_structured(
        self, messages: list[dict], schema: type[T]
    ) -> T:
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
        # 取 messages 裡 system 的 hint（可能帶 stage 資訊）
        stage = 1
        for m in messages:
            if m.get("role") == "system" and "stage=" in m.get("content", ""):
                try:
                    stage = int(m["content"].split("stage=")[1].split()[0])
                except (ValueError, IndexError):
                    pass
        text = self._STAGE_QUESTIONS.get(stage, self._STAGE_QUESTIONS[1])
        # 拆成幾個 chunk 模擬 streaming
        for chunk in _chunkify(text, size=8):
            await asyncio.sleep(0.03)
            yield chunk

    async def chat_structured(
        self, messages: list[dict], schema: type[T]
    ) -> T:
        """給 mock 一個最小合理實例；不同 schema 不同處理。"""
        # 單純回 schema 的 default instance；節點層會負責組更合理的內容
        return schema.model_construct()


class _GeminiBackend(_Backend):
    """真呼叫；延後 import 以避免 mock 模式也要求裝套件正確。"""

    def __init__(self) -> None:
        from langchain_google_genai import ChatGoogleGenerativeAI

        self._chat = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=0.3,
        )

    async def chat_stream(self, messages: list[dict]) -> AsyncIterator[str]:
        lc_messages = _to_langchain_messages(messages)
        async for chunk in self._chat.astream(lc_messages):
            if chunk.content:
                yield chunk.content  # type: ignore[misc]

    async def chat_structured(
        self, messages: list[dict], schema: type[T]
    ) -> T:
        lc_messages = _to_langchain_messages(messages)
        structured = self._chat.with_structured_output(schema)
        result = await structured.ainvoke(lc_messages)
        if isinstance(result, schema):
            return result
        return schema.model_validate(result)


def _to_langchain_messages(messages: list[dict]):
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    mapping = {"system": SystemMessage, "user": HumanMessage, "assistant": AIMessage}
    return [mapping[m["role"]](content=m["content"]) for m in messages]


def _chunkify(text: str, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


# lazy singleton
_client: LLMClient | None = None


def get_llm() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
