"""
LocalSub - Neural Machine Translation Service.
Translates English transcribed dialogue into natural Persian (or other target languages),
preserving exact subtitle timestamps, sequential numbering, and SubRip integrity.
Supports CPU INT8 execution via CTranslate2 and Transformers.
"""

from __future__ import annotations

import gc
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from app.core.types import SubtitleSegment, TargetLanguage, TranslationModelType
from app.services.logging_service import get_logger
from app.services.model_manager import TRANSLATION_REGISTRY, ModelManager


class PersianTextNormalizer:
    """Normalizes Persian characters, punctuation, and typography for clean subtitles."""

    # Arabic to Persian character mappings (safe standard mappings only)
    CHAR_MAP = {
        "ي": "ی",
        "ك": "ک",
        "ى": "ی",
        "ة": "ه",
    }

    @classmethod
    def normalize(cls, text: str) -> str:
        """Apply safe character normalization and Persian punctuation without corrupting URLs/Latin text."""
        if not text:
            return ""

        # Character normalization
        for src, dst in cls.CHAR_MAP.items():
            text = text.replace(src, dst)

        # Apply Persian punctuation only if Persian text is present and avoid URLs
        has_persian = bool(re.search(r"[\u0600-\u06FF]", text))
        is_url = bool(re.search(r"https?://\S+", text))

        if has_persian and not is_url:
            # Replace question mark preceded by Persian letter or space
            text = re.sub(r"([\u0600-\u06FF\s])\?", r"\1؟", text)
            # Replace semicolon preceded by Persian letter or space
            text = re.sub(r"([\u0600-\u06FF\s]);", r"\1؛", text)
            # Replace comma only when adjacent to Persian letters
            text = re.sub(r"([\u0600-\u06FF]),", r"\1،", text)
            text = re.sub(r",([\u0600-\u06FF])", r"،\1", text)

        # Normalize whitespace
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()


class BaseTranslationBackend(ABC):
    """Abstract interface for local translation inference backends."""

    @abstractmethod
    def translate_batch(
        self,
        texts: List[str],
        source_lang: str = "en",
        target_lang: str = "fa",
    ) -> List[str]:
        """Translate a batch of text strings."""
        pass

    @abstractmethod
    def unload(self) -> None:
        """Free model weights from memory."""
        pass


