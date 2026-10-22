"""
Tests for ModelManager: offline detection, model registry, and error handling.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.types import TargetLanguage, TranslationModelType, WhisperModelSize
from app.services.model_manager import ModelManager, TRANSLATION_REGISTRY, WHISPER_REGISTRY


def test_model_manager_directories(temp_dir: Path):
    """Ensure manager creates whisper and translation directories inside models root."""
    mgr = ModelManager(models_root=temp_dir)
    assert mgr.whisper_dir.is_dir()
    assert mgr.translation_dir.is_dir()


def test_whisper_offline_readiness_check(temp_dir: Path):
    """Verify is_whisper_model_ready checks for presence of required model files."""
    mgr = ModelManager(models_root=temp_dir)
    model_size = WhisperModelSize.SMALL.value

    # Initially missing
    assert mgr.is_whisper_model_ready(model_size) is False

    # Create dummy required files
    target_dir = mgr.get_whisper_model_path(model_size)
    target_dir.mkdir(parents=True, exist_ok=True)
    for req in WHISPER_REGISTRY[model_size]["required_files"]:
        (target_dir / req).write_text("dummy", encoding="utf-8")

    # Now ready
    assert mgr.is_whisper_model_ready(model_size) is True


def test_translation_offline_readiness_check(temp_dir: Path):
    """Verify is_translation_model_ready checks for presence of required translation files."""
    mgr = ModelManager(models_root=temp_dir)
    model_type = TranslationModelType.NLLB_DISTILLED_600M.value

    # Initially missing
    assert mgr.is_translation_model_ready(model_type) is False

    # Create dummy files
    target_dir = mgr.get_translation_model_path(model_type)
    target_dir.mkdir(parents=True, exist_ok=True)
    for req in TRANSLATION_REGISTRY[model_type]["required_files"]:
        (target_dir / req).write_text("dummy", encoding="utf-8")

    assert mgr.is_translation_model_ready(model_type) is True


def test_status_summary_english_vs_persian(temp_dir: Path):
    """Ensure in English mode, translation is marked as not required."""
    mgr = ModelManager(models_root=temp_dir)

    # In English mode
    summary_en = mgr.get_status_summary(
        whisper_size=WhisperModelSize.SMALL.value,
        translation_type=TranslationModelType.NLLB_DISTILLED_600M.value,
        target_lang=TargetLanguage.ENGLISH.value,
    )
    assert summary_en["translation_required"] is False
    assert summary_en["translation_ready"] is True

    # In Persian mode
    summary_fa = mgr.get_status_summary(
        whisper_size=WhisperModelSize.SMALL.value,
        translation_type=TranslationModelType.NLLB_DISTILLED_600M.value,
        target_lang=TargetLanguage.PERSIAN.value,
    )
    assert summary_fa["translation_required"] is True
    # Since files don't exist yet, it's False
    assert summary_fa["translation_ready"] is False


def test_download_cleanup_on_failure(temp_dir: Path):
    """If snapshot_download raises an exception, partial directory is cleaned up."""
    mgr = ModelManager(models_root=temp_dir)

    with patch("app.services.model_manager.snapshot_download", side_effect=ConnectionError("Network drop")):
        with pytest.raises(ConnectionError):
            mgr.download_whisper_model(WhisperModelSize.BASE.value)

    target_dir = mgr.get_whisper_model_path(WhisperModelSize.BASE.value)
    assert not target_dir.is_dir() or len(list(target_dir.iterdir())) == 0


def test_download_tqdm_bridge_handles_none_stderr(temp_dir: Path):
    """
    Ensure downloading with sys.stderr=None (PyInstaller GUI mode)
    never crashes with 'NoneType' object has no attribute 'write'.
    """
    import sys
    from app.services.model_manager import create_tqdm_bridge

    orig_stderr = sys.stderr
    orig_stdout = sys.stdout
    sys.stderr = None
    sys.stdout = None

    try:
        progress_events = []
        bridge_cls = create_tqdm_bridge(
            progress_callback=lambda msg, pct: progress_events.append((msg, pct))
        )
        with bridge_cls(total=1000, desc="test_model") as pbar:
            pbar.update(250)
            pbar.refresh()
            pbar.set_description("downloading chunks")
            pbar.update(250)
            pbar.refresh()

        assert len(progress_events) == 2
        assert progress_events[0][1] > 0
    finally:
        sys.stderr = orig_stderr
        sys.stdout = orig_stdout


def test_import_model_from_zip_flat_and_nested(temp_dir: Path):
    """Test importing model files from zip archives (both flat and nested folder structure)."""
    import zipfile
    mgr = ModelManager(models_root=temp_dir)

    # 1. Test flat zip for whisper
    zip_flat = temp_dir / "whisper_flat.zip"
    with zipfile.ZipFile(zip_flat, "w") as zf:
        zf.writestr("model.bin", "binary-content")
        zf.writestr("config.json", "{}")
        zf.writestr("vocabulary.txt", "vocab")

    out_path = mgr.import_model_from_zip("whisper", WhisperModelSize.SMALL.value, zip_flat)
    assert out_path.is_dir()
    assert mgr.is_whisper_model_ready(WhisperModelSize.SMALL.value) is True
    assert (out_path / "vocabulary.txt").is_file()

    # 2. Test nested zip for translation
    zip_nested = temp_dir / "nllb_nested.zip"
    with zipfile.ZipFile(zip_nested, "w") as zf:
        zf.writestr("nllb-folder/model.bin", "model-data")
        zf.writestr("nllb-folder/shared_vocabulary.txt", "shared-vocab")

    trans_path = mgr.import_model_from_zip("translation", TranslationModelType.NLLB_DISTILLED_600M.value, zip_nested)
    assert trans_path.is_dir()
    assert mgr.is_translation_model_ready(TranslationModelType.NLLB_DISTILLED_600M.value) is True
    assert (trans_path / "shared_vocabulary.txt").is_file()


def test_import_model_from_folder(temp_dir: Path):
    """Test importing model files from a local directory."""
    mgr = ModelManager(models_root=temp_dir)

    source_dir = temp_dir / "my_downloaded_nllb"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "model.bin").write_text("model", encoding="utf-8")
    (source_dir / "shared_vocabulary.txt").write_text("vocab", encoding="utf-8")

    out_path = mgr.import_model_from_folder("translation", TranslationModelType.NLLB_DISTILLED_600M.value, source_dir)
    assert out_path.is_dir()
    assert mgr.is_translation_model_ready(TranslationModelType.NLLB_DISTILLED_600M.value) is True

