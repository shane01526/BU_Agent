"""Session CRUD 與主要 orchestration endpoints。"""

from __future__ import annotations

import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.middleware import current_user
from app.core.db import get_db
from app.core.logging import get_logger
from app.models.db import SessionRow, User
from app.models.schemas import (
    AcceptedResponse,
    CandidateSelectRequest,
    Deliverables,
    MessageInput,
    SectionActionRequest,
    SectionEditRequest,
    SectionState as SectionStateSchema,
    SessionCreateRequest,
    SessionFullState,
    SessionSummary,
)
from app.services import session_service

log = get_logger(__name__)


_BG_TASKS: set[asyncio.Task] = set()


def _spawn(coro_factory, label: str) -> None:
    """以 asyncio.create_task 跑 coroutine,確保 exception 不被吞掉。

    asyncio 用 weak-ref 追 task,沒 keep 強 reference 會被 GC;
    用 module-level set 保住,完成時自動移除。
    """

    async def runner():
        try:
            await coro_factory()
        except BaseException:
            log.exception("background_task_failed", label=label)

    task = asyncio.create_task(runner())
    _BG_TASKS.add(task)
    task.add_done_callback(_BG_TASKS.discard)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionSummary])
def list_sessions(
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[SessionSummary]:
    rows = db.scalars(
        select(SessionRow)
        .where(SessionRow.user_id == user.user_id, SessionRow.deleted_at.is_(None))
        .order_by(SessionRow.updated_at.desc())
    ).all()
    return [
        SessionSummary(
            session_id=r.session_id,
            bu=r.bu,
            mode=r.mode,
            status=r.status,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


@router.post("", response_model=SessionSummary, status_code=201)
async def create_session(
    payload: SessionCreateRequest,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SessionSummary:
    session = await session_service.create_session(db, user, payload)
    sid = session.session_id
    _spawn(lambda: _run_turn_bg(sid, None), f"kickoff:{sid}")
    return SessionSummary(
        session_id=session.session_id,
        bu=session.bu,
        mode=session.mode,
        status=session.status,
        updated_at=session.updated_at,
    )


@router.get("/{session_id}", response_model=SessionFullState)
async def get_session(
    session_id: uuid.UUID,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SessionFullState:
    session = db.get(SessionRow, session_id)
    if session is None or session.user_id != user.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")

    # 從 LangGraph checkpoint 讀最新 state
    from app.graph.main_graph import get_graph
    from app.graph.shared.state import GraphState

    graph = await get_graph()
    config = {"configurable": {"thread_id": str(session_id)}}
    snapshot = await graph.aget_state(config)
    state = (
        GraphState.model_validate(snapshot.values)
        if snapshot.values
        else None
    )

    sections = []
    if state:
        for s in state.brd_outline:
            d = s.model_dump() if not isinstance(s, dict) else s
            # 轉成前端統一介面（content_md 名稱對齊 Section schema）
            sections.append(
                {
                    "section_id": d["section_id"],
                    "title": d["title"],
                    "status": d["status"],
                    "content_md": d.get("draft_content", ""),
                    "last_edit_by": d.get("last_edit_by"),
                }
            )

    return SessionFullState(
        session_id=session.session_id,
        user_id=session.user_id,
        bu=session.bu,
        sme_role=session.sme_role,
        raw_hint=session.raw_hint,
        mode=session.mode,
        stage=session.stage,
        status=session.status,
        history=[h.model_dump() for h in state.history] if state else [],
        candidates=[c.model_dump() for c in state.scored_candidates] if state else [],
        pain_signals=[p.model_dump() for p in state.pain_signals] if state else [],
        sections=sections,
        paragraph_description=state.paragraph_description if state else None,
    )


@router.post("/{session_id}/messages", response_model=AcceptedResponse, status_code=202)
async def post_message(
    session_id: uuid.UUID,
    payload: MessageInput,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AcceptedResponse:
    session = db.get(SessionRow, session_id)
    if session is None or session.user_id != user.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    if session.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "session not active")

    text = payload.text
    _spawn(lambda: _run_turn_bg(session_id, text), f"turn:{session_id}")
    return AcceptedResponse()


async def _run_turn_bg(session_id: uuid.UUID, text: str | None) -> None:
    from app.core.db import SessionLocal

    db = SessionLocal()
    try:
        session = db.get(SessionRow, session_id)
        if session is None:
            log.warning("run_turn_bg.session_missing", session_id=str(session_id))
            return
        await session_service.run_turn(db, session, bu_text=text)
    finally:
        db.close()


@router.post("/{session_id}/candidates/select", response_model=AcceptedResponse)
async def select_candidate(
    session_id: uuid.UUID,
    payload: CandidateSelectRequest,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AcceptedResponse:
    session = db.get(SessionRow, session_id)
    if session is None or session.user_id != user.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    await session_service.select_candidate(db, session, payload.rank)
    return AcceptedResponse()


@router.post("/{session_id}/handoff/confirm", response_model=AcceptedResponse)
async def confirm_handoff(
    session_id: uuid.UUID,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AcceptedResponse:
    session = db.get(SessionRow, session_id)
    if session is None or session.user_id != user.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    await session_service.confirm_handoff(db, session)
    return AcceptedResponse()


@router.post("/{session_id}/handoff/dismiss", response_model=AcceptedResponse)
async def dismiss_handoff(
    session_id: uuid.UUID,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AcceptedResponse:
    """BU 在 handoff modal 點「再討論一下」。"""
    session = db.get(SessionRow, session_id)
    if session is None or session.user_id != user.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    await session_service.dismiss_handoff(db, session)
    return AcceptedResponse()


@router.post("/{session_id}/ai-necessity/acknowledge", response_model=AcceptedResponse)
async def acknowledge_ai_necessity_warning(
    session_id: uuid.UUID,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AcceptedResponse:
    """BU 點「我了解了/讓我繼續想想」。"""
    session = db.get(SessionRow, session_id)
    if session is None or session.user_id != user.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    await session_service.acknowledge_ai_necessity_warning(db, session)
    return AcceptedResponse()


@router.post("/{session_id}/ai-necessity/override", response_model=AcceptedResponse)
async def override_ai_necessity_warning(
    session_id: uuid.UUID,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AcceptedResponse:
    """BU 點「還是想試試 AI」:標 bu_overrode,寫進 BRD。"""
    session = db.get(SessionRow, session_id)
    if session is None or session.user_id != user.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    await session_service.override_ai_necessity_warning(db, session)
    return AcceptedResponse()


@router.post("/{session_id}/ai-necessity/explain", response_model=AcceptedResponse)
async def explain_ai_necessity(
    session_id: uuid.UUID,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AcceptedResponse:
    """BU 點「想了解差別」:agent 在對話區產一段白話說明。"""
    session = db.get(SessionRow, session_id)
    if session is None or session.user_id != user.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    # 用 spawn 跑 LLM streaming(別讓 endpoint 等 5-15 秒)
    sid = session_id
    _spawn(lambda: _explain_ai_bg(sid), f"explain:{sid}")
    return AcceptedResponse()


async def _explain_ai_bg(session_id: uuid.UUID) -> None:
    from app.core.db import SessionLocal

    db = SessionLocal()
    try:
        session = db.get(SessionRow, session_id)
        if session is None:
            return
        await session_service.explain_solution_class(db, session)
    finally:
        db.close()


@router.post("/{session_id}/stage5/dismiss", response_model=AcceptedResponse)
async def dismiss_stage5_stuck(
    session_id: uuid.UUID,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AcceptedResponse:
    """BU 在 stage 5 卡關 modal 點「再聊一下」。"""
    session = db.get(SessionRow, session_id)
    if session is None or session.user_id != user.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    await session_service.dismiss_stage5_stuck(db, session)
    return AcceptedResponse()


@router.post("/{session_id}/stage5/quick-handoff", response_model=AcceptedResponse)
async def quick_handoff(
    session_id: uuid.UUID,
    payload: CandidateSelectRequest,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AcceptedResponse:
    """BU 在 stage 5 卡關 modal 點「先用 #N 試試 BRD」。"""
    session = db.get(SessionRow, session_id)
    if session is None or session.user_id != user.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    await session_service.quick_handoff(db, session, payload.rank)
    return AcceptedResponse()


@router.post("/{session_id}/explore/reset", response_model=AcceptedResponse)
async def reset_explore(
    session_id: uuid.UUID,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AcceptedResponse:
    """C3 重新探索：清候選與大綱,回到 Explore mode。"""
    session = db.get(SessionRow, session_id)
    if session is None or session.user_id != user.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    await session_service.reset_explore(db, session)
    return AcceptedResponse()


# ---- Consult Step 2 ----


@router.get("/{session_id}/sections", response_model=list[SectionStateSchema])
async def list_sections(
    session_id: uuid.UUID,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[SectionStateSchema]:
    session = db.get(SessionRow, session_id)
    if session is None or session.user_id != user.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    rows = await session_service.get_outline(db, session)
    return [
        SectionStateSchema(
            section_id=r["section_id"],
            title=r["title"],
            status=r["status"],
            content_md=r.get("draft_content", ""),
            last_edit_by=r.get("last_edit_by"),
        )
        for r in rows
    ]


@router.patch(
    "/{session_id}/sections/{section_id}", response_model=SectionStateSchema
)
async def edit_section(
    session_id: uuid.UUID,
    section_id: str,
    payload: SectionEditRequest,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SectionStateSchema:
    session = db.get(SessionRow, session_id)
    if session is None or session.user_id != user.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    try:
        sec = await session_service.edit_section(
            db, session, section_id, payload.content
        )
    except KeyError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    return SectionStateSchema(
        section_id=sec["section_id"],
        title=sec["title"],
        status=sec["status"],
        content_md=sec.get("draft_content", ""),
        last_edit_by=sec.get("last_edit_by"),
    )


@router.post(
    "/{session_id}/sections/{section_id}/action", response_model=SectionStateSchema
)
async def section_action(
    session_id: uuid.UUID,
    section_id: str,
    payload: SectionActionRequest,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SectionStateSchema:
    session = db.get(SessionRow, session_id)
    if session is None or session.user_id != user.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    try:
        sec = await session_service.section_action(
            db, session, section_id, payload.action
        )
    except KeyError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return SectionStateSchema(
        section_id=sec["section_id"],
        title=sec["title"],
        status=sec["status"],
        content_md=sec.get("draft_content", ""),
        last_edit_by=sec.get("last_edit_by"),
    )


@router.post("/{session_id}/submit", response_model=Deliverables)
async def submit_session(
    session_id: uuid.UUID,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Deliverables:
    """F1 送 BA：產出交付物 + 標 session done。"""
    session = db.get(SessionRow, session_id)
    if session is None or session.user_id != user.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    out = await session_service.submit_session(db, session)
    return Deliverables(
        brd_doc_ref=out["brd_doc_ref"] or "",
        summary_json=out["summary_json"] or {},
        flag_for_ba_review={"sections": out["flag_for_ba_review"]},
    )