class CTranslate2NLLBBackend(BaseTranslationBackend):
    """
    CTranslate2 execution backend for quantized NLLB-200.
    Ultra-efficient INT8 CPU inference with ~800MB RAM consumption.
    """

    def __init__(self, model_dir: Path, cpu_threads: int = 4):
        self.model_dir = Path(model_dir)
        self.cpu_threads = cpu_threads
        self._translator = None
        self._tokenizer = None
        self._load()

    def _load(self) -> None:
        import ctranslate2
        from transformers import AutoTokenizer
        from app.services.model_manager import ModelManager

        # Ensure no invalid non-JSON shared_vocabulary.json causes CTranslate2 parse error
        ModelManager._normalize_model_files(self.model_dir)

        get_logger().info(f"Initializing CTranslate2 Translator from '{self.model_dir}' (threads={self.cpu_threads})...")
        self._translator = ctranslate2.Translator(
            str(self.model_dir),
            device="cpu",
            compute_type="int8",
            intra_threads=self.cpu_threads,
            inter_threads=1,
        )

        # Load tokenizer strictly offline from local model directory
        get_logger().info(f"Loading NLLB Tokenizer offline from '{self.model_dir}'...")
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(
                str(self.model_dir),
                src_lang="eng_Latn",
                local_files_only=True,
            )
        except Exception as err:
            sp_model = self.model_dir / "sentencepiece.bpe.model"
            if sp_model.is_file():
                try:
                    from transformers import NllbTokenizer
                    self._tokenizer = NllbTokenizer(
                        vocab_file=str(sp_model),
                        src_lang="eng_Latn",
                    )
                except Exception as sp_err:
                    raise RuntimeError(
                        f"Failed to load NLLB tokenizer offline from '{self.model_dir}': {sp_err}"
                    ) from sp_err
            else:
                raise FileNotFoundError(
                    f"NLLB model directory '{self.model_dir}' is missing required local tokenizer files "
                    f"(sentencepiece.bpe.model or tokenizer.json). Offline translation requires these files. Error: {err}"
                ) from err

    def translate_batch(
        self,
        texts: List[str],
        source_lang: str = "en",
        target_lang: str = "fa",
    ) -> List[str]:
        if not texts:
            return []

        # Map language codes to NLLB codes
        tgt_code = "pes_Arab" if target_lang in ("fa", "pes", "fas") else f"{target_lang}_Latn"
        src_code = "eng_Latn" if source_lang in ("en", "eng") else f"{source_lang}_Latn"

        self._tokenizer.src_lang = src_code

        # Tokenize source texts
        source_tokens = [self._tokenizer.convert_ids_to_tokens(self._tokenizer.encode(t)) for t in texts]

        # Target prefix token is the target language code
        target_prefix = [[tgt_code]] * len(texts)

        # CTranslate2 translation
        results = self._translator.translate_batch(
            source_tokens,
            target_prefix=target_prefix,
            beam_size=4,
            max_batch_size=16,
            batch_type="examples",
        )

        translated_texts: List[str] = []
        for res in results:
            # Drop the target prefix token
            output_tokens = res.hypotheses[0]
            if output_tokens and output_tokens[0] == tgt_code:
                output_tokens = output_tokens[1:]
            token_ids = self._tokenizer.convert_tokens_to_ids(output_tokens)
            text = self._tokenizer.decode(token_ids, skip_special_tokens=True)
            translated_texts.append(text.strip())

        return translated_texts

    def unload(self) -> None:
        if self._translator is not None:
            del self._translator
            self._translator = None
        if self._tokenizer is not None:
            del self._tokenizer
            self._tokenizer = None
        gc.collect()


class TransformersSeq2SeqBackend(BaseTranslationBackend):
    """
    HuggingFace transformers pipeline backend (for Opus-MT or fallback NLLB).
    """

    def __init__(self, model_dir_or_name: str, cpu_threads: int = 4):
        self.model_identifier = str(model_dir_or_name)
        self.cpu_threads = cpu_threads
        self._pipeline = None
        self._load()

    def _load(self) -> None:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline

        torch.set_num_threads(self.cpu_threads)
        get_logger().info(f"Loading Transformers translation pipeline from '{self.model_identifier}'...")
        tokenizer = AutoTokenizer.from_pretrained(self.model_identifier)
        model = AutoModelForSeq2SeqLM.from_pretrained(self.model_identifier)
        self._pipeline = pipeline("translation", model=model, tokenizer=tokenizer, device=-1)

    def translate_batch(
        self,
        texts: List[str],
        source_lang: str = "en",
        target_lang: str = "fa",
    ) -> List[str]:
        if not texts or self._pipeline is None:
            return []

        outputs = self._pipeline(texts, max_length=256, truncation=True)
        results: List[str] = []
        for out in outputs:
            text = out.get("translation_text", "").strip()
            results.append(text)
        return results

    def unload(self) -> None:
        if self._pipeline is not None:
            del self._pipeline
            self._pipeline = None
        gc.collect()


