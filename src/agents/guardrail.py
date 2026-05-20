from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from src.agents.types import GuardrailDecision, RefusalArtifact, RefusalCategory, RefusalCode


SEXUAL_CONTENT_PATTERNS = (
    r"\bsex\b",
    r"\bsexy\b",
    r"\badult content\b",
    r"\bporn\b",
)
VIOLENCE_PATTERNS = (
    r"\bbomb\b",
    r"\bkill\b",
    r"\bweapon\b",
    r"\bshoot\b",
    r"\bwar\b",
)
PROMPT_INJECTION_PATTERNS = (
    r"ignore (all )?(previous|prior) instructions",
    r"reveal (your )?(system prompt|hidden instructions)",
    r"bypass (the )?(guardrails|safety|rules)",
    r"override (the )?(system|safety|tool) (prompt|rules|instructions)",
)
DESTRUCTIVE_SQL_PATTERNS = (
    r"\bdrop\b",
    r"\bdelete\b",
    r"\btruncate\b",
    r"\balter\b",
    r"\bupdate\b",
    r"\binsert\b",
    r"\bdisable (the )?(sql )?(guardrails|validator|safety)\b",
)

SMALL_TALK_PATTERNS = (
    r"\bhello\b",
    r"\bhi\b",
    r"\bhey\b",
    r"\bthanks\b",
    r"\bthank you\b",
    r"\bwhat can you do\b",
    r"\bhelp\b",
)
RESUME_PATTERNS = (
    r"\bresume\b",
    r"\bcv\b",
    r"\bmatch my\b",
    r"\bscore my\b",
)
JOB_SCOPE_PATTERNS = (
    r"\bjob(s)?\b",
    r"\bintern(ship|ships)?\b",
    r"\brole(s)?\b",
    r"\bclean_jobs\b",
    r"\bdatabase\b",
    r"\bsql\b",
    r"\bsalary\b",
    r"\bcity\b",
    r"\bcompany\b",
    r"\bposition\b",
)


BAD_WORDS_PATH = Path(__file__).with_name("bad_words.txt")
MIN_BAD_WORD_LENGTH = 4


def _normalize_question(question: str) -> str:
    return " ".join(question.strip().lower().split())


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


@lru_cache(maxsize=1)
def _load_bad_words() -> frozenset[str]:
    words: set[str] = set()
    for raw_line in BAD_WORDS_PATH.read_text(encoding="utf-8").splitlines():
        word = raw_line.strip().lower()
        if word and not word.startswith("#") and len(word) >= MIN_BAD_WORD_LENGTH:
            words.add(word)
    return frozenset(words)


def _contains_bad_word(text: str) -> bool:
    tokens = re.findall(r"[a-z0-9_']+", text.lower())
    return any(token in _load_bad_words() for token in tokens)


def _block(code: RefusalCode, category: RefusalCategory, message: str) -> GuardrailDecision:
    return GuardrailDecision(
        allowed=False,
        refusal=RefusalArtifact(code=code, category=category, message=message),
    )


def screen_question(question: str) -> GuardrailDecision:
    normalized = _normalize_question(question)

    if _matches_any(normalized, PROMPT_INJECTION_PATTERNS):
        return _block(
            RefusalCode.UNSUPPORTED_REQUEST,
            RefusalCategory.PROMPT_INJECTION,
            "I can't help with requests to override or reveal system, safety, or tool instructions.",
        )

    if _matches_any(normalized, DESTRUCTIVE_SQL_PATTERNS):
        return _block(
            RefusalCode.UNSAFE_SQL,
            RefusalCategory.DESTRUCTIVE_REQUEST,
            "I can only help with safe read-only database exploration requests.",
        )

    if _contains_bad_word(normalized):
        return _block(
            RefusalCode.UNSUPPORTED_REQUEST,
            RefusalCategory.SENSITIVE_CONTENT,
            "I can't continue with abusive or profane requests.",
        )

    if _matches_any(normalized, SEXUAL_CONTENT_PATTERNS):
        return _block(
            RefusalCode.UNSUPPORTED_REQUEST,
            RefusalCategory.SENSITIVE_CONTENT,
            "I can't help with sexual content requests.",
        )

    if _matches_any(normalized, VIOLENCE_PATTERNS):
        return _block(
            RefusalCode.UNSUPPORTED_REQUEST,
            RefusalCategory.SENSITIVE_CONTENT,
            "I can't help with violent, weapon, or graphic harm requests.",
        )

    if _matches_any(normalized, SMALL_TALK_PATTERNS):
        return GuardrailDecision(allowed=True)

    if _matches_any(normalized, RESUME_PATTERNS):
        return GuardrailDecision(allowed=True)

    if _matches_any(normalized, JOB_SCOPE_PATTERNS):
        return GuardrailDecision(allowed=True)

    return _block(
        RefusalCode.UNSUPPORTED_REQUEST,
        RefusalCategory.OUT_OF_SCOPE,
        "I can help with job-database questions, resume matching requests, and a small amount of related small talk.",
    )
