"""Тесты маркера Миросложения."""
from __future__ import annotations

from miro_vizor.exporter import MiroExporter
from miro_vizor.marker import MiroMarker
from miro_vizor.ontology import MiroOntology
from miro_vizor.tokenizer import MiroTokenizer


def test_ontology_loads() -> None:
    onto = MiroOntology.from_package()
    assert set(onto.levels_ids()) == {"L1", "L2", "L3", "L4", "L5", "L6", "L7"}
    assert onto.name("L4") == "Зелёный"


def test_token_scores_direct_match() -> None:
    onto = MiroOntology.from_package()
    marker = MiroMarker(ontology=onto, use_embeddings=False)
    scores = marker.scorer.token_scores("гармония")
    assert "L4" in scores
    assert marker.scorer.dominant(scores) == "L4"


def test_sentence_dominant() -> None:
    marker = MiroMarker(use_embeddings=False)
    result = marker.mark_text("Гармония природы требует сотрудничества всех живых систем.")
    assert result["work"]["dominant_level"] == "L4"
    assert result["sentences"][0]["dominant_level"] == "L4"
    spectrum = result["work"]["spectrum"]
    assert spectrum["L4"] > spectrum["L1"]


def test_levels_complete() -> None:
    marker = MiroMarker(use_embeddings=False)
    result = marker.mark_text("Воля и дисциплина ведут к победе.")
    assert set(result["work"]["spectrum"].keys()) == {"L1", "L2", "L3", "L4", "L5", "L6", "L7"}


def test_chapter_splitting() -> None:
    marker = MiroMarker(use_embeddings=False)
    text = "Глава 1. Введение\n\nГармония природы.\n\nГлава 2. Воля\n\nВоля и дисциплина."
    result = marker.mark_text(text)
    assert len(result["chapters"]) == 2
    assert result["chapters"][0]["title"]
    assert result["chapters"][1]["title"]


def test_exporter_json() -> None:
    marker = MiroMarker(use_embeddings=False)
    exporter = MiroExporter(ontology=marker.ontology)
    result = marker.mark_text("Гармония и воля.")
    json_out = exporter.to_json(result)
    assert '"work"' in json_out


def test_exporter_csv() -> None:
    marker = MiroMarker(use_embeddings=False)
    exporter = MiroExporter(ontology=marker.ontology)
    result = marker.mark_text("Гармония и воля.")
    csv_out = exporter.to_csv(result)
    lines = csv_out.strip().split("\n")
    assert lines[0].startswith("index")
    assert len(lines) == 2


def test_exporter_html() -> None:
    marker = MiroMarker(use_embeddings=False)
    exporter = MiroExporter(ontology=marker.ontology)
    result = marker.mark_text("Гармония и воля.")
    html_out = exporter.to_html(result, text="Гармония и воля.")
    assert "<!DOCTYPE html>" in html_out
    assert "L4" in html_out
    assert '<span class="token"' in html_out


def test_chapter_regex_multi() -> None:
    text = "Глава 1. A\n\nBody one.\n\nГлава 2. B\n\nBody two."
    tok = MiroTokenizer()
    chapters = tok.split_chapters(text)
    assert len(chapters) == 2, chapters
    assert chapters[0][0] == "Глава 1. A"
    assert chapters[1][0] == "Глава 2. B"


def test_mark_multiple_chapters() -> None:
    text = (
        "Глава 1. Гармония\n\n"
        "Гармония природы требует сотрудничества.\n\n"
        "Глава 2. Воля\n\n"
        "Воля и дисциплина ведут к победе.\n\n"
        "Глава 3. Коммуникация\n\n"
        "Язык и диалог открывают понимание."
    )
    marker = MiroMarker(use_embeddings=False)
    result = marker.mark_text(text)
    assert len(result["chapters"]) == 3, result["chapters"]
    exporter = MiroExporter(marker.ontology)
    csv_out = exporter.to_csv(result)
    assert csv_out.count("\n") == 4  # header + 3 sentences


def test_api_root() -> None:
    from fastapi.testclient import TestClient
    from miro_vizor.app_api import app

    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "Miro Marker API"


