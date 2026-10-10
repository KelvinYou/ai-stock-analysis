import copy
import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = runpy.run_path(str(ROOT / "scripts/sync_architecture.py"))


def pipeline():
    return json.loads((ROOT / "pipeline.json").read_text())


def test_generated_flow_preserves_real_optional_memory_and_sequential_risk():
    graph = pipeline()
    generated = GENERATOR["emit"](graph)
    assert 'MEM -.->|"resolved outcomes"| SYN' in generated
    assert "RM --> MEM" not in generated
    assert "SYN --> GATE" in generated
    assert "GATE --> RISK" in generated
    assert "RISK --> OUT" in generated
    assert "MEM --> L4" not in generated
    for edge in graph["edges"]:
        arrow = {"flow": "-->", "conditional": "-.->", "bidirectional": "<-->"}[edge["kind"]]
        label = f'|"{GENERATOR["esc"](edge["label"])}"|' if edge.get("label") else ""
        assert f'{edge["from"]} {arrow}{label} {edge["to"]}' in generated


@pytest.mark.parametrize("corruption", ["unknown_endpoint", "duplicate_id", "literal_newline", "unknown_kind"])
def test_invalid_model_fails_before_generation(corruption):
    graph = pipeline()
    if corruption == "unknown_endpoint":
        graph["edges"][0]["to"] = "MISSING"
    elif corruption == "duplicate_id":
        graph["output"]["id"] = "MEM"
    elif corruption == "literal_newline":
        graph["output"]["label"] = "Briefing\\nresult"
    else:
        graph["edges"][0]["kind"] = "unknown"
    with pytest.raises(ValueError):
        GENERATOR["emit"](graph)


def test_document_is_exactly_generated_from_canonical_model():
    current = (ROOT / "architecture.md").read_text()
    assert GENERATOR["splice"](current, GENERATOR["emit"](pipeline())) == current


def test_legacy_model_without_explicit_edges_remains_supported():
    graph = copy.deepcopy(pipeline())
    graph.pop("edges")
    # Legacy snapshots predate the portfolio batch stage and explicit dependencies.
    graph["stages"] = [stage for stage in graph["stages"] if stage["id"] != "L5"]
    synthesis = graph["stages"][-1]
    synthesis["rows"] = [[synthesis["rows"][0][0], synthesis["rows"][-1][0]]]
    assert "MEM --> L4" in GENERATOR["emit"](graph)
