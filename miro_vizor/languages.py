"""Мультиязычная поддержка: определение языка и лемматизация."""
from __future__ import annotations

import re
from collections import Counter
from typing import Callable

# Простая эвристика: короткие слова на латинице/кириллице
CYRILLIC_RE = re.compile(r"[а-яё]", re.IGNORECASE)
LATIN_RE = re.compile(r"[a-z]", re.IGNORECASE)


def detect_language(text: str) -> str:
    """Определить преобладающий язык текста: 'ru' или 'en'."""
    cyr = len(CYRILLIC_RE.findall(text))
    lat = len(LATIN_RE.findall(text))
    return "ru" if cyr >= lat else "en"


def identity_lemmatize(word: str) -> str:
    return word.lower().strip(".,!?;:\"'()[]«»—–-")


def build_lemmatizer(language: str) -> Callable[[str], str]:
    """Вернуть лемматизатор для языка."""
    if language == "ru":
        import pymorphy3

        morph = pymorphy3.MorphAnalyzer()

        def _lemmatize_ru(word: str) -> str:
            clean = word.lower().strip(".,!?;:\"'()[]«»—–-")
            if not clean:
                return clean
            parsed = morph.parse(clean)
            if not parsed:
                return clean
            return parsed[0].normal_form

        return _lemmatize_ru

    if language == "en":
        try:
            import simplemma

            def _lemmatize_en(word: str) -> str:
                clean = word.lower().strip(".,!?;:\"'()[]«»—–-")
                if not clean:
                    return clean
                return simplemma.lemmatize(clean, lang="en")

            return _lemmatize_en
        except Exception:  # pragma: no cover - fallback
            pass

    return identity_lemmatize
