"""МироВизор — административная панель управления miro_vizor."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

import streamlit as st

from . import __version__
from .exporter import MiroExporter
from .languages import detect_language
from .marker import MiroMarker
from .ontology import LEVEL_COLORS, LEVEL_FIELDS, MiroOntology


def _ontology_path(language: str) -> Path:
    pkg = Path(__file__).parent
    candidates = [
        pkg / ("miro_ontology_en.json" if language == "en" else "miro_ontology.json"),
        pkg.parent / ("miro_ontology_en.json" if language == "en" else "miro_ontology.json"),
    ]
    for path in candidates:
        if path.exists():
            return path
    # fallback: create in package directory if missing
    return candidates[0]


def _load_ontology_json(language: str) -> dict[str, Any]:
    path = _ontology_path(language)
    return json.loads(path.read_text(encoding="utf-8"))


def _save_ontology_json(language: str, data: dict[str, Any]) -> Path:
    path = _ontology_path(language)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _dependency_status(name: str) -> str:
    try:
        __import__(name)
        return "✅ установлен"
    except ImportError:
        return "❌ не установлен"


def _ensure_session_state() -> None:
    st.session_state.setdefault("admin_tab", "Онтология")
    st.session_state.setdefault("ontology_dirty", False)
    st.session_state.setdefault("custom_json", "")


def _render_ontology_editor() -> None:
    st.subheader("Редактор онтологии")
    language = st.selectbox("Язык онтологии", options=["ru", "en"], index=0, key="admin_lang")

    data = _load_ontology_json(language)
    levels: dict[str, Any] = data.get("levels", {})

    # ------------------------------------------------------------------
    # Level selector
    # ------------------------------------------------------------------
    level_ids = list(levels.keys()) or ["L1"]
    selected_level = st.selectbox("Уровень", options=level_ids, key="admin_level")
    level = levels.get(selected_level, {})

    # ------------------------------------------------------------------
    # Basic fields
    # ------------------------------------------------------------------
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Название", value=level.get("name", ""), key=f"{selected_level}_name")
    with col2:
        weight = st.number_input(
            "Базовый вес уровня",
            value=float(level.get("weight", 1.0)),
            min_value=0.0,
            max_value=10.0,
            step=0.1,
            key=f"{selected_level}_weight",
        )
    description = st.text_area(
        "Описание",
        value=level.get("description", ""),
        height=100,
        key=f"{selected_level}_desc",
    )

    # ------------------------------------------------------------------
    # Keywords
    # ------------------------------------------------------------------
    st.markdown("**Ключевые слова** (через запятую)")
    keywords = ", ".join(level.get("keywords", []))
    keywords_str = st.text_input("keywords", value=keywords, key=f"{selected_level}_keywords")

    # ------------------------------------------------------------------
    # Synonyms
    # ------------------------------------------------------------------
    st.markdown("**Синонимы** (JSON-объект `{term: [synonym, ...]}`)")
    synonyms = level.get("synonyms", {})
    synonyms_str = st.text_area(
        "synonyms",
        value=json.dumps(synonyms, ensure_ascii=False, indent=2) if synonyms else "{}",
        height=120,
        key=f"{selected_level}_synonyms",
    )

    # ------------------------------------------------------------------
    # Weights
    # ------------------------------------------------------------------
    st.markdown("**Веса терминов** (JSON-объект `{term: weight}`)")
    term_weights = level.get("term_weights", {})
    term_weights_str = st.text_area(
        "term_weights",
        value=json.dumps(term_weights, ensure_ascii=False, indent=2) if term_weights else "{}",
        height=120,
        key=f"{selected_level}_term_weights",
    )

    st.markdown("**Веса категорий** (JSON-объект `{category: weight}`)")
    category_weights = level.get("category_weights", {})
    category_weights_str = st.text_area(
        "category_weights",
        value=json.dumps(category_weights, ensure_ascii=False, indent=2) if category_weights else "{}",
        height=120,
        key=f"{selected_level}_category_weights",
    )

    # ------------------------------------------------------------------
    # Custom levels management
    # ------------------------------------------------------------------
    st.divider()
    st.subheader("Пользовательские уровни")
    new_level_id = st.text_input(
        "ID нового уровня (например, L8)",
        placeholder="L8",
        key="new_level_id",
    )
    if st.button("Добавить уровень", key="btn_add_level"):
        if new_level_id and new_level_id not in levels:
            levels[new_level_id] = {
                "id": new_level_id,
                "name": f"Уровень {new_level_id}",
                "description": "",
                "color": LEVEL_COLORS.get(new_level_id, "#000000"),
                "keywords": [],
                "weight": 1.0,
                "synonyms": {},
                "term_weights": {},
                "category_weights": {},
            }
            data["levels"] = levels
            _save_ontology_json(language, data)
            st.success(f"Уровень {new_level_id} добавлен")
            st.rerun()
        else:
            st.error("Укажите уникальный ID уровня")

    if selected_level.startswith("L") and int(selected_level[1:]) > 7:
        if st.button("Удалить выбранный уровень", key="btn_del_level"):
            del levels[selected_level]
            data["levels"] = levels
            _save_ontology_json(language, data)
            st.success(f"Уровень {selected_level} удалён")
            st.rerun()

    # ------------------------------------------------------------------
    # Save changes
    # ------------------------------------------------------------------
    st.divider()
    if st.button("💾 Сохранить изменения", key="btn_save_ontology"):
        try:
            synonyms_parsed = json.loads(synonyms_str or "{}")
            term_weights_parsed = json.loads(term_weights_str or "{}")
            category_weights_parsed = json.loads(category_weights_str or "{}")
        except json.JSONDecodeError as exc:
            st.error(f"Ошибка JSON: {exc}")
            return

        levels[selected_level] = {
            "id": selected_level,
            "name": name,
            "description": description,
            "weight": weight,
            "color": LEVEL_COLORS.get(selected_level) or level.get("color", "#000000"),
            "keywords": [kw.strip() for kw in keywords_str.split(",") if kw.strip()],
            "synonyms": synonyms_parsed,
            "term_weights": term_weights_parsed,
            "category_weights": category_weights_parsed,
        }
        data["levels"] = levels

        # Validate structure
        for lvl_id, lvl_data in levels.items():
            for field in LEVEL_FIELDS:
                lvl_data.setdefault(field, [] if field == "keywords" else (1.0 if field == "weight" else ""))

        saved_path = _save_ontology_json(language, data)
        st.success(f"Онтология сохранена: {saved_path}")
        st.session_state["ontology_dirty"] = True

    # ------------------------------------------------------------------
    # Upload / download
    # ------------------------------------------------------------------
    st.divider()
    col_up, col_down = st.columns(2)
    with col_up:
        uploaded = st.file_uploader("Загрузить онтологию JSON", type="json", key="upload_ontology")
        if uploaded is not None:
            try:
                uploaded_data = json.loads(uploaded.read().decode("utf-8"))
                data = uploaded_data
                _save_ontology_json(language, data)
                st.success("Онтология загружена")
                st.session_state["ontology_dirty"] = True
                st.rerun()
            except Exception as exc:
                st.error(f"Ошибка загрузки: {exc}")
    with col_down:
        st.download_button(
            "Скачать текущую онтологию",
            data=json.dumps(data, ensure_ascii=False, indent=2),
            file_name=f"miro_ontology_{language}.json",
            mime="application/json",
            key="download_ontology",
        )


def _render_run_panel() -> None:
    st.subheader("Запуск разметки")
    language = st.selectbox("Язык", options=["auto", "ru", "en"], index=0, key="run_lang")
    selected_language = None if language == "auto" else language
    use_embeddings = st.checkbox("Векторная семантика", value=True, key="run_embeddings")
    ontology_language = selected_language or detect_language("") or "ru"

    text = st.text_area(
        "Текст для разметки",
        height=250,
        value="Глава 1. Гармония\n\nГармония природы требует сотрудничества.",
        key="run_text",
    )

    if st.button("Разметить", key="btn_admin_run"):
        with st.spinner("Анализирую..."):
            ontology = MiroOntology.from_package(language=ontology_language)
            marker = MiroMarker(
                ontology=ontology,
                use_embeddings=use_embeddings,
                language=selected_language,
            )
            result = marker.mark_text(text, title="admin_run")
        exporter = MiroExporter(ontology=ontology)
        st.json(result["work"], expanded=True)
        st.download_button(
            "Скачать JSON",
            data=json.dumps(result, ensure_ascii=False, indent=2),
            file_name="admin_result.json",
            mime="application/json",
            key="download_admin_result",
        )
        html = exporter.to_html(result, text=text, title="admin_run")
        st.download_button(
            "Скачать HTML",
            data=html,
            file_name="admin_result.html",
            mime="text/html",
            key="download_admin_html",
        )


def _miro_processes() -> list[tuple[int, str]]:
    """Возвращает процессы МироВизора, исключая текущий процесс админки."""
    current_pid = os.getpid()
    processes: list[tuple[int, str]] = []

    if os.name == "nt":
        command = (
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.Name -match 'miro-vizor-(web|admin)\\.exe' "
            "-or $_.CommandLine -match 'miro-vizor-(web|admin)|app_streamlit\\.py|app_admin\\.py' } | "
            "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress"
        )
        try:
            raw = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", command],
                text=True,
                encoding="utf-8",
                errors="replace",
            ).strip()
            if not raw:
                return processes
            records = json.loads(raw)
            if isinstance(records, dict):
                records = [records]
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            return processes
        for record in records:
            pid = record.get("ProcessId")
            if not isinstance(pid, int) or pid == current_pid:
                continue
            name = record.get("Name") or "python.exe"
            command_line = record.get("CommandLine") or name
            processes.append((pid, command_line))
        return processes

    try:
        output = subprocess.check_output(["ps", "-eo", "pid=,args="], text=True)
    except (OSError, subprocess.SubprocessError):
        return processes
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        pid_text, _, command_text = line.partition(" ")
        if not pid_text.isdigit() or int(pid_text) == current_pid:
            continue
        if any(marker in command_text for marker in ("miro-vizor-web", "miro-vizor-admin", "app_streamlit.py", "app_admin.py")):
            processes.append((int(pid_text), command_text))
    return processes


def _stop_miro_processes(processes: list[tuple[int, str]]) -> list[int]:
    """Останавливает только переданные процессы и возвращает PID с ошибками."""
    failed: list[int] = []
    for pid, _ in processes:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=True, capture_output=True, text=True)
            else:
                os.kill(pid, signal.SIGTERM)
        except (OSError, subprocess.SubprocessError):
            failed.append(pid)
    return failed


def _render_process_control() -> None:
    st.subheader("Управление процессами")
    st.caption("Кнопка останавливает веб-панель и другие процессы МироВизора, но не текущую админ-панель.")
    processes = _miro_processes()
    if processes:
        st.write("Найдены процессы:")
        st.table([{"PID": pid, "Процесс": name} for pid, name in processes])
    else:
        st.info("Других процессов МироВизора не найдено.")

    confirm = st.checkbox("Подтверждаю остановку процессов", key="confirm_stop_miro")
    if st.button("⛔ Остановить процессы МироВизора", type="secondary", key="btn_stop_miro"):
        if not confirm:
            st.warning("Сначала подтвердите остановку процессов.")
            return
        failed = _stop_miro_processes(processes)
        if failed:
            st.error(f"Не удалось остановить PID: {', '.join(map(str, failed))}")
        elif processes:
            st.success("Процессы МироВизора остановлены.")
        else:
            st.info("Активных процессов для остановки не было.")
        st.rerun()


def _render_command_help() -> None:
    st.subheader("Команды управления")
    st.caption("Запускайте команды в PowerShell или CMD из корня проекта.")
    st.code(
        """# Установить/обновить пакет и команды