class LlamaCppTranslationBackend(BaseTranslationBackend):
    """
    llama-cpp-python execution backend for GGUF models like Google TranslateGemma 4B.
    Highly optimized 4-bit CPU inference with ~3-4GB RAM consumption.
    """

    def __init__(self, model_dir: Path, cpu_threads: int = 4):
        self.model_dir = Path(model_dir)
        self.cpu_threads = cpu_threads
        self._llm = None
        self._load()

    def _load(self) -> None:
        try:
            from llama_cpp import Llama
        except ImportError as e:
            raise ImportError(
                "llama-cpp-python is required for running GGUF translation models (TranslateGemma). "
                "Install it using: pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu"
            ) from e

        gguf_files = list(self.model_dir.glob("*.gguf"))
        if not gguf_files:
            raise FileNotFoundError(f"No .gguf model file found in '{self.model_dir}'.")
        model_file = gguf_files[0]

        get_logger().info(
            f"Loading GGUF Translation Model from '{model_file.name}' with {self.cpu_threads} CPU threads..."
        )
        self._llm = Llama(
            model_path=str(model_file),
            n_ctx=2048,
            n_threads=self.cpu_threads,
            verbose=False,
        )

    def translate_batch(
        self,
        texts: List[str],
        source_lang: str = "en",
        target_lang: str = "fa",
    ) -> List[str]:
        if not texts or self._llm is None:
            return []

        results: List[str] = []
        system_instruction = (
            "You are a professional English to Persian subtitle translator. "
            "Translate each dialogue line naturally, accurately, and idiomatically into fluent Persian (fa-IR). "
            "Output ONLY the direct Persian translation without any quotes, notes, or extra English words."
        )

        for text in texts:
            cleaned = text.strip()
            if not cleaned:
                results.append("")
                continue

            try:
                response = self._llm.create_chat_completion(
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": f"Translate to Persian:\n{cleaned}"},
                    ],
                    temperature=0.1,
                    max_tokens=256,
                )
                output = response["choices"][0]["message"]["content"]
                output = output.strip().strip('"').strip("'")
                results.append(output)
            except Exception as e:
                get_logger().warning(f"TranslateGemma translation error for '{cleaned}': {e}")
                results.append(cleaned)

        return results

    def unload(self) -> None:
        if self._llm is not None:
            del self._llm
            self._llm = None
        gc.collect()


class MockTranslationBackend(BaseTranslationBackend):
    """Mock backend used for unit tests to avoid internet/model download requirements."""

    def __init__(self, prefix: str = "[FA] "):
        self.prefix = prefix
        self.call_count = 0

    def translate_batch(
        self,
        texts: List[str],
        source_lang: str = "en",
        target_lang: str = "fa",
    ) -> List[str]:
        self.call_count += len(texts)
        # Mock translations mapping known phrases or prefixing
        translations = []
        dictionary = {
            "Hello": "سلام",
            "Hello world": "سلام دنیا",
            "Thank you": "متشکرم",
            "Good morning": "صبح بخیر",
            "This is a test": "این یک آزمایش است",
        }
        for t in texts:
            cleaned = t.strip()
            if cleaned in dictionary:
                translations.append(dictionary[cleaned])
            else:
                translations.append(f"{self.prefix}{cleaned}")
        return translations

    def unload(self) -> None:
        pass


