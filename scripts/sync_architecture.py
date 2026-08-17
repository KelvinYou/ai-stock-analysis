#!/usr/bin/env python3
"""Regenerate the mermaid flowchart in architecture.md from pipeline.json.

pipeline.json is the single source of truth: web/app/about renders it as an SVG,
this script renders it as mermaid so the docs cannot drift from the UI. Only the
fenced ```mermaid block is rewritten; the rest of architecture.md is left alone.

Usage:
    python scripts/sync_architecture.py           # rewrite in place
    python scripts/sync_architecture.py --check   # exit 1 if out of date (CI)

Standard library only, on purpose: this runs in CI and in the web build without
needing the project installed.
"""

from __future__ import annotations

import argparse
import json
import sys
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPELINE = ROOT / "pipeline.json"
ARCHITECTURE = ROOT / "architecture.md"
FENCE = "```mermaid"

# Mermaid renders in whatever theme the viewer's markdown host uses, so the
# palette here is deliberately neutral and only marks the bull/bear split.
TONE_STYLE = {
    "bull": "fill:#dcfce7,stroke:#16a34a,color:#14532d",
    "bear": "fill:#fee2e2,stroke:#dc2626,color:#7f1d1d",
    "output": "fill:#f5f5f4,stroke:#57534e,color:#1c1917",
    "muted": "fill:#fafaf9,stroke:#d6d3d1,color:#57534e",
}


def esc(text: str) -> str:
    """Escape what mermaid node labels cannot carry literally."""
    return text.replace("&", "&amp;").replace('"', "&quot;")


def node_label(node: dict) -> str:
    parts = [f"<b>{esc(node['label'])}</b>"]
    parts += [esc(line) for line in node.get("lines", [])]
    return "<br/>".join(parts)


def emit(pipeline: dict) -> str:
    out: list[str] = [FENCE, "flowchart TD"]
    styles: list[str] = []
    # Every stage exits from its last row (or sink) into the next stage's first row.
    prev_exit: list[str] = []

    def collect_styles(node: dict) -> None:
        style = TONE_STYLE.get(node.get("tone", ""))
        if style:
            styles.append(f"    style {node['id']} {style}")

    for stage in pipeline["stages"]:
        header = f"{stage['layer']} — {stage['title']}"
        if stage.get("model"):
            header += f" ({stage.get('modelKey', 'model')} = {stage['model']})"
        elif stage.get("note"):
            header += f" ({stage['note']})"

        out.append("")
        out.append(f'    subgraph {stage["id"]}["{esc(header)}"]')
        rows = stage["rows"]
        # LR only helps when the stage is a single wide row; with stacked rows it
        # fights the top-down edges between them.
        if len(rows) == 1 and len(rows[0]) > 1:
            out.append("        direction LR")
        for row in rows:
            for node in row:
                out.append(f'        {node["id"]}["{node_label(node)}"]')
                collect_styles(node)
        # Bull vs bear argue inside the subgraph; keep that edge local to it.
        if stage.get("pairLabel") and len(rows[-1]) == 2:
            a, b = rows[-1][0]["id"], rows[-1][1]["id"]
            out.append(f'        {a} <-->|"{esc(stage["pairLabel"])}"| {b}')
        out.append("    end")

        # Rows inside a stage chain together, then the sink converges them.
        out.append("")
        for upper, lower in pairwise(rows):
            for src in upper:
                arrow = "-.->" if src.get("dashed") else "-->"
                label = f'|"{esc(src["edgeLabel"])}"|' if src.get("edgeLabel") else ""
                for dst in lower:
                    out.append(f'    {src["id"]} {arrow}{label} {dst["id"]}')

        exit_ids = [n["id"] for n in rows[-1]]
        if stage.get("sink"):
            sink = stage["sink"]
            out.append(f'    {sink["id"]}["{node_label(sink)}"]')
            collect_styles(sink)
            for src_id in exit_ids:
                out.append(f'    {src_id} --> {sink["id"]}')
            exit_ids = [sink["id"]]

        # Cross-stage links go subgraph-to-subgraph when either side is a whole
        # row, so a 4-agent fan-out stays one edge instead of eight.
        if prev_exit:
            entry = [n["id"] for n in rows[0]]
            dsts = [stage["id"]] if len(entry) > 1 else entry
            for src_id in prev_exit:
                for dst_id in dsts:
                    out.append(f"    {src_id} --> {dst_id}")
        prev_exit = [stage["id"]] if len(exit_ids) > 1 else exit_ids

    output = pipeline["output"]
    out.append("")
    out.append(f'    {output["id"]}["{node_label(output)}"]')
    collect_styles(output)
    for src_id in prev_exit:
        out.append(f'    {src_id} --> {output["id"]}')

    if pipeline.get("consumers"):
        out.append("")
        out.append('    subgraph CONSUMERS["Consumers"]')
        out.append("        direction LR")
        for node in pipeline["consumers"]:
            out.append(f'        {node["id"]}["{node_label(node)}"]')
            collect_styles(node)
        out.append("    end")
        out.append(f'    {output["id"]} --> CONSUMERS')

    if styles:
        out.append("")
        out.extend(styles)
    out.append("```")
    return "\n".join(out)


def splice(markdown: str, block: str) -> str:
    """Replace the first fenced mermaid block, or append one if absent."""
    start = markdown.find(FENCE)
    if start == -1:
        return markdown.rstrip() + "\n\n" + block + "\n"
    end = markdown.find("```", start + len(FENCE))
    if end == -1:
        raise SystemExit("architecture.md: unterminated ```mermaid block")
    end = markdown.find("\n", end)
    end = len(markdown) if end == -1 else end
    return markdown[:start] + block + markdown[end:]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 if architecture.md is out of date",
    )
    args = parser.parse_args()

    pipeline = json.loads(PIPELINE.read_text())
    current = ARCHITECTURE.read_text()
    updated = splice(current, emit(pipeline))

    if args.check:
        if updated != current:
            print(
                "architecture.md is out of date — run: python scripts/sync_architecture.py",
                file=sys.stderr,
            )
            return 1
        print("architecture.md is up to date")
        return 0

    if updated == current:
        print("architecture.md already up to date")
        return 0
    ARCHITECTURE.write_text(updated)
    print(f"architecture.md updated from {PIPELINE.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
