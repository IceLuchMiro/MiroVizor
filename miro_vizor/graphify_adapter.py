"""Adapter that exposes vendored graphify as miro_vizor.graphify.*.

Контракт (совместимый с тестами и CLI):
    build_code_graph(project_dir) -> networkx.Graph
    build_text_graph(text, result, ontology=None) -> networkx.Graph
    build_levels_graph(result, ontology=None) -> networkx.Graph   (alias build_text_graph)
    render_graph(graph_or_dict, output_path)
    export_graph_html(G, output_path)                              (alias render_graph)

Vendored graphify API (см. miro_vizor/vendor/graphify/graphify/__init__.py):
    collect_files, extract, build_from_json, cluster, score_all, to_html, ...
Импортируем функции напрямую из подмодулей: при доступе через пакет
graphify.<name> lazy-__getattr__ может вернуть одноимённый подмодуль вместо функции.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Подключаем vendored-копию graphify в путь импорта.
VENDOR = Path(__file__).resolve().parent / "vendor" / "graphify"
if VENDOR.is_dir() and str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

try:
    from graphify.extract import collect_files, extract as extract_files  # type: ignore
    from graphify.build import build_from_json  # type: ignore
    from graphify.cluster import cluster, score_all  # type: ignore
    from graphify.export import to_html  # type: ignore
except Exception as _exc:  # pragma: no cover - vendor может отсутствовать
    build_from_json = None  # type: ignore
    cluster = None  # type: ignore
    collect_files = None  # type: ignore
    score_all = None  # type: ignore
    to_html = None  # type: ignore
    extract_files = None  # type: ignore
    _GRAPHIFY_ERROR = _exc
else:
    _GRAPHIFY_ERROR = None


def _ensure_graphify() -> None:
    if _GRAPHIFY_ERROR is not None:
        raise RuntimeError(
            "graphify недоступен. Установите графовые зависимости: "
            "pip install -e '.[graph]'"
        ) from _GRAPHIFY_ERROR


# ── Внутренние хелперы ───────────────────────────────────────────────────────

def _extract_project(project: Path) -> Dict[str, Any]:
    """Собрать объединённую extraction-структуру из всех .py-файлов проекта."""
    files = collect_files(project)
    extractions: List[dict] = []
    for f in files:
        ext = extract_files([f])
        if ext.get("nodes"):
            extractions.append(ext)
    nodes: list[dict] = []
    edges: list[dict] = []
    seen: set[str] = set()
    for e in extractions:
        for n in e.get("nodes", []):
            if n["id"] not in seen:
                seen.add(n["id"])
                nodes.append(n)
        edges.extend(e.get("edges", []))
    return {"nodes": nodes, "edges": edges}


def _build_nx(extraction: Dict[str, Any]):
    """Из nodes/edges-дикта собрать NetworkX граф через graphify.build_from_json."""
    _ensure_graphify()
    return build_from_json(extraction)


# ── Публичный API ────────────────────────────────────────────────────────────

def build_code_graph(project_dir: Path | str):
    """Построить NetworkX-граф структуры Python-проекта (файлы, классы, функции, импорты)."""
    _ensure_graphify()
    combined = _extract_project(Path(project_dir))
    return _build_nx(combined)


def build_text_graph(
    text: str,
    result: Dict[str, Any],
    ontology: Optional[Any] = None,
):
    """Построить NetworkX-граф уровней Миросложения из результата mark_text.

    Узлы: труд → главы → предложения → уровни; рёбра — принадлежность.
    Аргумент ontology принят для совместимости со старым API и пока не используется.
    """
    _ensure_graphify()
    nodes: list[dict] = []
    edges: list[dict] = []

    def _nid(*parts: str) -> str:
        raw = "_".join(str(p) for p in parts if str(p) != "")
        return re.sub(r"[^a-zA-Z0-9]+", "_", raw).strip("_").lower()

    work = result.get("work", {})
    work_id = _nid("work")
    nodes.append({
        "id": work_id,
        "label": work.get("title") or "Труд",
        "file_type": "document",
        "source_file": "",
        "source_location": "",
    })
    dom = work.get("dominant_level")
    if dom:
        dom_id = _nid("level", dom)
        nodes.append({
            "id": dom_id,
            "label": f"{dom} (доминанта)",
            "file_type": "document",
            "source_file": "",
            "source_location": "",
        })
        edges.append({
            "source": work_id,
            "target": dom_id,
            "relation": "dominant",
            "confidence": "EXTRACTED",
            "source_file": "",
            "source_location": "",
            "weight": 1.0,
        })

    for ch in result.get("chapters", []):
        ch_id = _nid("chapter", ch.get("index"))
        ch_label = ch.get("title") or f"Глава {ch.get('index')}"
        nodes.append({
            "id": ch_id,
            "label": ch_label,
            "file_type": "document",
            "source_file": "",
            "source_location": "",
        })
        edges.append({
            "source": work_id,
            "target": ch_id,
            "relation": "contains",
            "confidence": "EXTRACTED",
            "source_file": "",
            "source_location": "",
            "weight": 1.0,
        })

        for s in ch.get("sentences", []):
            s_id = _nid("sentence", ch.get("index"), s.get("index"))
            s_text = (s.get("text") or "").replace("\n", " ")
            if len(s_text) > 60:
                s_text = s_text[:57] + "..."
            nodes.append({
                "id": s_id,
                "label": f"#{s.get('index')}: {s_text}",
                "file_type": "document",
                "source_file": "",
                "source_location": "",
            })
            edges.append({
                "source": ch_id,
                "target": s_id,
                "relation": "contains",
                "confidence": "EXTRACTED",
                "source_file": "",
                "source_location": "",
                "weight": 1.0,
            })
            sdom = s.get("dominant_level")
            if sdom:
                lvl_id = _nid("level", sdom)
                if not any(n["id"] == lvl_id for n in nodes):
                    nodes.append({
                        "id": lvl_id,
                        "label": sdom,
                        "file_type": "document",
                        "source_file": "",
                        "source_location": "",
                    })
                edges.append({
                    "source": s_id,
                    "target": lvl_id,
                    "relation": "level",
                    "confidence": "EXTRACTED",
                    "source_file": "",
                    "source_location": "",
                    "weight": 1.0,
                })

    return _build_nx({"nodes": nodes, "edges": edges})


def build_levels_graph(
    result: Dict[str, Any],
    ontology: Optional[Any] = None,
    text: Optional[str] = None,
):
    """Alias build_text_graph для совместимости со старым API.

    Принимает result первым аргументом и optional ontology/text,
    чтобы работать как `build_levels_graph(result, ontology=ontology)`.
    """
    if text is None:
        pieces: list[str] = []
        for ch in result.get("chapters", []):
            for s in ch.get("sentences", []):
                pieces.append(s.get("text", ""))
        text = " ".join(pieces)
    return build_text_graph(text, result, ontology=ontology)


def render_graph(graph: Any, output_path: Path | str) -> None:
    """Сохранить граф в интерактивный HTML (vis.js) через graphify.to_html.

    graph может быть NetworkX-графом или dict-обёрткой {graph, communities}.
    """
    _ensure_graphify()
    if isinstance(graph, dict) and "graph" in graph:
        G = graph["graph"]
        communities = graph.get("communities", {})
    else:
        G = graph
        communities = {}
    if communities == {} and G is not None:
        communities = cluster(G)
    to_html(G, communities, str(output_path))


# Обратная совместимость с README и старым API
export_graph_html = render_graph


class MiroGraphifyExporter:
    """Высокоуровневая обёртка для CLI/API: рендерит графы кода и уровней в HTML."""

    def __init__(self, ontology: Optional[Any] = None) -> None:
        self.ontology = ontology

    def write_graph_code(
        self,
        project_dir: Path | str,
        output_path: Path | str,
    ) -> Dict[str, int]:
        """Построить и сохранить граф кода проекта в HTML."""
        _ensure_graphify()
        G = build_code_graph(project_dir)
        communities = cluster(G)
        to_html(G, communities, str(output_path))
        return {
            "nodes": G.number_of_nodes(),
            "edges": G.number_of_edges(),
            "communities": len(communities),
        }

    def write_graph_text(
        self,
        result: Dict[str, Any],
        output_path: Path | str,
        text: Optional[str] = None,
        ontology: Optional[Any] = None,
    ) -> Dict[str, int]:
        """Построить и сохранить граф уровней из результата MiroMarker."""
        _ensure_graphify()
        if text is None:
            pieces: list[str] = []
            for ch in result.get("chapters", []):
                for s in ch.get("sentences", []):
                    pieces.append(s.get("text", ""))
            text = " ".join(pieces)
        G = build_text_graph(text, result, ontology=ontology or self.ontology)
        communities = cluster(G)
        to_html(G, communities, str(output_path))
        return {
            "nodes": G.number_of_nodes(),
            "edges": G.number_of_edges(),
            "communities": len(communities),
        }


__all__ = [
    "MiroGraphifyExporter",
    "build_code_graph",
    "build_text_graph",
    "build_levels_graph",
    "render_graph",
    "export_graph_html",
]
