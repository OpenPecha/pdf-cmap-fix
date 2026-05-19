"""Generate docs/openpecha-forum-post.md from docs/blog.md for forum paste (absolute URLs + mermaid.ink images)."""
from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Tuple

ROOT = Path(__file__).resolve().parents[1]
BLOG = ROOT / "docs" / "blog.md"
OUT = ROOT / "docs" / "openpecha-forum-post.md"
REPO_BLOB = "https://github.com/OpenPecha/pdf-cmap-fix/blob/main"
REPO_TREE = "https://github.com/OpenPecha/pdf-cmap-fix/tree/main"

_INIT = re.compile(r"^%%\{.*?\}%%\s*\n", re.DOTALL | re.MULTILINE)

# All forum diagrams: light canvas + dark labels (readable on white forum CSS behind SVG).
# Covers flowchart + sequence (union of themeVariables both use).
_FORUM_INIT_LIGHT = """%%{init: {'theme':'base','themeVariables':{
'background':'#ffffff',
'primaryColor':'#eeeeee','primaryTextColor':'#111111','primaryBorderColor':'#333333',
'secondaryColor':'#f5f5f5','tertiaryColor':'#e8e8e8',
'lineColor':'#0066cc','textColor':'#111111',
'mainBkg':'#f3f3f3','secondBkg':'#ebebeb','nodeBorder':'#333333',
'clusterBkg':'#f7f7f7','clusterBorder':'#0066cc',
'edgeLabelBackground':'#ffffff','edgeLabelColor':'#000000','titleColor':'#111111',
'actorBkg':'#e8e8e8','actorBorder':'#222222','actorTextColor':'#111111',
'signalColor':'#0066cc','signalTextColor':'#000000',
'labelBoxBkgColor':'#ffffff','labelBoxBorderColor':'#444444','labelTextColor':'#000000',
'activationBkgColor':'#f5f5f5','activationBorderColor':'#333333',
'noteBkgColor':'#fff9e6','noteTextColor':'#111111','noteBorderColor':'#cc8800',
'loopTextColor':'#111111','loopBkgColor':'#eeeeee','loopBorderColor':'#666666'
}}}%%
"""

# Map blog.md dark node styles → light “sequence-style” palette (gray fills, #111 text, blue/green accents).
_LIGHT_CLASSDEF_REPLACEMENTS: Tuple[Tuple[str, str], ...] = (
    (
        "classDef u fill:#1a1a1a,stroke:#e0e0e0,color:#fff",
        "classDef u fill:#ececec,stroke:#444444,color:#111111",
    ),
    (
        "classDef eng fill:#252525,stroke:#e0e0e0,color:#fff",
        "classDef eng fill:#dce8f5,stroke:#0066cc,color:#111111",
    ),
    (
        "classDef g fill:#1f1f1f,stroke:#d0d0d0,color:#fff",
        "classDef g fill:#e8e8e8,stroke:#333333,color:#111111",
    ),
    (
        "classDef in fill:#1a1a1a,stroke:#e0e0e0,color:#fff",
        "classDef in fill:#fff9e6,stroke:#cc8800,color:#111111",
    ),
    (
        "classDef db fill:#222222,stroke:#f5f5f5,color:#fff",
        "classDef db fill:#e3ecf7,stroke:#0066cc,color:#111111",
    ),
    (
        "classDef out fill:#1c1c1c,stroke:#d8d8d8,color:#fff",
        "classDef out fill:#edf7ed,stroke:#2e7d32,color:#111111",
    ),
)


def _lighten_flowchart_classdefs(body: str) -> str:
    for old, new in _LIGHT_CLASSDEF_REPLACEMENTS:
        body = body.replace(old, new)
    return body


def _high_contrast_mermaid_body(diagram: str) -> str:
    body = _INIT.sub("", diagram).strip()
    body = body.replace(
        "    loop for each Type0 font with /ToUnicode\n",
        "    loop for each Type0 font ToUnicode stream\n",
    )

    stripped = body.lstrip()
    if stripped.startswith("flowchart"):
        body = _lighten_flowchart_classdefs(body)
        body = body.replace(
            "flowchart LR",
            "flowchart LR\n  linkStyle default stroke:#0066cc,stroke-width:4px",
            1,
        )
    return _FORUM_INIT_LIGHT + body


def mermaid_ink_svg_url(diagram: str) -> str:
    body = _high_contrast_mermaid_body(diagram)
    b64 = base64.urlsafe_b64encode(body.encode("utf-8")).decode("ascii").rstrip("=")
    return f"https://mermaid.ink/svg/{b64}"


def diagram_alt(diagram: str) -> str:
    if "Original PDF" in diagram and "font_lookup" in diagram:
        return "pdf-cmap-fix end-to-end pipeline"
    if "subgraph Compose" in diagram:
        return "Composition vs decomposition (GSUB walk)"
    if "sequenceDiagram" in diagram:
        return "Runtime sequence: match font, merge maps, write ToUnicode"
    if "U+0F40" in diagram and "Shaper" in diagram:
        return "Forward shaping: Unicode to ligature GID"
    return "Diagram"


def absolutize_links(text: str) -> str:
    t = text
    # scripts
    t = re.sub(
        r"\]\(\.\./scripts/([^)]+)\)",
        rf"]({REPO_BLOB}/scripts/\1)",
        t,
    )
    # docs/*.md
    t = re.sub(
        r"\]\((approach\.md)(#[^)]+)?\)",
        rf"]({REPO_BLOB}/docs/approach.md\2)",
        t,
    )
    t = re.sub(
        r"\]\((font-inventory\.md)(#[^)]+)?\)",
        rf"]({REPO_BLOB}/docs/font-inventory.md\2)",
        t,
    )
    # README
    t = t.replace("](../README.md)", f"]({REPO_BLOB}/README.md)")
    # examples folder in tree
    t = t.replace("](examples/)", f"]({REPO_TREE}/docs/examples/)")
    # bare (approach.md) in prose
    t = t.replace("(approach.md)", f"({REPO_BLOB}/docs/approach.md)")
    return t


def mermaid_to_images(text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        raw = m.group(1)
        return f"![{diagram_alt(raw)}]({mermaid_ink_svg_url(raw)})\n"

    return re.sub(r"```mermaid\n(.*?)```", repl, text, flags=re.DOTALL)


def main() -> None:
    body = BLOG.read_text(encoding="utf-8")
    body = absolutize_links(body)
    body = mermaid_to_images(body)
    header = (
        "<!-- OpenPecha forum export: absolute github.com links; diagrams via mermaid.ink SVG. "
        "All diagrams use a light theme (white bg, dark text, blue connectors) for white forum pages. "
        "Copy from below the line. If images are blocked, open each URL or re-host. -->\n\n"
        "---\n\n"
    )
    OUT.write_text(header + body, encoding="utf-8")
    print("Wrote", OUT)


if __name__ == "__main__":
    main()
