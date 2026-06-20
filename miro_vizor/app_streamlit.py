"""Streamlit-приложение для маркировки текстов и визуализации графов."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile

import streamlit as st

from .exporter import MiroExporter
from .graphify_adapter import MiroGraphifyExporter
from .marker import MiroMarker
from .ontology import MiroOntology


def run() -> None:
    st.set_page_config(page_title="МироВизор", page_icon="🌈", layout="wide")
    st.markdown(
        """
        <style>
        html, body, [class*="css"] {
            font-size: 18px;
        }
        h1 { font-size: 2.4em; }
        h2 { font-size: 1.8em; }
        h3 { font-size: 1.4em; }
        .stButton>button { font-size: 18px; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("🌈 МироВизор — маркировка знаний по 7 уровням Миросложения")

    with st.sidebar:
        st.header("Настройки")
        use_embeddings = st.checkbox("Использовать векторную семантику", value=True)
        language = st.selectbox(
            "Язык",
            options=["auto", "ru", "en"],
            index=0,
            help="auto — определять по тексту автоматически",
        )
        selected_language = None if language == "auto" else language

    tab_text, tab_graph_text, tab_graph_code = st.tabs(
        ["📝 Разметка текста", "🕸️ Граф уровней", "🕸️ Граф кода"]
    )

    ontology = MiroOntology.from_package(language=selected_language)
    exporter = MiroExporter(ontology=ontology)
    graph_exporter = MiroGraphifyExporter(ontology=ontology)

    # ------------------------------------------------------------------
    # Tab 1: text marking
    # ------------------------------------------------------------------
    with tab_text:
        text = st.text_area(
            "Вставьте текст",
            height=300,
            value="Глава 1. Гармония\n\nГармония природы требует сотрудничества всех живых систем.",
        )

        show_html = st.checkbox("Показать цветную HTML-разметку", value=True, key="show_html")
        show_csv = st.checkbox("Показать CSV по предложениям", value=False, key="show_csv")
        show_tokens = st.checkbox("Показать токены", value=False, key="show_tokens")

        if st.button("Разметить", key="btn_mark"):
            with st.spinner("Анализирую..."):
                marker = MiroMarker(
                    ontology=ontology,
                    use_embeddings=use_embeddings,
                    language=selected_language,
                )
                result = marker.mark_text(text, title="streamlit_input")

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Спектр труда")
                work = result["work"]
                st.json(work, expanded=True)
                st.write(f"**Доминирующий уровень:** {work['dominant_level']}")
            with col2:
                st.subheader("Распределение по главам")
                for ch in result["chapters"]:
                    st.write(
                        f"Глава {ch['index']}: **{ch['title'] or '<без названия>'}** — "
                        f"{ch['dominant_level']}"
                    )

            if show_html:
                st.subheader("Цветная разметка")
                html = exporter.to_html(result, text=text, title="streamlit_input")
                st.components.v1.html(html, height=400, scrolling=True)

            if show_csv:
                st.subheader("CSV по предложениям")
                csv_text = exporter.to_csv(result)
                st.code(csv_text, language="csv")

            if show_tokens:
                st.subheader("Токены")
                st.json(result["sentences"], expanded=False)

            st.download_button(
                "Скачать JSON",
                data=json.dumps(result, ensure_ascii=False, indent=2),
                file_name="miro_result.json",
                mime="application/json",
            )

            html_full = exporter.to_html(result, text=text, title="streamlit_input")
            st.download_button(
                "Скачать HTML",
                data=html_full,
                file_name="miro_result.html",
                mime="text/html",
            )

    # ------------------------------------------------------------------
    # Tab 2: graph from marked text
    # ------------------------------------------------------------------
    with tab_graph_text:
        graph_text = st.text_area(
            "Текст для графа",
            height=250,
            value="Глава 1. Гармония\n\nГармония природы требует сотрудничества. Воля человека направляет поступки.",
            key="graph_text_area",
        )
        if st.button("Построить граф уровней", key="btn_graph_text"):
            with st.spinner("Строю граф..."):
                marker = MiroMarker(
                    ontology=ontology,
                    use_embeddings=use_embeddings,
                    language=selected_language,
                )
                result = marker.mark_text(graph_text, title="streamlit_graph")
                with NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
                    out_path = Path(f.name)
                stats = graph_exporter.write_graph_text(result, out_path, ontology=ontology)
                html_content = out_path.read_text(encoding="utf-8")
            st.write(
                f"Узлов: {stats['nodes']}, рёбер: {stats['edges']}, сообществ: {stats['communities']}"
            )
            st.components.v1.html(html_content, height=600, scrolling=True)
            st.download_button(
                "Скачать граф (HTML)",
                data=html_content,
                file_name="miro_levels_graph.html",
                mime="text/html",
            )

    # ------------------------------------------------------------------
    # Tab 3: graph from code
    # ------------------------------------------------------------------
    with tab_graph_code:
        code_dir = st.text_input(
            "Директория с Python-кодом",
            value=str(Path.cwd() / "miro_vizor"),
            key="code_dir",
        )
        if st.button("Построить граф кода", key="btn_graph_code"):
            path = Path(code_dir)
            if not path.is_dir():
                st.error("Указанный путь не является директорией")
            else:
                with st.spinner("Парсинг кода..."):
                    with NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
                        out_path = Path(f.name)
                    stats = graph_exporter.write_graph_code(path, out_path)
                    html_content = out_path.read_text(encoding="utf-8")
                st.write(
                    f"Узлов: {stats['nodes']}, рёбер: {stats['edges']}, сообществ: {stats['communities']}"
                )
                st.components.v1.html(html_content, height=600, scrolling=True)
                st.download_button(
                    "Скачать граф кода (HTML)",
                    data=html_content,
                    file_name="miro_code_graph.html",
                    mime="text/html",
                )


if __name__ == "__main__":
    run()
