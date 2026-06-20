"""Тесты административной панели и entry points."""
from __future__ import annotations

import json
from pathlib import Path

from miro_vizor.app_admin import _dependency_status, _load_ontology_json, _render_ontology_editor
from miro_vizor.ontology import LEVEL_FIELDS, MiroOntology


def test_level_fields_constant():
    assert "name" in LEVEL_FIELDS
    assert "weight" in LEVEL_FIELDS
    assert "synonyms" in LEVEL_FIELDS


def test_load_ontology_json(tmp_path):
    data = _load_ontology_json("ru")
    assert "levels" in data
    assert "L4" in data["levels"]


def test_dependency_status():
    assert "установлен" in _dependency_status("sys")
    assert "не установлен" in _dependency_status("nonexistent_package_12345")


def test_admin_ontology_serialization(tmp_path):
    data = _load_ontology_json("ru")
    path = tmp_path / "test_ontology.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    ontology = MiroOntology.from_file(path)
    assert len(ontology.levels) >= 7
