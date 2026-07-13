"""Тесты пользовательской веб-панели и её entry point."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from miro_vizor import app_streamlit


def test_web_main_launches_streamlit(monkeypatch):
    captured: dict[str, object] = {}

    def fake_call(command: list[str]) -> int:
        captured["command"] = command
        return 0

    monkeypatch.setattr(app_streamlit.subprocess, "call", fake_call)
    monkeypatch.setattr(sys, "argv", ["miro-vizor-web", "--server.headless=true"])

    with pytest.raises(SystemExit) as exit_info:
        app_streamlit.main()

    assert exit_info.value.code == 0
    assert captured["command"] == [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(Path(app_streamlit.__file__).resolve()),
        "--server.headless=true",
    ]
