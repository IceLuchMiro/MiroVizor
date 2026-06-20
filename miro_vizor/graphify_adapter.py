"""Adapter that exposes vendored graphify as miro_vizor.graphify.*."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Try to import vendor graphify from the bundled copy.
VENDOR = Path(__file__).resolve().parent / "vendor" / "graphify"
if VENDOR.is_dir() and str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

try:
    from graphify import (  # type: ignore
        generate_code_graph,
        generate_text_graph,
        visualize_graph,
    )
except Exception as _exc:  # pragma: no cover - vendor may be missing
    generate_code_graph = None
    generate_text_graph = None
    visualize_graph = None
    _GRAPHIFY_ERROR = _exc
else:
    _GRAPHIFY_ERROR = None


def _ensure_graphify() -> None:
    if _GRAPHIFY_ERROR is not None:
        raise RuntimeError(
            "graphify is not available. Install the graph extra: "
            "pip install -e '.[graph]'"
        ) from _GRAPHIFY_ERROR


def build_code_graph(project_dir: Path | str) -> Dict[str, Any]:
    """Build a NetworkX graph of a Python project structure."""
    _ensure_graphify()
    return generate_code_graph(str(project_dir))


def build_text_graph(text: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Build a semantic graph of MiroVizor levels from a marked text result."""
    _ensure_graphify()
    return generate_text_graph(text, result)


def render_graph(graph: Dict[str, Any], output_path: Path | str) -> None:
    """Render a graph to an interactive HTML file."""
    _ensure_graphify()
    visualize_graph(graph, str(output_path))


class MiroGraphifyExporter:
    """High-level wrapper used by CLI/API to render code and level graphs."""

    def __init__(self, ontology: Optional[Any] = None) -> None:
        self.ontology = ontology

    def write_graph_code(
        self,
        project_dir: Path | str,
        output_path: Path | str,
    ) -> Dict[str, int]:
        """Build and render a code graph to an HTML file."""
        graph = build_code_graph(project_dir)
        render_graph(graph, output_path)
        return {
            "nodes": len(graph.get("nodes", [])),
            "edges": len(graph.get("edges", [])),
            "communities": len(graph.get("communities", [])),
        }

    def write_graph_text(
        self,
        result: Dict[str, Any],
        output_path: Path | str,
        text: Optional[str] = None,
        ontology: Optional[Any] = None,
    ) -> Dict[str, int]:
        """Build and render a level graph from a MiroVizor result."""
        if text is None:
            # Try to reconstruct text from paragraphs/sentences.
            paragraphs = result.get("paragraphs", [])
            if not paragraphs:
                chapters = result.get("chapters", [])
                if chapters:
                    paragraphs = chapters[0].get("paragraphs", [])
            pieces: list[str] = []
            for p in paragraphs:
                for s in p.get("sentences", []):
                    pieces.append(s.get("text", ""))
            text = " ".join(pieces)
        graph = build_text_graph(text, result)
        render_graph(graph, output_path)
        return {
            "nodes": len(graph.get("nodes", [])),
            "edges": len(graph.get("edges", [])),
            "communities": len(graph.get("communities", [])),
        }


__all__ = [
    "MiroGraphifyExporter",
    "build_code_graph",
    "build_text_graph",
    "render_graph",
]
