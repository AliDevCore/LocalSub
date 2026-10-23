"""
LocalSub - Model Manager Service.
Handles downloading, caching, integrity validation, and offline readiness checks
for both faster-whisper speech recognition models and local neural machine translation models.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


class SafeStdWriter:
    """Safe fallback stream when running in PyInstaller GUI mode (console=False)."""
    def write(self, text: str) -> None:
        pass

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False


# Ensure sys.stdout and sys.stderr are never None in GUI execution
if sys.stdout is None:
    sys.stdout = SafeStdWriter()
if sys.stderr is None:
    sys.stderr = SafeStdWriter()

from huggingface_hub import hf_hub_download, snapshot_download
from tqdm.auto import tqdm as base_tqdm

from app.core.config import get_models_dir
from app.core.types import TargetLanguage, TranslationModelType, WhisperModelSize
from app.services.logging_service import get_logger


def create_tqdm_bridge(
    progress_callback: Optional[Callable[[str, float], None]] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
):
    """
    Creates a full tqdm subclass that safely diverts stdout/stderr output
    and feeds download progress into the GUI progress callback.
    """

    class TqdmCallbackBridge(base_tqdm):
        def __init__(self, *args, **kwargs):
            # Divert output to SafeStdWriter to prevent any 'NoneType' object has no attribute 'write'
            kwargs["file"] = SafeStdWriter()
            super().__init__(*args, **kwargs)

        def update(self, n: int = 1) -> None:
            if is_cancelled and is_cancelled():
                raise InterruptedError("Download cancelled by user.")
            super().update(n)
            if progress_callback and self.total:
                pct = min(99.0, 5.0 + (self.n / self.total) * 94.0)
                mb_curr = self.n / (1024 * 1024)
                mb_tot = self.total / (1024 * 1024)
                label = (
                    f"Downloading: {self.desc} ({mb_curr:.1f} / {mb_tot:.1f} MB)..."
                    if self.desc
                    else f"Downloading ({mb_curr:.1f} / {mb_tot:.1f} MB)..."
                )
                progress_callback(label, pct)

    return TqdmCallbackBridge


# Registry of faster-whisper models
WHISPER_REGISTRY: Dict[str, Dict[str, Any]] = {
    WhisperModelSize.BASE.value: {
        "repo_id": "Systran/faster-whisper-base",
        "size_mb": 145,
        "required_files": ["model.bin", "config.json", "vocabulary.txt"],
        "license": "MIT",
        "page_url": "https://huggingface.co/Systran/faster-whisper-base/tree/main",
        "direct_links": [
            ("model.bin (~145 MB)", "https://huggingface.co/Systran/faster-whisper-base/resolve/main/model.bin"),
            ("config.json", "https://huggingface.co/Systran/faster-whisper-base/resolve/main/config.json"),
            ("vocabulary.txt", "https://huggingface.co/Systran/faster-whisper-base/resolve/main/vocabulary.txt"),
            ("tokenizer.json", "https://huggingface.co/Systran/faster-whisper-base/resolve/main/tokenizer.json"),
        ],
    },
    WhisperModelSize.SMALL.value: {
        "repo_id": "Systran/faster-whisper-small",
        "size_mb": 488,
        "required_files": ["model.bin", "config.json", "vocabulary.txt"],
        "license": "MIT",
        "page_url": "https://huggingface.co/Systran/faster-whisper-small/tree/main",
        "direct_links": [
            ("model.bin (~488 MB)", "https://huggingface.co/Systran/faster-whisper-small/resolve/main/model.bin"),
            ("config.json", "https://huggingface.co/Systran/faster-whisper-small/resolve/main/config.json"),
            ("vocabulary.txt", "https://huggingface.co/Systran/faster-whisper-small/resolve/main/vocabulary.txt"),
            ("tokenizer.json", "https://huggingface.co/Systran/faster-whisper-small/resolve/main/tokenizer.json"),
        ],
    },
    WhisperModelSize.MEDIUM.value: {
        "repo_id": "Systran/faster-whisper-medium",
        "size_mb": 1530,
        "required_files": ["model.bin", "config.json", "vocabulary.txt"],
        "license": "MIT",
        "page_url": "https://huggingface.co/Systran/faster-whisper-medium/tree/main",
        "direct_links": [
            ("model.bin (~1.5 GB)", "https://huggingface.co/Systran/faster-whisper-medium/resolve/main/model.bin"),
            ("config.json", "https://huggingface.co/Systran/faster-whisper-medium/resolve/main/config.json"),
            ("vocabulary.txt", "https://huggingface.co/Systran/faster-whisper-medium/resolve/main/vocabulary.txt"),
            ("tokenizer.json", "https://huggingface.co/Systran/faster-whisper-medium/resolve/main/tokenizer.json"),
        ],
    },
}

# Registry of local translation models
TRANSLATION_REGISTRY: Dict[str, Dict[str, Any]] = {
    TranslationModelType.TRANSLATEGEMMA_4B.value: {
        "repo_id": "vwdvaan/translategemma-4b-it-Q4_K_M-GGUF",
        "type": "gguf",
        "size_mb": 2400,
        "required_files": ["translategemma-4b-it-q4_k_m.gguf"],
        "license": "Gemma Open",
        "license_description": "Google Gemma Open Weights Terms of Use.",
        "supported_pairs": [("en", "fa")],
        "page_url": "https://huggingface.co/vwdvaan/translategemma-4b-it-Q4_K_M-GGUF",
        "direct_links": [
            (
                "translategemma-4b-it-q4_k_m.gguf (~2.4 GB)",
                "https://huggingface.co/vwdvaan/translategemma-4b-it-Q4_K_M-GGUF/resolve/main/translategemma-4b-it-q4_k_m.gguf",
            ),
        ],
    },
    TranslationModelType.NLLB_DISTILLED_600M.value: {
        "repo_id": "JustFrederik/nllb-200-distilled-600M-ct2-int8",
        "fallback_hf_repo": "facebook/nllb-200-distilled-600M",
        "type": "ctranslate2",
        "size_mb": 620,
        "required_files": ["model.bin", "shared_vocabulary.txt"],
        "tokenizer_repo": "facebook/nllb-200-distilled-600M",
        "license": "CC-BY-NC-4.0",
        "license_description": "Non-commercial educational and personal research use.",
        "supported_pairs": [("en", "fa"), ("en", "de"), ("en", "fr"), ("en", "es")],
        "page_url": "https://huggingface.co/JustFrederik/nllb-200-distilled-600M-ct2-int8/tree/main",
        "direct_links": [
            ("model.bin (~622 MB)", "https://huggingface.co/JustFrederik/nllb-200-distilled-600M-ct2-int8/resolve/main/model.bin"),
            ("shared_vocabulary.txt (~2.5 MB)", "https://huggingface.co/JustFrederik/nllb-200-distilled-600M-ct2-int8/resolve/main/shared_vocabulary.txt"),
            ("sentencepiece.bpe.model (~4.8 MB)", "https://huggingface.co/JustFrederik/nllb-200-distilled-600M-ct2-int8/resolve/main/sentencepiece.bpe.model"),
            ("config.json", "https://huggingface.co/JustFrederik/nllb-200-distilled-600M-ct2-int8/resolve/main/config.json"),
            ("tokenizer.json (~17 MB)", "https://huggingface.co/JustFrederik/nllb-200-distilled-600M-ct2-int8/resolve/main/tokenizer.json"),
            ("tokenizer_config.json", "https://huggingface.co/facebook/nllb-200-distilled-600M/resolve/main/tokenizer_config.json"),
            ("special_tokens_map.json", "https://huggingface.co/facebook/nllb-200-distilled-600M/resolve/main/special_tokens_map.json"),
        ],
    },
    TranslationModelType.OPUS_MT_EN_FA.value: {
        "repo_id": "Helsinki-NLP/opus-mt-en-fa",
        "type": "transformers",
        "size_mb": 310,
        "required_files": ["model.bin"],
        "license": "Apache-2.0",
        "license_description": "Permissive open source license.",
        "supported_pairs": [("en", "fa")],
        "page_url": "https://huggingface.co/Helsinki-NLP/opus-mt-en-fa",
        "direct_links": [],
    },
}


class ModelManager:
    """Manages local storage, downloading, and validation of AI models."""

    def __init__(self, models_root: Optional[Path] = None):
        self.models_root = models_root or get_models_dir()
        self.whisper_dir = self.models_root / "whisper"
        self.translation_dir = self.models_root / "translation"

        self.whisper_dir.mkdir(parents=True, exist_ok=True)
        self.translation_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------------
    # Whisper Model Management
    # --------------------------------------------------------------------------

    def get_whisper_model_path(self, model_size: str) -> Path:
        """Return the directory path for a whisper model."""
        return self.whisper_dir / model_size

    def is_whisper_model_ready(self, model_size: str) -> bool:
        """
        Verify if the whisper model is completely downloaded and intact.
        Checks for required model files.
        """
        model_path = self.get_whisper_model_path(model_size)
        if not model_path.is_dir():
            return False

        spec = WHISPER_REGISTRY.get(model_size)
        if not spec:
            return False

        for req in spec["required_files"]:
            file_path = model_path / req
            if not file_path.is_file() or file_path.stat().st_size == 0:
                if req == "vocabulary.txt" and (model_path / "vocabulary.json").is_file():
                    continue
                return False

        return True

    def download_whisper_model(
        self,
        model_size: str,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> Path:
        """
        Download whisper model from HuggingFace to local cache directory.
        """
        if self.is_whisper_model_ready(model_size):
            get_logger().info(f"Whisper model '{model_size}' already downloaded and verified.")
            return self.get_whisper_model_path(model_size)

        spec = WHISPER_REGISTRY.get(model_size)
        if not spec:
            raise ValueError(f"Unknown whisper model size: {model_size}")

        repo_id = spec["repo_id"]
        target_dir = self.get_whisper_model_path(model_size)
        target_dir.mkdir(parents=True, exist_ok=True)

        get_logger().info(f"Downloading Whisper '{model_size}' from '{repo_id}' (~{spec['size_mb']} MB)...")
        if progress_callback:
            progress_callback(f"Connecting to download Whisper {model_size}...", 5.0)

        try:
            if is_cancelled and is_cancelled():
                raise InterruptedError("Download cancelled by user.")

            tqdm_bridge = create_tqdm_bridge(progress_callback, is_cancelled)

            snapshot_download(
                repo_id=repo_id,
                local_dir=str(target_dir),
                tqdm_class=tqdm_bridge,
            )

            if not self.is_whisper_model_ready(model_size):
                raise RuntimeError(f"Whisper model '{model_size}' download was incomplete or corrupted.")

            get_logger().info(f"Whisper model '{model_size}' ready at: {target_dir}")
            if progress_callback:
                progress_callback(f"Whisper {model_size} downloaded successfully.", 100.0)

            return target_dir

        except Exception as e:
            get_logger().error(f"Error downloading whisper model '{model_size}': {e}")
            # If download failed and model is incomplete, clean up partial files
            if not self.is_whisper_model_ready(model_size):
                self._safe_clean_dir(target_dir)
            raise

    # --------------------------------------------------------------------------
    # Translation Model Management
    # --------------------------------------------------------------------------

    def get_translation_model_path(self, model_type: str) -> Path:
        """Return directory path for translation model."""
        return self.translation_dir / model_type

    def is_translation_model_ready(self, model_type: str) -> bool:
        """
        Verify if the translation model is downloaded and intact.
        """
        model_path = self.get_translation_model_path(model_type)
        if not model_path.is_dir():
            return False

        spec = TRANSLATION_REGISTRY.get(model_type)
        if not spec:
            return False

        if spec.get("type") == "gguf":
            gguf_files = list(model_path.glob("*.gguf"))
            return len(gguf_files) > 0 and any(f.stat().st_size > 100 * 1024 * 1024 for f in gguf_files)

        for req in spec["required_files"]:
            file_path = model_path / req
            if not file_path.is_file() or file_path.stat().st_size == 0:
                if req == "shared_vocabulary.txt" and (model_path / "shared_vocabulary.json").is_file():
                    continue
                return False

        return True

    def download_translation_model(
        self,
        model_type: str,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> Path:
        """
        Download translation model from HuggingFace to local cache directory.
        Only called when target language requires translation.
        """
        if self.is_translation_model_ready(model_type):
            get_logger().info(f"Translation model '{model_type}' already downloaded and verified.")
            return self.get_translation_model_path(model_type)

        spec = TRANSLATION_REGISTRY.get(model_type)
        if not spec:
            raise ValueError(f"Unknown translation model type: {model_type}")

        repo_id = spec["repo_id"]
        target_dir = self.get_translation_model_path(model_type)
        target_dir.mkdir(parents=True, exist_ok=True)

        get_logger().info(
            f"Downloading Translation Model '{model_type}' from '{repo_id}' (~{spec['size_mb']} MB)..."
        )
        if progress_callback:
            progress_callback(f"Connecting to download Translation model (~{spec['size_mb']} MB)...", 5.0)

        try:
            if is_cancelled and is_cancelled():
                raise InterruptedError("Download cancelled by user.")

            tqdm_bridge = create_tqdm_bridge(progress_callback, is_cancelled)

            snapshot_download(
                repo_id=repo_id,
                local_dir=str(target_dir),
                tqdm_class=tqdm_bridge,
            )

            if not self.is_translation_model_ready(model_type):
                raise RuntimeError(
                    f"Translation model '{model_type}' files failed validation after download."
                )

            get_logger().info(f"Translation model '{model_type}' ready at: {target_dir}")
            if progress_callback:
                progress_callback("Translation model downloaded successfully.", 100.0)

            return target_dir

        except Exception as e:
            get_logger().error(f"Error downloading translation model '{model_type}': {e}")
            if not self.is_translation_model_ready(model_type):
                self._safe_clean_dir(target_dir)
            raise

    def get_model_download_info(self, category: str, identifier: str) -> Dict[str, Any]:
        """Return download links and metadata for a model."""
        if category == "whisper":
            spec = WHISPER_REGISTRY.get(identifier, {})
        else:
            spec = TRANSLATION_REGISTRY.get(identifier, {})
        return spec

    def import_model_from_zip(
        self,
        category: str,
        identifier: str,
        zip_path: Path,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> Path:
        """
        Extract and validate a user-provided ZIP archive containing model files.
        Handles flat archives and archives with a root subdirectory.
        """
        import tempfile
        import zipfile

        if not zip_path.is_file():
            raise FileNotFoundError(f"File not found: {zip_path}")

        if category == "whisper":
            target_dir = self.get_whisper_model_path(identifier)
        elif category == "translation":
            target_dir = self.get_translation_model_path(identifier)
        else:
            raise ValueError(f"Unknown category: {category}")

        if progress_callback:
            progress_callback(f"Opening ZIP file '{zip_path.name}'...", 10.0)

        with tempfile.TemporaryDirectory() as temp_unpack:
            temp_unpack_path = Path(temp_unpack)
            with zipfile.ZipFile(zip_path, "r") as zf:
                # Zip safety limits (prevent zip bombs)
                infolist = zf.infolist()
                if len(infolist) > 500:
                    raise ValueError(f"Zip archive contains too many files ({len(infolist)} > 500 limit).")
                total_uncompressed = sum(info.file_size for info in infolist)
                if total_uncompressed > 5 * 1024 * 1024 * 1024:  # 5 GB limit
                    raise ValueError("Zip archive uncompressed size exceeds safe limit (5 GB).")

                zf.extractall(temp_unpack_path)

            if progress_callback:
                progress_callback("Analyzing extracted files...", 50.0)

            # Determine if files are directly inside temp_unpack or in a single subfolder
            candidates = [p for p in temp_unpack_path.iterdir() if p.is_dir()]
            files_in_root = [p for p in temp_unpack_path.iterdir() if p.is_file()]

            source_dir = temp_unpack_path
            if len(files_in_root) == 0 and len(candidates) == 1:
                source_dir = candidates[0]

            # Normalize vocabulary files in staging first
            self._normalize_model_files(source_dir)

            # Validate files in staging directory BEFORE touching target_dir!
            if category == "whisper":
                spec = WHISPER_REGISTRY.get(identifier, {})
                for req in spec.get("required_files", []):
                    req_path = source_dir / req
                    if not req_path.is_file() or req_path.stat().st_size == 0:
                        if req == "vocabulary.txt" and (source_dir / "vocabulary.json").is_file():
                            continue
                        raise ValueError(
                            f"The ZIP archive does not contain the required Whisper '{identifier}' file: '{req}'."
                        )
            elif category == "translation":
                spec = TRANSLATION_REGISTRY.get(identifier, {})
                if spec.get("type") == "gguf":
                    gguf_files = list(source_dir.glob("*.gguf"))
                    if not gguf_files or not any(f.stat().st_size > 100 * 1024 * 1024 for f in gguf_files):
                        raise ValueError(
                            f"The ZIP archive does not contain a valid GGUF model file (*.gguf) for '{identifier}'."
                        )
                else:
                    for req in spec.get("required_files", []):
                        req_path = source_dir / req
                        if not req_path.is_file() or req_path.stat().st_size == 0:
                            if req == "shared_vocabulary.txt" and (source_dir / "shared_vocabulary.json").is_file():
                                continue
                            raise ValueError(
                                f"The ZIP archive does not contain the required translation '{identifier}' file: '{req}'."
                            )

            # Validation passed in staging: now safely populate target_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            for item in source_dir.rglob("*"):
                if item.is_file():
                    rel = item.relative_to(source_dir)
                    dest_file = target_dir / rel
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest_file)

        # Normalize final target directory
        self._normalize_model_files(target_dir)

        if progress_callback:
            progress_callback("Model imported and verified successfully!", 100.0)

        return target_dir

    def import_model_from_folder(
        self,
        category: str,
        identifier: str,
        folder_path: Path,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> Path:
        """
        Copy and validate files from a user-selected folder into the proper model directory.
        """
        if not folder_path.is_dir():
            raise NotADirectoryError(f"Directory not found: {folder_path}")

        if category == "whisper":
            target_dir = self.get_whisper_model_path(identifier)
            spec = WHISPER_REGISTRY.get(identifier, {})
            for req in spec.get("required_files", []):
                req_path = folder_path / req
                if not req_path.is_file() or req_path.stat().st_size == 0:
                    if req == "vocabulary.txt" and (folder_path / "vocabulary.json").is_file():
                        continue
                    raise ValueError(
                        f"Selected folder does not contain required Whisper '{identifier}' file: '{req}'."
                    )
        elif category == "translation":
            target_dir = self.get_translation_model_path(identifier)
            spec = TRANSLATION_REGISTRY.get(identifier, {})
            if spec.get("type") == "gguf":
                gguf_files = list(folder_path.glob("*.gguf"))
                if not gguf_files or not any(f.stat().st_size > 100 * 1024 * 1024 for f in gguf_files):
                    raise ValueError(
                        f"Selected folder does not contain a valid GGUF model file (*.gguf) for '{identifier}'."
                    )
            else:
                for req in spec.get("required_files", []):
                    req_path = folder_path / req
                    if not req_path.is_file() or req_path.stat().st_size == 0:
                        if req == "shared_vocabulary.txt" and (folder_path / "shared_vocabulary.json").is_file():
                            continue
                        raise ValueError(
                            f"Selected folder does not contain required translation '{identifier}' file: '{req}'."
                        )
        else:
            raise ValueError(f"Unknown category: {category}")

        if progress_callback:
            progress_callback("Copying model files...", 30.0)

        target_dir.mkdir(parents=True, exist_ok=True)
        for item in folder_path.rglob("*"):
            if item.is_file():
                rel = item.relative_to(folder_path)
                dest = target_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest)

        self._normalize_model_files(target_dir)

        if progress_callback:
            progress_callback("Model imported and verified successfully!", 100.0)

        return target_dir

    def import_model_from_file(
        self,
        category: str,
        identifier: str,
        file_path: Path,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> Path:
        """
        Copy a single model file (such as a .gguf or .bin file) directly into the proper model directory.
        """
        if not file_path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        if category == "whisper":
            target_dir = self.get_whisper_model_path(identifier)
        elif category == "translation":
            target_dir = self.get_translation_model_path(identifier)
        else:
            raise ValueError(f"Unknown category: {category}")

        target_dir.mkdir(parents=True, exist_ok=True)
        dest_file = target_dir / file_path.name

        if progress_callback:
            progress_callback(f"Copying '{file_path.name}'...", 30.0)

        shutil.copy2(file_path, dest_file)

        # Verification check
        if category == "whisper":
            if not self.is_whisper_model_ready(identifier):
                raise ValueError(
                    f"Model file '{file_path.name}' was copied, but Whisper '{identifier}' is still missing required files."
                )
        elif category == "translation":
            if not self.is_translation_model_ready(identifier):
                raise ValueError(
                    f"Model file '{file_path.name}' was copied, but translation model '{identifier}' is still missing required files."
                )

        if progress_callback:
            progress_callback("Model file imported and verified successfully!", 100.0)

        return target_dir

    @staticmethod
    def _normalize_model_files(directory: Path) -> None:
        """
        Clean up any invalid non-JSON vocabulary files so CTranslate2 does not crash.
        CTranslate2 expects vocabulary.json to be valid JSON format, and vocabulary.txt
        to be a newline-delimited text file. If vocabulary.json contains plain text,
        it causes [json.exception.parse_error.101].
        """
        import json

        v_json = directory / "vocabulary.json"
        if v_json.is_file():
            try:
                with open(v_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if not isinstance(data, dict):
                        v_json.unlink(missing_ok=True)
            except Exception:
                # Not valid JSON! Delete it so CTranslate2 cleanly uses vocabulary.txt
                v_json.unlink(missing_ok=True)

        sv_json = directory / "shared_vocabulary.json"
        if sv_json.is_file():
            try:
                with open(sv_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if not isinstance(data, dict):
                        sv_json.unlink(missing_ok=True)
            except Exception:
                sv_json.unlink(missing_ok=True)

    # --------------------------------------------------------------------------
    # Utility Methods
    # --------------------------------------------------------------------------

    @staticmethod
    def _safe_clean_dir(directory: Path) -> None:
        """Clean directory if it exists."""
        try:
            if directory.is_dir():
                shutil.rmtree(directory, ignore_errors=True)
        except Exception:
            pass

    def get_status_summary(
        self, whisper_size: str, translation_type: str, target_lang: str
    ) -> Dict[str, Any]:
        """Provide detailed readiness summary for GUI display."""
        whisper_ready = self.is_whisper_model_ready(whisper_size)
        trans_required = target_lang != TargetLanguage.ENGLISH.value
        trans_ready = self.is_translation_model_ready(translation_type) if trans_required else True

        whisper_spec = WHISPER_REGISTRY.get(whisper_size, {})
        trans_spec = TRANSLATION_REGISTRY.get(translation_type, {})

        return {
            "whisper_size": whisper_size,
            "whisper_ready": whisper_ready,
            "whisper_path": str(self.get_whisper_model_path(whisper_size)),
            "whisper_size_mb": whisper_spec.get("size_mb", 0),
            "translation_required": trans_required,
            "translation_type": translation_type,
            "translation_ready": trans_ready,
            "translation_path": str(self.get_translation_model_path(translation_type)),
            "translation_size_mb": trans_spec.get("size_mb", 0),
            "translation_license": trans_spec.get("license", "Unknown"),
            "all_ready": whisper_ready and trans_ready,
        }