python -m pip install -e .[web]

# Запустить веб-панель
miro-vizor-web

# Запустить админ-панель
miro-vizor-admin

# Запустить на конкретном порту
miro-vizor-web --server.port 8501

# Проверить процессы МироВизора
Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'miro-vizor' -or $_.CommandLine -match 'app_streamlit.py|app_admin.py|streamlit' } | Select-Object ProcessId,Name,CommandLine

# Завершить веб-панель по PID вместе с дочерними процессами
taskkill /F /T /PID <PID>

# Проверить занятый порт
Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue
""",
        language="powershell",
    )


def _render_system_info() -> None:
    st.subheader("Системная информация")
    _render_process_control()
    st.divider()
    _render_command_help()
    st.divider()
    st.write(f"**Версия пакета:** `{__version__}`")
    st.write(f"**Python:** `{sys.version}`")
    st.write(f"**Корень проекта:** `{Path(__file__).parent.resolve()}`")

    st.markdown("**Зависимости**")
    st.table(
        [
            {"Компонент": "numpy", "Статус": _dependency_status("numpy")},
            {"Компонент": "scikit-learn", "Статус": _dependency_status("sklearn")},
            {"Компонент": "sentence-transformers", "Статус": _dependency_status("sentence_transformers")},
            {"Компонент": "streamlit", "Статус": _dependency_status("streamlit")},
            {"Компонент": "fastapi", "Статус": _dependency_status("fastapi")},
            {"Компонент": "simplemma", "Статус": _dependency_status("simplemma")},
            {"Компонент": "tree-sitter", "Статус": _dependency_status("tree_sitter")},
            {"Компонент": "graphify (vendor)", "Статус": _dependency_status("graphify")},
        ]
    )

    if st.button("🧪 Запустить тесты", key="btn_run_tests"):
        import subprocess

        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "tests", "-v", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            st.code(proc.stdout + proc.stderr, language="bash")
            if proc.returncode == 0:
                st.success("Все тесты прошли")
            else:
                st.error(f"Тесты завершились с кодом {proc.returncode}")
        except Exception as exc:
            st.error(f"Ошибка запуска тестов: {exc}")


def run() -> None:
    st.set_page_config(page_title="МироВизор — Админка", page_icon="🛠️", layout="wide")
    st.markdown(
        """
        <style>
        html, body, [class*="css"] {
            font-size: 18px;
        }
        h1 { font-size: 2.2em; }
        h2 { font-size: 1.7em; }
        h3 { font-size: 1.35em; }
        .stButton>button { font-size: 18px; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("🛠️ МироВизор — административная панель")

    _ensure_session_state()

    tab_names = ["📚 Онтология", "▶️ Запуск разметки", "ℹ️ Система"]
    tabs = st.tabs(tab_names)

    with tabs[0]:
        _render_ontology_editor()
    with tabs[1]:
        _render_run_panel()
    with tabs[2]:
        _render_system_info()


if __name__ == "__main__":
    run()
