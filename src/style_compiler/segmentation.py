"""Reproducible punctuation segmentation, not linguistic sentence recognition.

Offsets are Python Unicode code-point offsets into the unchanged input. Each
nonempty physical line is a paragraph; CRLF and blank lines retain source offsets.
Decimal points and common ASCII initials are protected, not all abbreviations.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import re
import unicodedata

SEGMENTER_VERSION = "punctuation-lines/1.0.0"
TERMINALS = frozenset("。！？!?．")
CLOSERS = frozenset('”’」』）》】〕〗〙〛"\'')


def content_chars(text: str) -> int:
    """Count Unicode letter/number code points; not words or grapheme clusters."""
    return sum(unicodedata.category(char)[0] in {"L", "N"} for char in text)


@dataclass(frozen=True)
class Span:
    index: int
    start: int
    end: int
    content_chars: int
    paragraph_index: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _is_terminal(text: str, pos: int, end: int) -> bool:
    char = text[pos]
    if char in TERMINALS:
        return True
    if char != ".":
        return False
    if pos and pos + 1 < end and text[pos - 1].isdigit() and text[pos + 1].isdigit():
        return False
    # Initials such as A. Smith and dotted abbreviations such as U.S. remain
    # a known limitation; the initial guard avoids the simplest false boundary.
    prefix = re.search(r"([A-Za-z]+)$", text[:pos])
    if prefix and len(prefix.group(1)) == 1:
        return False
    return pos + 1 == end or text[pos + 1].isspace() or text[pos + 1] in CLOSERS


def segment(text: str) -> tuple[list[Span], list[Span]]:
    paragraphs: list[Span] = []
    sentences: list[Span] = []
    for match in re.finditer(r"[^\r\n]+", text):
        start, end = _trim(text, match.start(), match.end())
        count = content_chars(text[start:end])
        if not count:
            continue
        pi = len(paragraphs)
        paragraphs.append(Span(pi, start, end, count))
        cursor = start
        pos = start
        while pos < end:
            if _is_terminal(text, pos, end):
                boundary = pos + 1
                while boundary < end and (text[boundary] in TERMINALS or text[boundary] in CLOSERS or text[boundary] == "."):
                    boundary += 1
                a, b = _trim(text, cursor, boundary)
                n = content_chars(text[a:b])
                if n:
                    sentences.append(Span(len(sentences), a, b, n, pi))
                cursor = boundary
                pos = boundary
            else:
                pos += 1
        a, b = _trim(text, cursor, end)
        n = content_chars(text[a:b])
        if n:
            sentences.append(Span(len(sentences), a, b, n, pi))
    return paragraphs, sentences
