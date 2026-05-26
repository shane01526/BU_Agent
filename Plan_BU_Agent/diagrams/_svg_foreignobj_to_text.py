"""把 mermaid SVG 內所有 <foreignObject><div>...<p>text</p></div></foreignObject>
轉成原生 SVG <text> element,讓 Miro / Inkscape 等不支援 foreignObject 的環境也能顯示文字。

策略:
- 讀 foreignObject 的 width/height 計算 anchor
- 把 <div> 內每個 <span> 或 <br/> 拆成多行
- 用 <text x="w/2" y="line*lineHeight" text-anchor="middle"> 渲染
- 字體/大小從 CSS 推:預設 14px、line-height ~ 18

對齊原則:foreignObject transform 在外層 <g>,我們不動外層 transform,
只把 foreignObject 替換成 <text>,座標相對 (0,0) → 用中心對齊。
"""

from __future__ import annotations

import html
import re
from pathlib import Path

DIAGRAMS = Path(__file__).parent

# foreignObject 完整匹配
FO_RE = re.compile(
    r'<foreignObject(?P<attrs>[^>]*?)>(?P<inner>.*?)</foreignObject>',
    re.DOTALL,
)
WIDTH_RE = re.compile(r'width="([\d.]+)"')
HEIGHT_RE = re.compile(r'height="([\d.]+)"')

# inner 的 <p>...</p> 抽行
P_RE = re.compile(r'<p[^>]*>(.*?)</p>', re.DOTALL)
# 移除剩餘 HTML tag
TAG_RE = re.compile(r'<[^>]+>')

LINE_HEIGHT = 19  # px


def split_lines(inner_html: str) -> list[str]:
    """從 foreignObject 內 HTML 抽出多行純文字。

    優先抽 <p>;若無則整段去 tag 後依 <br/> 切行。
    """
    # 先把 <br/> 統一成換行符
    normalized = re.sub(r'<br\s*/?\s*>', '\n', inner_html, flags=re.IGNORECASE)
    paragraphs = P_RE.findall(normalized)
    if paragraphs:
        # <p> 一段對應一行 group
        lines: list[str] = []
        for p in paragraphs:
            p_text = TAG_RE.sub('', p)
            for sub in p_text.split('\n'):
                stripped = html.unescape(sub).strip()
                if stripped:
                    lines.append(stripped)
        return lines
    # 沒 <p>:整段去 tag 後依 \n 切
    plain = TAG_RE.sub('', normalized)
    return [
        html.unescape(line).strip()
        for line in plain.split('\n')
        if line.strip()
    ]


def fo_to_text(match: re.Match) -> str:
    attrs = match.group('attrs')
    inner = match.group('inner')

    w_m = WIDTH_RE.search(attrs)
    h_m = HEIGHT_RE.search(attrs)
    w = float(w_m.group(1)) if w_m else 100.0
    h = float(h_m.group(1)) if h_m else 24.0

    lines = split_lines(inner)
    if not lines:
        return ''  # 空 label,直接刪

    cx = w / 2
    n = len(lines)
    # 垂直置中:總文字塊高 = (n-1)*LH;頂端 y0 使中心 = h/2
    block_h = (n - 1) * LINE_HEIGHT
    y0 = h / 2 - block_h / 2

    tspans = []
    for i, line in enumerate(lines):
        # XML escape
        safe = html.escape(line)
        y = y0 + i * LINE_HEIGHT
        tspans.append(
            f'<tspan x="{cx:.2f}" y="{y:.2f}">{safe}</tspan>'
        )

    return (
        f'<text text-anchor="middle" dominant-baseline="middle" '
        f'font-family="Microsoft YaHei, PingFang TC, Noto Sans TC, sans-serif" '
        f'font-size="14">'
        + ''.join(tspans)
        + '</text>'
    )


def fix_svg(path: Path) -> tuple[int, int]:
    text = path.read_text(encoding='utf-8')
    before = text.count('<foreignObject')
    new_text, n = FO_RE.subn(fo_to_text, text)
    after = new_text.count('<foreignObject')
    path.write_text(new_text, encoding='utf-8')
    return before, after


def main() -> None:
    files = sorted(DIAGRAMS.glob('*.svg'))
    for f in files:
        before, after = fix_svg(f)
        status = 'OK' if after == 0 else f'RESIDUAL={after}'
        print(f'{f.name}: {before} -> {after}  {status}')


if __name__ == '__main__':
    main()
