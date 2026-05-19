"""Per-session SSE endpoint（technical_design.md §3.8）。"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sse_starlette.sse import EventSourceResponse

from app.auth.middleware import current_user
from app.core.db import get_db
from app.core.logging import get_logger
from app.graph.shared.events import bus
from app.models.db import SessionRow, User
from sqlalchemy.orm import Session

log = get_logger(__name__)
router = APIRouter(prefix="/sessions", tags=["sse"])

HEARTBEAT_INTERVAL = 25


@router.get("/{session_id}/events")
async def stream_events(
    session_id: uuid.UUID,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
):
    session = db.get(SessionRow, session_id)
    if session is None or session.user_id != user.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")

    session_key = str(session_id)
    try:
        resume_from = int(last_event_id) if last_event_id else 0
    except ValueError:
        resume_from = 0

    queue, replay = bus.subscribe(session_key, last_event_id=resume_from)

    async def event_source():
        try:
            # 先補送歷史事件，避免訂閱前已 publish 的 agent_reply_delta / candidate_updated 遺失
            for payload in replay:
                yield {
                    "id": str(payload["id"]),
                    "event": payload["type"],
                    "data": json.dumps(payload["data"], ensure_ascii=False),
                }
            while True:
                try:
                    payload = await asyncio.wait_for(
                        queue.get(), timeout=HEARTBEAT_INTERVAL
                    )
                    yield {
                        "id": str(payload["id"]),
                        "event": payload["type"],
                        "data": json.dumps(payload["data"], ensure_ascii=False),
                    }
                except asyncio.TimeoutError:
                    yield {"event": "heartbeat", "data": "{}"}
        except asyncio.CancelledError:
            raise
        finally:
            bus.unsubscribe(session_key, queue)

    return EventSourceResponse(event_source())
