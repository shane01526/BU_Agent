"""Pydantic API schemas（request / response DTO）。

與 `app.graph.shared.state.GraphState` 分離：
- GraphState：LangGraph 內部 state
- 本檔：對外 API 表面
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ---- Onboarding ----


class SessionCreateRequest(BaseModel):
    bu: str = Field(..., description="BU 別（產險/壽險/銀行/證券/投信 …）")
    sme_role: str = Field(..., description="1-2 句角色簡述")
    raw_hint: str | None = Field(None, description="選填的第一句 hint")


class SessionSummary(BaseModel):
    session_id: uuid.UUID
    bu: str
    mode: str
    status: str
    updated_at: datetime


class SessionFullState(BaseModel):
    session_id: uuid.UUID
    user_id: str
    bu: str
    sme_role: str
    raw_hint: str | None = None
    mode: str
    stage: int | None = None
    status: str
    # 對話歷史 + 工作區資訊；Explore / Consult 相關欄位 M2+ 填
    history: list[dict] = []
    candidates: list[dict] = []
    pain_signals: list[dict] = []
    sections: list[dict] = []
    paragraph_description: str | None = None


# ---- Messages ----


class MessageInput(BaseModel):
    text: str


class AcceptedResponse(BaseModel):
    accepted: bool = True


# ---- Sections ----


class SectionState(BaseModel):
    section_id: str
    title: str
    status: Literal[
        "auto_filled", "needs_round2", "placeholder", "accepted", "skipped", "flagged_for_ba"
    ]
    content_md: str = ""
    last_edit_by: Literal["agent", "bu"] | None = None


class SectionEditRequest(BaseModel):
    content: str


class SectionActionRequest(BaseModel):
    action: Literal["accept", "refine", "skip", "flag"]
    payload: dict | None = None


class CandidateSelectRequest(BaseModel):
    rank: int


# ---- Handoff / Deliverables ----


class Deliverables(BaseModel):
    brd_doc_ref: str
    summary_json: dict
    flag_for_ba_review: dict