class TranslationService:
    """Orchestrates subtitle translation with batching, progress reporting, and alignment."""

    def __init__(
        self,
        model_manager: Optional[ModelManager] = None,
        custom_backend: Optional[BaseTranslationBackend] = None,
    ):
        self.model_manager = model_manager or ModelManager()
        self._backend: Optional[BaseTranslationBackend] = custom_backend
        self._current_model_type: Optional[str] = None

    def set_backend(self, backend: BaseTranslationBackend) -> None:
        """Inject custom or mock backend for testing."""
        self._backend = backend

    def load_model(
        self,
        model_type: str = TranslationModelType.NLLB_DISTILLED_600M.value,
        cpu_threads: int = 4,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> BaseTranslationBackend:
        """Load and cache translation backend."""
        if self._backend is not None and self._current_model_type == model_type:
            return self._backend

        # If custom backend was manually set, keep it
        if self._backend is not None and isinstance(self._backend, MockTranslationBackend):
            return self._backend

        if not self.model_manager.is_translation_model_ready(model_type):
            if progress_callback:
                progress_callback(f"Downloading translation model ({model_type})...", 0.0)
            self.model_manager.download_translation_model(
                model_type=model_type,
                progress_callback=progress_callback,
                is_cancelled=is_cancelled,
            )

        model_path = self.model_manager.get_translation_model_path(model_type)
        spec = TRANSLATION_REGISTRY.get(model_type, {})
        engine_type = spec.get("type", "ctranslate2")

        self.unload_model()

        if is_cancelled and is_cancelled():
            raise InterruptedError("Cancelled before translation model initialization.")

        try:
            if engine_type == "ctranslate2":
                self._backend = CTranslate2NLLBBackend(model_dir=model_path, cpu_threads=cpu_threads)
            elif engine_type == "gguf":
                self._backend = LlamaCppTranslationBackend(model_dir=model_path, cpu_threads=cpu_threads)
            else:
                self._backend = TransformersSeq2SeqBackend(model_dir_or_name=str(model_path), cpu_threads=cpu_threads)
            self._current_model_type = model_type
            return self._backend
        except Exception as e:
            get_logger().error(f"Failed to initialize translation backend '{model_type}': {e}")
            raise RuntimeError(f"Unable to load translation model: {e}")

    def unload_model(self) -> None:
        """Free translation model from memory."""
        if self._backend is not None:
            get_logger().info(f"Unloading translation model '{self._current_model_type}' from memory.")
            self._backend.unload()
            self._backend = None
            self._current_model_type = None

    def translate_segments(
        self,
        segments: List[SubtitleSegment],
        target_lang: str = TargetLanguage.PERSIAN.value,
        source_lang: str = TargetLanguage.ENGLISH.value,
        model_type: str = TranslationModelType.NLLB_DISTILLED_600M.value,
        batch_size: int = 16,
        cpu_threads: int = 4,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> List[SubtitleSegment]:
        """
        Translate a list of SubtitleSegments while strictly preserving
        their original index, start time, end time, and structure.
        """
        if not segments:
            return []

        # If target language is English, NO translation is performed
        if target_lang == TargetLanguage.ENGLISH.value:
            get_logger().info("Target language is English; skipping translation entirely.")
            return segments

        backend = self.load_model(
            model_type=model_type,
            cpu_threads=cpu_threads,
            progress_callback=progress_callback,
            is_cancelled=is_cancelled,
        )

        total_segments = len(segments)
        get_logger().info(
            f"Translating {total_segments} subtitle segments ({source_lang} -> {target_lang}) in batches of {batch_size}..."
        )
        if progress_callback:
            progress_callback(f"Translating {total_segments} subtitles to Persian...", 5.0)

        translated_segments: List[SubtitleSegment] = []

        # Process in batches
        for i in range(0, total_segments, batch_size):
            if is_cancelled and is_cancelled():
                get_logger().info("Translation cancelled by user.")
                raise InterruptedError("Subtitle translation cancelled by user.")

            batch = segments[i : i + batch_size]
            batch_texts = [seg.text for seg in batch]

            try:
                translated_texts = backend.translate_batch(
                    batch_texts,
                    source_lang=source_lang,
                    target_lang=target_lang,
                )
            except Exception as e:
                get_logger().error(f"Error during translation batch [{i}:{i+batch_size}]: {e}")
                raise RuntimeError(f"Translation inference error: {e}")

            # Verify 1-to-1 correspondence
            if len(translated_texts) != len(batch):
                raise ValueError(
                    f"Translation length mismatch: expected {len(batch)} items, received {len(translated_texts)}"
                )

            for original_seg, fa_text in zip(batch, translated_texts):
                # Clean and normalize Persian typography
                cleaned_fa = PersianTextNormalizer.normalize(fa_text)
                if not cleaned_fa.strip():
                    # Fallback to original text if translation was unexpectedly blank
                    cleaned_fa = original_seg.text

                # Strict timestamp & index preservation
                new_segment = SubtitleSegment(
                    index=original_seg.index,
                    start=original_seg.start,
                    end=original_seg.end,
                    text=cleaned_fa,
                    words=original_seg.words,
                )
                translated_segments.append(new_segment)

            if progress_callback:
                pct = min(98.0, 5.0 + (len(translated_segments) / total_segments) * 90.0)
                progress_callback(
                    f"Translated {len(translated_segments)} of {total_segments} segments...", pct
                )

        get_logger().info(
            f"Subtitle translation complete: {len(translated_segments)} segments translated to {target_lang}."
        )
        if progress_callback:
            progress_callback("Translation finished successfully.", 100.0)

        return translated_segments
