"""SessionBus：把 LangGraph 節點 emit 的事件 fan-out 給 SSE 連線。

TDD §3.8 / §2.2：單 session 可能有多條 SSE 連線（多 tab），每條都該收到事件。
PoC 用 in-memory pub-sub；prod 若要跨 process 可換 Redis pub-sub。

v0.2 修：
- 每 session 保留最近 N 個事件於 ring buffer
- subscribe 時可帶 last_event_id，回放之後所有事件
- 這同時解決 graph 跑太快、SSE 連線晚到的 race
"""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from typing import Any

# 每個 session 保留的歷史事件數（約一次完整 Explore 5-7 輪 × 5 events = ~35，留寬一點）
HISTORY_LIMIT = 256


class SessionBus:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._counter: dict[str, int] = defaultdict(int)
        self._history: dict[str, deque[dict]] = defaultdict(
            lambda: deque(maxlen=HISTORY_LIMIT)
        )

    async def publish(self, session_id: str, event_type: str, data: dict[str, Any]) -> None:
        self._counter[session_id] += 1
        payload = {"id": self._counter[session_id], "type": event_type, "data": data}
        self._history[session_id].append(payload)
        for q in list(self._subs.get(session_id, set())):
            await q.put(payload)

    def subscribe(
        self, session_id: str, last_event_id: int = 0
    ) -> tuple[asyncio.Queue, list[dict]]:
        """訂閱 session 事件流。

        為避免 race：subscribe 與 replay snapshot 之間若有新事件進 history，
        會同步 push 到 queue（但同一個事件不會重複——history append 與 publish
        都在 publish() 內完成，subscribe 不會卡到中間）。
        """
        q: asyncio.Queue = asyncio.Queue(maxsize=512)
        # 先取 replay 再加進 subs，確保同一 publish 不會同時出現在 replay 與 queue
        replay = [
            p for p in self._history.get(session_id, ()) if p["id"] > last_event_id
        ]
        self._subs[session_id].add(q)
        return q, replay

    def unsubscribe(self, session_id: str, q: asyncio.Queue) -> None:
        self._subs.get(session_id, set()).discard(q)


bus = SessionBus()
