"""BU 知識卡（Knowledge Card）載入器與 Schema。

設計原則:
- 一份 BU 一個 YAML 檔(`knowledge/<bu>.yaml`),找不到 → fallback `default.yaml`
- LRU cache;改檔需重啟 backend container 或呼叫 `clear_cache()`
- Pydantic 驗證:確保 prompt 注入時欄位齊備、型別正確
- 所有欄位 optional with sensible defaults,允許先填一部分上線

對應規劃文件:`Plan_bu_agent/agent_prompting_rules.md` §10(待新增)
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class GlossaryItem(BaseModel):
    """一條業務術語對應(L1)。"""

    term: str  # 縮寫或內部用語,例:"PIS"
    full_name: str  # 完整名稱,例:"核保系統 (Policy Issuing System)"
    note: str = ""  # 一句補充,例:"商業保險主系統"


class AiInventoryItem(BaseModel):
    """Cathay 內部已建 AI / RPA / 工具清單(L3)。

    score_candidates 評 ROI / gap / ai_necessity 時用,避免重做別人做過的事。
    """

    name: str  # "文件 OCR 模型"
    status: str = "已上線"  # 已上線 / PoC / 規劃中
    owner: str = ""  # AI 科 / RPA team / 個別 BU
    scope: str = ""  # "理賠" / "客服" / "全行" 之類粒度
    note: str = ""  # 補充用


class KnowledgeCard(BaseModel):
    """單一 BU 的知識卡。

    所有欄位都允許空,prompt template 會用 Jinja2 條件判斷該段落要不要 render。
    """

    bu: str  # 必填:對應 BU 別(產險 / 壽險 / 銀行 ...)
    version: str = "v0.1"
    last_updated: str = ""  # ISO date,例:"2026-05-14"
    contact: str = ""  # 知識卡 owner 聯絡資訊;agent 不會 render 但給人 review 用

    # L1 業務術語(縮寫對照表)
    glossary: list[GlossaryItem] = Field(default_factory=list)

    # L2 BU 流程概觀
    process_overview: str = ""  # 多行字串,描述該 BU 主要工作流
    typical_pain_patterns: list[str] = Field(default_factory=list)  # 常見痛點 pattern

    # L2.5 規模與量能(score_candidates 評 ROI 用)
    volume_hints: list[str] = Field(default_factory=list)
    # 例:["新契約量月均 3000 件", "理賠案件月均 5000 件"]

    # L3 Cathay 已建 AI / 工具清單
    cathay_ai_inventory: list[AiInventoryItem] = Field(default_factory=list)

    # 法遵 / 合規地雷(taboos);agent 提醒 BU 哪些不能寫進 BRD
    taboos: list[str] = Field(default_factory=list)

    # 該 BU 偏好 / 不偏好的解決方案類型(影響 ai_necessity triage)
    preferred_solution_classes: list[str] = Field(default_factory=list)
    # 例:["llm_extract"]  → score 階段該 BU 對 LLM 抽取偏好高
    avoided_solution_classes: list[str] = Field(default_factory=list)
    # 例:["agent"]  → 該 BU 不偏好導入 multi-turn agent

    # 過去 BRD 經驗教訓(自由文字,給 agent 提問時參考)
    past_brd_lessons: list[str] = Field(default_factory=list)


_DIR = Path(__file__).parent / "knowledge"


@lru_cache(maxsize=16)
def load_card(bu: str) -> KnowledgeCard:
    """先試精準匹配,再 fallback 到 default。"""
    candidates = [
        _DIR / f"{bu}.yaml",
        _DIR / "default.yaml",
    ]
    for path in candidates:
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not data:
                continue
            # 強制 bu 欄位:精準匹配檔不允許 bu 寫錯;fallback 檔自動覆蓋成請求的 bu
            data.setdefault("bu", bu)
            return KnowledgeCard.model_validate(data)
    # 連 default 都沒有 → 回空殼,prompt 會走 fallback 區塊
    return KnowledgeCard(bu=bu)


def clear_cache() -> None:
    """改 yaml 不重啟 container 時手動清。M5 之後可加 file watch。"""
    load_card.cache_clear()
