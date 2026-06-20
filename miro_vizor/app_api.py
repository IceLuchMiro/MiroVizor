"""FastAPI API для массовой маркировки текстов и визуализации графов."""
from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from .exporter import MiroExporter
from .graphify_adapter import MiroGraphifyExporter
from .marker import MiroMarker
from .ontology import MiroOntology

app = FastAPI(title="Miro Marker API", version="0.5.0")


def _get_ontology(language: str | None = None) -> MiroOntology:
    return MiroOntology.from_package(language=language)


def _get_marker(use_embeddings: bool = True, language: str | None = None) -> MiroMarker:
    return MiroMarker(
        ontology=_get_ontology(language),
        use_embeddings=use_embeddings,
        language=language,
    )


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "Miro Marker API", "version": "0.5.0"}


@app.get("/levels")
def list_levels(language: str | None = None) -> dict[str, Any]:
    ontology = _get_ontology(language)
    return {
        "levels": [
            {
                "id": level_id,
                "name": level_data.get("name", level_id),
                "color": level_data.get("color", "#000000"),
                "theme": level_data.get("theme", ""),
            }
            for level_id, level_data in ontology.levels.items()
        ]
    }


@app.post("/mark")
def mark_text(
    text: str = Form(...),
    title: str = Form("input"),
    use_embeddings: bool = Form(True),
    language: str | None = Form(None),
) -> dict[str, Any]:
    marker = _get_marker(use_embeddings=use_embeddings, language=language)
    return marker.mark_text(text, title=title)


@app.post("/mark/json")
def mark_text_json(
    text: str = Form(...),
    title: str = Form("input"),
    use_embeddings: bool = Form(True),
    language: str | None = Form(None),
) -> JSONResponse:
    marker = _get_marker(use_embeddings=use_embeddings, language=language)
    result = marker.mark_text(text, title=title)
    return JSONResponse(content=result)


@app.post("/mark/html")
def mark_text_html(
    text: str = Form(...),
    title: str = Form("input"),
    use_embeddings: bool = Form(True),
    language: str | None = Form(None),
) -> FileResponse:
    marker = _get_marker(use_embeddings=use_embeddings, language=language)
    ontology = marker.ontology
    result = marker.mark_text(text, title=title)
    exporter = MiroExporter(ontology=ontology)
    html = exporter.to_html(result, text=text, title=title)
    with NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html)
        path = Path(f.name)
    return FileResponse(path, media_type="text/html", filename=f"{title}.html")


@app.post("/mark/csv")
def mark_text_csv(
    text: str = Form(...),
    title: str = Form("input"),
    use_embeddings: bool = Form(True),
    language: str | None = Form(None),
) -> FileResponse:
    marker = _get_marker(use_embeddings=use_embeddings, language=language)
    ontology = marker.ontology
    result = marker.mark_text(text, title=title)
    exporter = MiroExporter(ontology=ontology)
    csv_text = exporter.to_csv(result)
    with NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(csv_text)
        path = Path(f.name)
    return FileResponse(path, media_type="text/csv", filename=f"{title}.csv")


@app.post("/mark/file")
async def mark_file(
    file: UploadFile = File(...),
    use_embeddings: bool = Form(True),
    language: str | None = Form(None),
) -> JSONResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл не передан")
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Файл должен быть в UTF-8") from exc

    marker = _get_marker(use_embeddings=use_embeddings, language=language)
    result = marker.mark_text(text, title=file.filename)
    return JSONResponse(content=result)


# ---------------------------------------------------------------------------
# Graphify endpoints
# ---------------------------------------------------------------------------

@app.post("/graph/code")
def graph_code(
    project_dir: str = Form(...),
    use_embeddings: bool = Form(True),
    language: str | None = Form(None),
) -> FileResponse:
    """Build an interactive HTML graph from Python code in *project_dir*."""
    path = Path(project_dir)
    if not path.is_dir():
        raise HTTPException(status_code=400, detail="Указанный путь не является директорией")
    ontology = _get_ontology(language)
    graph_exporter = MiroGraphifyExporter(ontology=ontology)
    with NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        out_path = Path(f.name)
    stats = graph_exporter.write_graph_code(path, out_path)
    response = FileResponse(out_path, media_type="text/html", filename="graph.html")
    response.headers["X-Graph-Stats"] = str(stats)
    return response


@app.post("/graph/text")
def graph_text(
    text: str = Form(...),
    title: str = Form("input"),
    use_embeddings: bool = Form(True),
    language: str | None = Form(None),
) -> FileResponse:
    """Build an interactive HTML graph from a marked text."""
    marker = _get_marker(use_embeddings=use_embeddings, language=language)
    ontology = marker.ontology
    result = marker.mark_text(text, title=title)
    graph_exporter = MiroGraphifyExporter(ontology=ontology)
    with NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        out_path = Path(f.name)
    stats = graph_exporter.write_graph_text(result, out_path, ontology=ontology)
    response = FileResponse(out_path, media_type="text/html", filename="graph.html")
    response.headers["X-Graph-Stats"] = str(stats)
    return response
