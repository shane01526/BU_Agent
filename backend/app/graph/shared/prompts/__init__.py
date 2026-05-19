"""Jinja2-based prompt templates。

設計：每個 prompt 一份 .j2,檔頭註明版本與用途;
`render(name, **vars)` 從 templates 渲染後丟給 LLM client。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

_DIR = Path(__file__).parent


@lru_cache(maxsize=1)
def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_DIR)),
        autoescape=select_autoescape(disabled_extensions=("j2",)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=False,
    )


def render(name: str, **vars) -> str:
    """從 prompts/<name>.j2 渲染。"""
    tpl = _env().get_template(f"{name}.j2")
    return tpl.render(**vars)
