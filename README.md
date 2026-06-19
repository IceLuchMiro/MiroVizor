# miro_marker

Инструмент автоматической маркировки текстовых фрагментов по 7 уровням Миросложения.

## Установка

```bash
pip install -e .

# или с веб-интерфейсом, векторной семантикой и графами
pip install -e ".[all]"
```

## Использование

```python
from miro_marker import MiroMarker

marker = MiroMarker()
result = marker.mark_text("Гармония природы требует сотрудничества всех живых систем.")
print(result["work"]["dominant_level"])  # L4
```

## Экспорт

```python
from miro_marker import MiroMarker
from miro_marker.exporter import MiroExporter

marker = MiroMarker()
result = marker.mark_text(text)
exporter = MiroExporter()

exporter.write_json(result, "result.json")
exporter.write_csv(result, "result.csv")
exporter.write_html(result, "result.html", text=text, title="Мой труд")
```

## CLI

```bash
# базовый JSON
python -m miro_marker.cli sample.txt -o result.json

# с векторной семантикой (по умолчанию включена)
python -m miro_marker.cli sample.txt -o result.json

# только прямое совпадение
python -m miro_marker.cli sample.txt --no-embeddings -o result.json

# экспорт цветной HTML-разметки и CSV
python -m miro_marker.cli sample.txt --html result.html --csv result.csv -o result.json

# английский язык
python -m miro_marker.cli sample_en.txt --language en --no-embeddings -o result.json
```

## Веб-интерфейс МироВизор (Streamlit)

```bash
pip install -e ".[web]"
miro-marker-web
# или
streamlit run miro_marker/app_streamlit.py
```

В браузере откроется панель **МироВизор**: вставьте текст, нажмите «Разметить», получите спектр, HTML-разметку, графы и ссылки на скачивание JSON/HTML.

## API (FastAPI)

```bash
pip install -e ".[web]"
uvicorn miro_marker.app_api:app --reload --host 0.0.0.0 --port 8000
```

Примеры запросов:

```bash
curl -X POST "http://localhost:8000/mark" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "text=Гармония природы требует сотрудничества."

# скачать HTML
curl -X POST "http://localhost:8000/mark/html" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "text=Гармония природы требует сотрудничества." \
  --output result.html

# загрузить файл
curl -X POST "http://localhost:8000/mark/file" \
  -F "file=@sample.txt" \
  -F "use_embeddings=true"

# английский язык
curl -X POST "http://localhost:8000/mark" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "text=Harmony in nature requires cooperation." \
  -d "language=en" \
  -d "use_embeddings=false"
```

## Расширенная онтология

`miro_ontology.json` поддерживает:

- `synonyms` — синонимы ключевых терминов (`{"гармония": ["согласие", "лад"]}`)
- `term_weights` — веса отдельных ключевых слов
- `category_weights` — веса целых категорий
- `weight` — базовый вес уровня
- `custom_levels` — пользовательские уровни (L8+), добавляемые в тот же JSON

## Мультиязычность

- Автоопределение языка (`ru` / `en`) по преобладанию кириллицы/латиницы.
- Английская онтология — `miro_ontology_en.json`.
- Для лемматизации английских слов используется `simplemma`.

```bash
pip install -e ".[multilang]"
```

## Установка graphify-зависимостей

Для построения графов кода установите tree-sitter:

```bash
pip install -e ".[graph]"
```

## Графовая визуализация (graphify)

`miro_marker` включает vendored-версию [graphify](https://github.com/safishamsi/graphify) для построения интерактивных графов:

- **Граф кода** — структура Python-проекта (файлы, классы, функции, импорты).
- **Граф уровней** — семантический глосс из результата маркировки (главы → предложения → уровни Миросложения).

### CLI

```bash
# граф Python-кода проекта
python -m miro_marker.cli sample.txt --graph-code miro_marker --graph-output graph.html

# граф уровней из размеченного текста
python -m miro_marker.cli sample.txt --graph-text --graph-output graph.html
```

После выполнения откройте `graph.html` в браузере — интерактивный vis.js граф с поиском, фильтром сообществ и информационной панелью.

### API

```bash
curl -X POST "http://localhost:8000/graph/code" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "project_dir=miro_marker" \
  --output graph.html

curl -X POST "http://localhost:8000/graph/text" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "text=Гармония природы требует сотрудничества." \
  --output graph.html
```

### Streamlit

Во вкладках **🕸️ Граф уровней** и **🕸️ Граф кода** можно построить и скачать граф прямо из браузера.

### Python

```python
from miro_marker import build_code_graph, build_levels_graph, MiroMarker
from miro_marker.graphify_adapter import export_graph_html

# граф кода
G = build_code_graph("miro_marker")
export_graph_html(G, "code_graph.html")

# граф уровней
result = MiroMarker().mark_text("Гармония природы требует сотрудничества.")
G2 = build_levels_graph(result)
export_graph_html(G2, "levels_graph.html")
```

## МироВизор — административная панель

Полноценная админка для управления онтологиями и системными операциями:

```bash
pip install -e ".[web]"
miro-marker-admin
# или
streamlit run miro_marker/app_admin.py
```

Возможности:
- **📚 Онтология** — редактирование уровней, ключевых слов, синонимов и весов; добавление пользовательских уровней (L8+); загрузка/скачивание JSON.
- **▶️ Запуск разметки** — разметить текст выбранной онтологией и скачать JSON/HTML.
- **ℹ️ Система** — версия, статус зависимостей, запуск тестов.

*[graphify](https://github.com/safishamsi/graphify) интегрирован как vendored-зависимость.*

## Структура

- `ontology.py` — загрузка `miro_ontology.json`, индекс синонимов и весов
- `languages.py` — определение языка и выбор лемматизатора
- `tokenizer.py` — разбиение на токены/предложения/главы (ru/en)
- `scorer.py` — прямое совпадение с учётом весов + гибридный score с эмбеддингами
- `embedder.py` — векторная семантика (sentence-transformers + fallback)
- `marker.py` — агрегация труда → глав → предложений → токенов
- `exporter.py` — экспорт в JSON, CSV, цветной HTML
- `graphify_adapter.py` — интеграция graphify: графы кода и уровней
- `cli.py` — командная строка
- `app_streamlit.py` — веб-интерфейс
- `app_admin.py` — административная панель
- `app_api.py` — FastAPI API
# MiroVizor  