def test_api_mark_text() -> None:
    from fastapi.testclient import TestClient
    from miro_vizor.app_api import app

    client = TestClient(app)
    response = client.post(
        "/mark",
        data={"text": "Гармония природы требует сотрудничества.", "use_embeddings": "false"},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["work"]["dominant_level"] == "L4"
    assert len(result["sentences"]) == 1


def test_api_levels() -> None:
    from fastapi.testclient import TestClient
    from miro_vizor.app_api import app

    client = TestClient(app)
    response = client.get("/levels")
    assert response.status_code == 200
    levels = response.json()["levels"]
    assert len(levels) == 7
    ids = {lvl["id"] for lvl in levels}
    assert ids == {"L1", "L2", "L3", "L4", "L5", "L6", "L7"}


def test_synonyms_and_weights() -> None:
    onto = MiroOntology.from_package()
    # синоним "согласие" должен маппиться на L4
    assert "L4" in onto.matches("согласие")
    # вес синонима сохраняется
    assert onto.synonym_weight("согласие", "L4") is not None
    # базовый вес
    assert onto.weight("гармония", "L4") == 1.5


def test_custom_levels_support() -> None:
    data = MiroOntology.from_package()._data
    data["levels"]["L8"] = {
        "id": "L8",
        "name": "Test",
        "theme": "Test level",
        "color": "#000000",
        "keywords": ["testword"],
    }
    custom_onto = MiroOntology(data)
    assert "L8" in custom_onto.levels_ids()
    assert "L8" in custom_onto.matches("testword")


def test_english_language() -> None:
    onto = MiroOntology.from_package(language="en")
    assert onto.metadata.get("language") == "en"
    marker = MiroMarker(ontology=onto, use_embeddings=False, language="en")
    result = marker.mark_text("Harmony in nature requires cooperation among living systems.")
    assert result["work"]["dominant_level"] == "L4"


def test_language_detection() -> None:
    from miro_vizor.languages import detect_language

    assert detect_language("Гармония природы") == "ru"
    assert detect_language("Harmony of nature") == "en"


def test_api_mark_english() -> None:
    from fastapi.testclient import TestClient
    from miro_vizor.app_api import app

    client = TestClient(app)
    response = client.post(
        "/mark",
        data={
            "text": "Harmony in nature requires cooperation among living systems.",
            "use_embeddings": "false",
            "language": "en",
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["work"]["dominant_level"] == "L4"


def test_graphify_code_graph() -> None:
    from miro_vizor.graphify_adapter import build_code_graph, export_graph_html
    import tempfile
    from pathlib import Path

    G = build_code_graph(Path("miro_vizor"))
    assert G.number_of_nodes() > 0
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "graph.html"
        export_graph_html(G, out)
        assert out.exists()
        html = out.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in html


def test_graphify_levels_graph() -> None:
    from miro_vizor.graphify_adapter import build_levels_graph, MiroGraphifyExporter
    from miro_vizor.ontology import MiroOntology
    from miro_vizor.marker import MiroMarker
    import tempfile
    from pathlib import Path

    ontology = MiroOntology.from_package(language="ru")
    marker = MiroMarker(ontology=ontology, use_embeddings=False, language="ru")
    result = marker.mark_text("Гармония природы требует сотрудничества.")
    G = build_levels_graph(result, ontology=ontology)
    assert G.number_of_nodes() > 0

    exporter = MiroGraphifyExporter(ontology=ontology)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "levels_graph.html"
        stats = exporter.write_graph_text(result, out, ontology=ontology)
        assert out.exists()
        assert stats["nodes"] > 0


def test_api_graph_code() -> None:
    from fastapi.testclient import TestClient
    from miro_vizor.app_api import app

    client = TestClient(app)
    response = client.post(
        "/graph/code",
        data={"project_dir": "miro_vizor"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert "<!DOCTYPE html>" in response.text


def test_api_graph_text() -> None:
    from fastapi.testclient import TestClient
    from miro_vizor.app_api import app

    client = TestClient(app)
    response = client.post(
        "/graph/text",
        data={"text": "Гармония природы требует сотрудничества."},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert "<!DOCTYPE html>" in response.text
