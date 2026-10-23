"""
LocalSub - Filler Words and Vocalization Filter.
Identifies, cleans, or discards non-speech vocalizations and filler expressions
frequently occurring in adult films, moans, or repetitive audio artifacts
(e.g., 'oh my god', 'oh yeah', 'yes', 'no', 'ah', 'ahh', 'mmm', 'fuck').
"""

from __future__ import annotations

import re
from typing import List

from app.core.types import SubtitleSegment

# Comprehensive list of adult and dialogue vocalization / filler phrases
FILLER_PHRASES: List[str] = [
    # Multi-word compound expressions
    r"oh\s+my\s+god",
    r"oh\s+my\s+gosh",
    r"oh\s+god",
    r"my\s+god",
    r"oh\s+my",
    r"oh\s+yes+",
    r"oh\s+yeah+",
    r"oh\s+no+",
    r"oh\s+fuck+",
    r"fuck\s+yeah+",
    r"holy\s+fuck+",
    r"holy\s+shit+",
    r"uh\s+huh",
    r"mm+\s+hmm+",
    r"ah+\s+yes+",
    r"ah+\s+yeah+",
    # Single vocalizations and interjections with character repetitions
    r"oh+",
    r"a+h+",
    r"o+h+h*",
    r"o+o+h+",
    r"u+h+",
    r"u+m+",
    r"m+h+m+",
    r"h+m+m*",
    r"m+m+",
    r"yes+",
    r"no+",
    r"yeah+",
    r"yep",
    r"nope",
    r"fuck+",
    r"fucking",
    r"ugh+",
    r"whoa+",
    r"woah+",
]

_COMBINED_FILLERS = "|".join(FILLER_PHRASES)
_WORD_BOUNDARY_PATTERN = re.compile(rf"\b({_COMBINED_FILLERS})\b", re.IGNORECASE)
_PUNCT_PATTERN = re.compile(r"[\s\.,!\?'\"\-_:;~]+")

_LEADING_PATTERN = re.compile(
    rf"^(?:[\s\.,!\?'\"\-_:;~]*(?:\b(?:{_COMBINED_FILLERS})\b)[\s\.,!\?'\"\-_:;~]*)+",
    re.IGNORECASE,
)
_TRAILING_PATTERN = re.compile(
    rf"(?:[\s\.,!\?'\"\-_:;~]+(?:\b(?:{_COMBINED_FILLERS})\b)[\s\.,!\?'\"\-_:;~]*)+$",
    re.IGNORECASE,
)


def is_pure_filler(text: str) -> bool:
    """
    Check if a text consists ENTIRELY of filler words/sounds and punctuation.
    Returns True if no substantive words remain.
    """
    if not text or not text.strip():
        return True
    cleaned = _WORD_BOUNDARY_PATTERN.sub("", text)
    cleaned_no_punct = _PUNCT_PATTERN.sub("", cleaned)
    return len(cleaned_no_punct) == 0


def clean_sentence_fillers(text: str) -> str:
    """
    Clean leading and trailing filler phrases from a sentence while preserving
    substantive dialogue. If the entire sentence is pure filler, returns an empty string.
    """
    cleaned = text.strip()
    if is_pure_filler(cleaned):
        return ""

    cleaned = _LEADING_PATTERN.sub("", cleaned).strip()
    cleaned = _TRAILING_PATTERN.sub("", cleaned).strip()

    # Strip any remaining leading punctuation
    cleaned = re.sub(r"^[\s,\.\?!;:-]+", "", cleaned).strip()
    # Strip any dangling trailing commas or hyphens
    cleaned = re.sub(r"[\s,:-]+$", "", cleaned).strip()
    if not cleaned:
        return ""

    # Ensure proper capitalization of the cleaned sentence
    return cleaned[0].upper() + cleaned[1:] if len(cleaned) > 1 else cleaned.upper()


def filter_filler_segments(segments: List[SubtitleSegment]) -> List[SubtitleSegment]:
    """
    Filter a list of SubtitleSegment instances:
    1. Removes segments that consist purely of filler/groan words.
    2. Cleans leading and trailing filler vocalizations from remaining dialogue segments.
    3. Re-indexes remaining segments sequentially starting from 1.
    """
    filtered: List[SubtitleSegment] = []
    current_index = 1

    for seg in segments:
        cleaned_text = clean_sentence_fillers(seg.text)
        if not cleaned_text:
            continue

        filtered.append(
            SubtitleSegment(
                index=current_index,
                start=seg.start,
                end=seg.end,
                text=cleaned_text,
                words=seg.words,
            )
        )
        current_index += 1

    return filtered
