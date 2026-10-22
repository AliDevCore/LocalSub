"""
Tests for Neural Machine Translation Service, Persian Text Normalizer, and timestamp preservation.
"""

from __future__ import annotations

import pytest

from app.core.types import SubtitleSegment, TargetLanguage
from app.services.translation_service import (
    MockTranslationBackend,
    PersianTextNormalizer,
    TranslationService,
)


def test_persian_text_normalizer():
    """Verify Arabic to Persian character mapping and Persian punctuation conversions."""
    # Test character replacement: ي -> ی, ك -> ک
    raw = "فيلم كمپاني"
    normalized = PersianTextNormalizer.normalize(raw)
    assert normalized == "فیلم کمپانی"

    # Test punctuation: ? -> ؟, ; -> ؛
    punct_text = "آیا آماده هستید? بله; حتما!"
    norm_punct = PersianTextNormalizer.normalize(punct_text)
    assert "؟" in norm_punct
    assert "؛" in norm_punct
    assert "?" not in norm_punct


def test_english_mode_skips_translation(sample_segments):
    """In English mode, input segments are returned without calling the translation model."""
    mock_backend = MockTranslationBackend()
    service = TranslationService(custom_backend=mock_backend)

    output = service.translate_segments(
        segments=sample_segments,
        target_lang=TargetLanguage.ENGLISH.value,
        source_lang=TargetLanguage.ENGLISH.value,
    )

    # Backend was never invoked
    assert mock_backend.call_count == 0
    assert len(output) == len(sample_segments)
    for orig, out in zip(sample_segments, output):
        assert orig.text == out.text


def test_persian_translation_preserves_timestamps_and_index(sample_segments):
    """In Persian mode, timestamps and indices remain strictly identical while text is translated."""
    mock_backend = MockTranslationBackend(prefix="[ترجمه] ")
    service = TranslationService(custom_backend=mock_backend)

    translated = service.translate_segments(
        segments=sample_segments,
        target_lang=TargetLanguage.PERSIAN.value,
        source_lang=TargetLanguage.ENGLISH.value,
        batch_size=2,
    )

    assert mock_backend.call_count == len(sample_segments)
    assert len(translated) == len(sample_segments)

    for orig, trans in zip(sample_segments, translated):
        # Index strictly preserved
        assert orig.index == trans.index
        # Start and end timestamps strictly preserved
        assert abs(orig.start - trans.start) < 0.0001
        assert abs(orig.end - trans.end) < 0.0001
        # Text is translated (not identical to English)
        assert orig.text != trans.text


def test_translation_cancellation_cooperation(sample_segments):
    """Verify cancellation raises InterruptedError and aborts midway."""
    mock_backend = MockTranslationBackend()
    service = TranslationService(custom_backend=mock_backend)

    # Cancellation predicate returning True immediately
    cancelled = True
    with pytest.raises(InterruptedError):
        service.translate_segments(
            segments=sample_segments,
            target_lang=TargetLanguage.PERSIAN.value,
            is_cancelled=lambda: cancelled,
        )


def test_translation_batch_size_handling():
    """Verify handling of larger segment lists chunked across batches."""
    segments = [
        SubtitleSegment(index=i, start=float(i * 2), end=float(i * 2 + 1.5), text=f"Sentence {i}")
        for i in range(1, 26)  # 25 segments
    ]
    mock_backend = MockTranslationBackend(prefix="FA_")
    service = TranslationService(custom_backend=mock_backend)

    results = service.translate_segments(
        segments=segments,
        target_lang=TargetLanguage.PERSIAN.value,
        batch_size=8,
    )

    assert len(results) == 25
    assert results[0].index == 1
    assert results[-1].index == 25
    assert results[10].text.startswith("FA_")
