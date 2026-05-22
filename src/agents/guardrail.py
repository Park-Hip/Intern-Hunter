from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from src.agents.types import GuardrailDecision, RefusalArtifact, RefusalCategory, RefusalCode

BAD_WORDS_PATH = Path(__file__).with_name("bad_words.txt")
MIN_BAD_WORD_LENGTH = 4


def _normalize_question(question: str) -> str:
    """Normalize user input before applying the lightweight profanity screen."""
    return " ".join(question.strip().lower().split())


@lru_cache(maxsize=1)
def _load_bad_words() -> frozenset[str]:
    """Load blocked words from the local bad-words file once per process."""
    words: set[str] = set()
    for raw_line in BAD_WORDS_PATH.read_text(encoding="utf-8").splitlines():
        word = raw_line.strip().lower()
        if word and not word.startswith("#") and len(word) >= MIN_BAD_WORD_LENGTH:
            words.add(word)
    return frozenset(words)


def _contains_bad_word(text: str) -> bool:
    """Return whether any normalized token exactly matches a blocked word."""
    tokens = re.findall(r"[a-z0-9_']+", text.lower())
    return any(token in _load_bad_words() for token in tokens)


def _block(code: RefusalCode, category: RefusalCategory, message: str) -> GuardrailDecision:
    """Build a blocked guardrail decision with the standard refusal payload."""
    return GuardrailDecision(
        allowed=False,
        refusal=RefusalArtifact(code=code, category=category, message=message),
    )


def screen_question(question: str) -> GuardrailDecision:
    """Allow all questions except requests containing blocked profanity tokens."""
    normalized = _normalize_question(question)

    if _contains_bad_word(normalized):
        return _block(
            RefusalCode.UNSUPPORTED_REQUEST,
            RefusalCategory.SENSITIVE_CONTENT,
            "I can't continue with abusive or profane requests.",
        )

    return GuardrailDecision(allowed=True)
