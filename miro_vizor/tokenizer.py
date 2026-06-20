"""Сегментация текста на токены, предложения и главы."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from .languages import detect_language


@dataclass
class Token:
    text: str
    start: int
    end: int


@dataclass
class Sentence:
    text: str
    start: int
    end: int
    tokens: list[Token]


class MiroTokenizer:
    """Токенизатор с поддержкой русского и английского.

    Попытается использовать razdel для русского, если установлен.
    """

    WORD_RE = re.compile(r"[а-яёa-z0-9]+(-[а-яёa-z0-9]+)*", re.IGNORECASE)
    SENTENCE_RE = re.compile(r"[^.!?]+[.!?]+")
    CHAPTER_RE = re.compile(
        r"(?:^|\r?\n)\s*(?:глава|chapter|раздел|часть|section|part)\s*[\dIVX]+[.:\s]?.*",
        re.IGNORECASE,
    )

    def __init__(self, language: str | None = None) -> None:
        self.language = language
        self._sentenize: Callable[[str], list[tuple[int, int]]] | None = None
        self._tokenize: Callable[[str], list[tuple[int, int]]] | None = None
        self._init_razdel()

    def _init_razdel(self) -> None:
        if self.language == "en":
            return
        try:
            from razdel import sentenize, tokenize  # type: ignore

            def _sent(text: str) -> list[tuple[int, int]]:
                return [(s.start, s.stop) for s in sentenize(text)]

            def _tok(text: str) -> list[tuple[int, int]]:
                return [(t.start, t.stop) for t in tokenize(text)]

            self._sentenize = _sent
            self._tokenize = _tok
        except Exception:  # pragma: no cover
            self._sentenize = None
            self._tokenize = None

    def _resolve_language(self, text: str) -> str:
        if self.language:
            return self.language
        return detect_language(text)

    def tokenize_words(self, text: str) -> list[Token]:
        if self._tokenize is not None:
            spans = self._tokenize(text)
            return [Token(text[start:end], start, end) for start, end in spans]
        return [
            Token(match.group(), match.start(), match.end())
            for match in self.WORD_RE.finditer(text)
        ]

    def split_sentences(self, text: str, offset: int = 0) -> list[Sentence]:
        lang = self._resolve_language(text)
        if self._sentenize is not None and lang == "ru":
            spans = self._sentenize(text)
        else:
            spans = [(m.start(), m.end()) for m in self.SENTENCE_RE.finditer(text)]
        sentences: list[Sentence] = []
        for start, end in spans:
            sent_text = text[start:end]
            tokens = self.tokenize_words(sent_text)
            sentences.append(
                Sentence(sent_text, start + offset, end + offset, tokens)
            )
        return sentences

    def split_chapters(self, text: str) -> list[tuple[str, str]]:
        """Разбить текст на главы по заголовкам.

        Возвращает список (заголовок, содержимое).
        """
        matches = list(self.CHAPTER_RE.finditer(text))
        if not matches:
            return [("", text)]
        chapters: list[tuple[str, str]] = []
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            header = text[start:match.end()].strip()
            body = text[match.end():end].strip()
            chapters.append((header, body))
        return chapters
