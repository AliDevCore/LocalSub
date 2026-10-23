"""
Tests for Filler Words and Vocalization Filter and English Whisper Models.
"""

import pytest
from app.core.filler_filter import (
    clean_sentence_fillers,
    filter_filler_segments,
    is_pure_filler,
)
from app.core.types import SubtitleSegment, WhisperModelSize
from app.services.model_manager import WHISPER_REGISTRY


def test_pure_filler_detection():
    # Vocalizations and moans
    assert is_pure_filler("Oh, yeah...") is True
    assert is_pure_filler("Oh my god!") is True
    assert is_pure_filler("Ah, ahh, ooh, mmm...") is True
    assert is_pure_filler("Oh my god! Oh fuck! Yes, yes!") is True
    assert is_pure_filler("Yes") is True
    assert is_pure_filler("No") is True
    assert is_pure_filler("Mmhmm... oh yes!") is True
    assert is_pure_filler("uh huh, mm hmm") is True
    assert is_pure_filler("fuck yeah") is True
    assert is_pure_filler("") is True
    assert is_pure_filler("   ") is True

    # Substantive speech
    assert is_pure_filler("Oh god, please don't leave me alone.") is False
    assert is_pure_filler("Look at that house, oh yeah!") is False
    assert is_pure_filler("Where are you going tomorrow?") is False
    assert is_pure_filler("Hello world") is False


def test_clean_sentence_fillers():
    # Pure fillers reduce to empty string
    assert clean_sentence_fillers("Oh yeah!") == ""
    assert clean_sentence_fillers("Ah, ahh, ooh, mmm...") == ""
    assert clean_sentence_fillers("No") == ""
    assert clean_sentence_fillers("Yes") == ""

    # Mixed sentences clean leading/trailing fillers and properly capitalize
    assert (
        clean_sentence_fillers("Oh god, please don't leave me alone.")
        == "Please don't leave me alone."
    )
    assert clean_sentence_fillers("Look at that house, oh yeah!") == "Look at that house"
    assert (
        clean_sentence_fillers("Oh yeah, you should definitely watch this movie.")
        == "You should definitely watch this movie."
    )
    assert (
        clean_sentence_fillers("Ahhh, yes, exactly what I thought.")
        == "Exactly what I thought."
    )
    assert clean_sentence_fillers("Just hello.") == "Just hello."


def test_filter_filler_segments():
    segments = [
        SubtitleSegment(index=1, start=1.0, end=3.0, text="Oh, yeah... oh my god!"),
        SubtitleSegment(index=2, start=3.5, end=6.0, text="Oh yeah, let's get out of here."),
        SubtitleSegment(index=3, start=7.0, end=8.5, text="Mmm... ahh..."),
        SubtitleSegment(index=4, start=9.0, end=12.0, text="Where is the exit?"),
        SubtitleSegment(index=5, start=12.5, end=14.0, text="Yes, yes!"),
    ]

    filtered = filter_filler_segments(segments)

    # Segments 1, 3, and 5 should be discarded
    assert len(filtered) == 2

    # Segments must be re-indexed sequentially starting at 1
    assert filtered[0].index == 1
    assert filtered[0].text == "Let's get out of here."
    assert filtered[0].start == 3.5

    assert filtered[1].index == 2
    assert filtered[1].text == "Where is the exit?"
    assert filtered[1].start == 9.0


def test_english_whisper_models_registry():
    assert WhisperModelSize.SMALL_EN.value in WHISPER_REGISTRY
    assert WhisperModelSize.MEDIUM_EN.value in WHISPER_REGISTRY
    assert WhisperModelSize.BASE_EN.value in WHISPER_REGISTRY

    small_spec = WHISPER_REGISTRY[WhisperModelSize.SMALL_EN.value]
    assert small_spec["repo_id"] == "Systran/faster-whisper-small.en"
    assert "model.bin" in small_spec["required_files"]
