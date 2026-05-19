"""Explore 題庫載入與階段輪詢。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel


class QuestionStage(BaseModel):
    id: int
    name: str
    intent: str
    seeds: list[str]
    max_rounds: int


class QuestionBank(BaseModel):
    stages: list[QuestionStage]

    def stage(self, stage_id: int) -> QuestionStage:
        for s in self.stages:
            if s.id == stage_id:
                return s
        raise KeyError(f"stage {stage_id} not found")

    def seed_for(self, stage_id: int, round_idx: int) -> str:
        stage = self.stage(stage_id)
        return stage.seeds[round_idx % len(stage.seeds)]


@lru_cache(maxsize=1)
def load_bank() -> QuestionBank:
    path = Path(__file__).with_name("question_bank.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return QuestionBank.model_validate(data)
