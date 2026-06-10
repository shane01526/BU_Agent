"""LangGraph 內部 state schema（technical_design.md §3.3）。

設計選擇：history / pain_signals 不用 `operator.add` reducer。
原因：在 LangGraph PostgresSaver round-trip + Pydantic 序列化下,reducer 偶爾會
重複套用,造成 history 翻倍累積。改為「replace」semantics、由節點顯式 read-then-write。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PainSignal(BaseModel):
    turn_id: int
    raw_text: str
    source: Literal["bu_explicit", "agent_reframe"]
    tags: list[str] = Field(default_factory=list)


SOLUTION_CLASSES = (
    "rule",
    "rpa",
    "pipeline",
    "classical_ml",
    "llm_extract",
    "llm_reason",
    "agent",
)
AI_NECESSITY_LEVELS = ("low", "medium", "high")


class CandidateDirection(BaseModel):
    rank: int
    direction: str
    process_target: str
    project_type: str
    # rule_repeat / data_avail / reversibility / scale_roi / gap
    score_5d: dict[str, int] = Field(default_factory=dict)
    # 每個維度一句話描述「為何給這分」；key 同 score_5d
    score_5d_desc: dict[str, str] = Field(default_factory=dict)
    pain_signals: list[str] = Field(default_factory=list)
    # AI 必要性 triage（M4 加入,擋過度導 AI）
    solution_class: str | None = None  # 7 類之一,見 SOLUTION_CLASSES
    ai_necessity: str | None = None  # low / medium / high
    solution_rationale: str | None = None  # 一句話說明


class TraceEntry(BaseModel):
    turn_id: int
    mode: str
    role: Literal["agent", "bu", "system"]
    raw_text: str
    agent_reframe_flag: bool = False
    bu_choice_flag: bool = False
    linked_candidate_id: int | None = None
    timestamp: str
    # Consult Step 2 章節訪談時,標記 trace 對應的章節 id;Explore 階段為 None
    section_id: str | None = None


class PainSignalDraft(BaseModel):
    """LLM structured output: 抽 pain signal（缺 turn_id,由 caller 補）。"""

    raw_text: str
    source: Literal["bu_explicit", "agent_reframe"] = "bu_explicit"
    tags: list[str] = Field(default_factory=list)


class PainSignalListOutput(BaseModel):
    signals: list[PainSignalDraft] = Field(default_factory=list)


class CandidateScore5d(BaseModel):
    rule_repeat: int = Field(ge=1, le=5)
    data_avail: int = Field(ge=1, le=5)
    reversibility: int = Field(ge=1, le=5)
    scale_roi: int = Field(ge=1, le=5)
    gap: int = Field(ge=1, le=5)


class CandidateScore5dDesc(BaseModel):
    """5 維評分各一句話描述（為何給這分）。"""

    rule_repeat: str
    data_avail: str
    reversibility: str
    scale_roi: str
    gap: str


class CandidateDraft(BaseModel):
    """LLM 評分 output 的單條候選。"""

    rank: int
    direction: str
    process_target: str
    project_type: str
    score_5d: CandidateScore5d
    score_5d_desc: CandidateScore5dDesc
    pain_signals: list[str] = Field(default_factory=list)
    solution_class: Literal[
        "rule", "rpa", "pipeline", "classical_ml",
        "llm_extract", "llm_reason", "agent",
    ]
    ai_necessity: Literal["low", "medium", "high"]
    solution_rationale: str


class CandidateListOutput(BaseModel):
    candidates: list[CandidateDraft] = Field(default_factory=list)


class SectionDraft(BaseModel):
    """LLM auto_fill_outline 的單章 output。"""

    section_id: str
    content_md: str


class SectionDraftListOutput(BaseModel):
    sections: list[SectionDraft] = Field(default_factory=list)


class Conflict(BaseModel):
    section_ids: list[str]
    description: str


class ConflictListOutput(BaseModel):
    conflicts: list[Conflict] = Field(default_factory=list)


class SectionState(BaseModel):
    section_id: str
    title: str
    status: Literal[
        "auto_filled",
        "needs_round2",
        "placeholder",
        "accepted",
        "skipped",
        "flagged_for_ba",
    ]
    draft_content: str = ""
    last_edit_by: Literal["agent", "bu"] | None = None


class GraphState(BaseModel):
    """`thread_id == session_id`；由 PostgresSaver 持久化。"""

    # identifiers
    session_id: str
    user_id: str

    # mode state
    # "submit" 是 service 層送 BA 時暫時設的觸發值（consult subgraph entry router
    # 用它路由到 build_deliverables）；build_deliverables 末端再把 mode 設回 "done"。
    mode: Literal[
        "explore", "consult_step1", "consult_step2", "submit", "done", "cold"
    ] = "explore"
    stage: int = 1  # Explore 題庫階段 1-5

    # onboarding metadata
    bu: str
    sme_role: str
    raw_hint: str | None = None
    # 該 session 全程使用的 LLM 模型 id（前端建 session 時挑一次,中途不換）
    llm_model: str | None = None

    # dialog（replace semantics；節點要 append 時自己讀 + concat）
    history: list[TraceEntry] = Field(default_factory=list)
    pain_signals: list[PainSignal] = Field(default_factory=list)

    # explore working state
    candidate_directions: list[CandidateDirection] = Field(default_factory=list)
    scored_candidates: list[CandidateDirection] = Field(default_factory=list)
    selected_candidate: int | None = None
    ready_to_handoff: bool = False
    # BU 已「不採用」的候選方向文字；餵給評分 prompt 避免重生同方向
    rejected_directions: list[str] = Field(default_factory=list)

    # Stage 5 卡關偵測:
    # - stage_5_rounds:在 stage 5 已跑過幾輪 discovery_loop
    # - stage_5_stuck_acked:BU 已在 stuck modal 點過「再聊一下」,本 session 不再彈
    # - pending_stage5_decision:stage5_stuck 已發、等 BU 在 modal 做選擇,
    #   期間 graph 不再產 agent 回覆;dismiss / quick_handoff endpoint 後 clear
    stage_5_rounds: int = 0
    stage_5_stuck_acked: bool = False
    pending_stage5_decision: bool = False

    # AI 必要性 triage:
    # - low_ai_necessity_streak:top 1 候選連續被 LLM 標 low 的次數
    # - ai_necessity_warned:已彈過 warning modal,本 session 不再彈
    # - bu_overrode_ai_necessity:BU 看過 warning 仍堅持用 AI(會寫進 BRD)
    # - pending_ai_necessity_decision:彈窗已發、等 BU 在 modal 做選擇,
    #   期間 graph 不再產 agent 回覆;三個 modal endpoint 之一被呼叫後 clear
    low_ai_necessity_streak: int = 0
    ai_necessity_warned: bool = False
    bu_overrode_ai_necessity: bool = False
    pending_ai_necessity_decision: bool = False

    # dual output
    structured_json: dict | None = None
    paragraph_description: str | None = None

    # consult state
    brd_outline: list[SectionState] = Field(default_factory=list)
    current_section_idx: int | None = None
    conflicts: list[str] = Field(default_factory=list)

    # deliverables
    summary_json: dict | None = None
    conversation_trace: list[TraceEntry] = Field(default_factory=list)
    brd_doc_ref: str | None = None

    # misc
    cold_exit_reason: str | None = None
    # 最新一題 agent 提問；前端用這個決定 chat panel 顯示內容
    pending_question: str | None = None
