"""BRD 模板載入器。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel


class SectionTemplate(BaseModel):
    id: str
    title: str
    owner: str
    default_status: str
    extract_from_explore: list[str] = []
    questions: list[str] = []


class BrdTemplate(BaseModel):
    template_id: str
    bu: str
    project_type: str
    sections: list[SectionTemplate]


_DIR = Path(__file__).parent / "templates"


@lru_cache(maxsize=32)
def load_template(bu: str, project_type: str) -> BrdTemplate:
    """先試精準匹配,再 fallback 到 default。"""
    candidates = [
        _DIR / f"{bu}_{project_type}.yaml",
        _DIR / "default.yaml",
    ]
    for path in candidates:
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            return BrdTemplate.model_validate(data)
    raise FileNotFoundError(f"no template found for bu={bu} project_type={project_type}")
