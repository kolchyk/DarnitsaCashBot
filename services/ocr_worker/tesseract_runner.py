from __future__ import annotations

import logging
import re
import shutil
from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
import pytesseract
from pytesseract import Output

from libs.common import AppSettings

from .preprocess import Artifact, PreprocessResult

LOGGER = logging.getLogger(__name__)


class TesseractRuntimeError(RuntimeError):
    """Raised when the OCR engine cannot complete successfully."""


@dataclass
class OcrToken:
    text: str
    confidence: float
    left: int
    top: int
    width: int
    height: int
    profile: str


@dataclass
class TesseractProfile:
    name: str
    psm: int
    oem: int = 1
    whitelist: str | None = None


@dataclass
class TesseractResult:
    tokens_by_profile: dict[str, list[OcrToken]]
    stats: dict[str, Any]
    artifacts: list[Artifact] = field(default_factory=list)


class TesseractRunner:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        else:
            # Auto-detect tesseract if not explicitly configured
            detected_path = self._find_tesseract()
            if detected_path:
                pytesseract.pytesseract.tesseract_cmd = detected_path
                LOGGER.info("Auto-detected tesseract at %s", detected_path)
        
        # Set TESSDATA_PREFIX - use configured value or auto-detect
        # Priority: 1) configured TESSDATA_DIR, 2) app tessdata_final (Heroku), 3) system paths
        tessdata_path = settings.tessdata_dir
        if not tessdata_path:
            # Check for app-local tessdata directory (created by post_compile script)
            # Try multiple possible locations for tessdata_final
            possible_app_paths = [
                Path("tessdata_final"),  # Relative to current working directory
                Path.cwd() / "tessdata_final",  # Explicitly relative to CWD
                Path(__file__).parent.parent.parent / "tessdata_final",  # Relative to this file
            ]
            
            app_tessdata = None
            for path_candidate in possible_app_paths:
                if path_candidate.exists() and any(path_candidate.glob("*.traineddata")):
                    app_tessdata = path_candidate
                    LOGGER.info("Found tessdata_final at %s", app_tessdata)
                    break
            
            if app_tessdata:
                tessdata_path = str(app_tessdata.absolute())
                # Verify Ukrainian language file exists
                ukr_file = app_tessdata / "ukr.traineddata"
                if not ukr_file.exists():
                    LOGGER.warning("Ukrainian language file not found at %s", ukr_file)
            else:
                LOGGER.info("tessdata_final not found, trying system paths")
                # Try system paths: versioned (Tesseract 5.x) then non-versioned
                versioned_path = "/usr/share/tesseract-ocr/5/tessdata"
                non_versioned_path = "/usr/share/tesseract-ocr/tessdata"
                if Path(versioned_path).exists():
                    tessdata_path = versioned_path
                    LOGGER.info("Using system tessdata at %s", tessdata_path)
                elif Path(non_versioned_path).exists():
                    tessdata_path = non_versioned_path
                    LOGGER.info("Using system tessdata at %s", tessdata_path)
                else:
                    # Default to versioned path (Tesseract 5.x standard)
                    tessdata_path = versioned_path
                    LOGGER.warning("System tessdata not found, defaulting to %s (may not exist)", tessdata_path)
        
        # Verify language files exist before setting TESSDATA_PREFIX
        tessdata_dir = Path(tessdata_path)
        if tessdata_dir.exists():
            available_langs = list(tessdata_dir.glob("*.traineddata"))
            lang_names = [f.stem for f in available_langs]
            LOGGER.info("Available language files: %s", ", ".join(lang_names) if lang_names else "none")
            
            # Check if configured languages are available
            # Parse languages from settings (format: "ukr", "ukr+eng", etc.)
            configured_langs = [lang.strip() for lang in settings.ocr_languages.split("+")]
            available_lang_names = [f.stem for f in available_langs]
            missing_langs = [lang for lang in configured_langs if lang not in available_lang_names]
            if missing_langs:
                LOGGER.error("Missing required language files: %s in %s", ", ".join(missing_langs), tessdata_path)
        else:
            LOGGER.error("TESSDATA directory does not exist: %s", tessdata_path)
        
        os.environ["TESSDATA_PREFIX"] = tessdata_path
        LOGGER.info("TESSDATA_PREFIX set to %s", tessdata_path)
        self.languages = settings.ocr_languages
        self.profiles = {
            "full": TesseractProfile(name="full", psm=4),
            "line_items": TesseractProfile(name="line_items", psm=6),
            "totals": TesseractProfile(name="totals", psm=7, whitelist="0123456789₴грн., "),
        }

    @staticmethod
    def _find_tesseract() -> str | None:
        """Find tesseract binary in common installation locations."""
        # First, try using shutil.which which checks PATH
        tesseract_path = shutil.which("tesseract")
        if tesseract_path:
            return tesseract_path
        
        # Common installation paths (especially for Heroku/apt buildpack)
        common_paths = [
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract",
            "/opt/homebrew/bin/tesseract",  # macOS Apple Silicon
            "/usr/local/opt/tesseract/bin/tesseract",  # macOS Homebrew
        ]
        
        for path in common_paths:
            if Path(path).exists() and os.access(path, os.X_OK):
                return path
        
        return None

    def run(self, preprocess_result: PreprocessResult) -> TesseractResult:
        base_image = Image.fromarray(preprocess_result.processed_image)
        oriented_full = self._apply_orientation(base_image, preprocess_result.metadata)
        image_map = {
            "full": oriented_full,
            "line_items": Image.fromarray(preprocess_result.crops["body"]),
            "totals": Image.fromarray(preprocess_result.crops["totals"]),
        }

        tokens_by_profile: dict[str, list[OcrToken]] = {}
        stats: dict[str, Any] = {}
        artifacts: list[Artifact] = []

        for key, profile in self.profiles.items():
            image = image_map.get(key)
            if image is None:
                LOGGER.warning("Missing image for profile %s", key)
                continue
            
            image_size = f"{image.width}x{image.height}" if hasattr(image, 'width') else "unknown"
            LOGGER.debug("Running Tesseract profile '%s' on image %s", key, image_size)
            
            profile_tokens, profile_stats, raw_artifact = self._run_profile(profile, image)
            tokens_by_profile[key] = profile_tokens
            stats[key] = profile_stats
            artifacts.append(raw_artifact)
            
            LOGGER.debug(
                "Profile '%s' completed: tokens=%d, mean_confidence=%.3f",
                key,
                profile_stats.get("token_count", 0),
                profile_stats.get("mean_confidence", 0.0),
            )

        total_tokens = sum(len(tokens) for tokens in tokens_by_profile.values())
        LOGGER.info(
            "Tesseract run completed: total_tokens=%d across %d profiles",
            total_tokens,
            len(tokens_by_profile),
        )
        
        return TesseractResult(tokens_by_profile=tokens_by_profile, stats=stats, artifacts=artifacts)

    def _run_profile(
        self,
        profile: TesseractProfile,
        image: Image.Image,
    ) -> tuple[list[OcrToken], dict[str, Any], Artifact]:
        config = f"--oem {profile.oem} --psm {profile.psm}"
        if profile.whitelist:
            config += f' -c tessedit_char_whitelist="{profile.whitelist}"'
        try:
            LOGGER.debug("Running Tesseract with lang=%s, config=%s, TESSDATA_PREFIX=%s", 
                        self.languages, config, os.environ.get("TESSDATA_PREFIX"))
            dict_output = pytesseract.image_to_data(
                image,
                lang=self.languages,
                config=config,
                output_type=Output.DICT,
            )
        except pytesseract.TesseractError as exc:  # pragma: no cover
            error_msg = str(exc)
            LOGGER.error("Tesseract error: %s (lang=%s, TESSDATA_PREFIX=%s)", 
                        error_msg, self.languages, os.environ.get("TESSDATA_PREFIX"))
            # Provide more helpful error message for missing language files
            if "Error opening data file" in error_msg or "Unable to load" in error_msg:
                error_msg = f"{error_msg} (Check if language files exist in TESSDATA_PREFIX={os.environ.get('TESSDATA_PREFIX')})"
            raise TesseractRuntimeError(error_msg) from exc

        tokens: list[OcrToken] = []
        confidences: list[float] = []
        low_confidence_count = 0
        
        for idx, text in enumerate(dict_output["text"]):
            cleaned = text.strip()
            conf_value = float(dict_output["conf"][idx]) if dict_output["conf"][idx] not in {"", "-1"} else 0.0
            conf_norm = max(conf_value, 0.0) / 100
            if not cleaned:
                continue
            
            if conf_norm < 0.5:
                low_confidence_count += 1
            
            confidences.append(conf_norm)
            tokens.append(
                OcrToken(
                    text=cleaned,
                    confidence=conf_norm,
                    left=int(dict_output["left"][idx]),
                    top=int(dict_output["top"][idx]),
                    width=int(dict_output["width"][idx]),
                    height=int(dict_output["height"][idx]),
                    profile=profile.name,
                )
            )
        
        if low_confidence_count > 0:
            LOGGER.warning(
                "Profile '%s': %d tokens with low confidence (<0.5) out of %d total",
                profile.name,
                low_confidence_count,
                len(tokens),
            )

        stats = {
            "token_count": len(tokens),
            "mean_confidence": float(np.mean(confidences)) if confidences else 0.0,
        }
        raw_tsv = pytesseract.image_to_data(
            image,
            lang=self.languages,
            config=config,
            output_type=Output.STRING,
        ).encode("utf-8")
        artifact = Artifact(
            name=f"ocr/{profile.name}.tsv",
            content=raw_tsv,
            content_type="text/tab-separated-values",
            metadata=stats,
        )
        return tokens, stats, artifact

    def _apply_orientation(self, image: Image.Image, metadata: dict[str, Any]) -> Image.Image:
        residual = abs(float(metadata.get("residual_skew", 0.0)))
        if residual <= 5:
            return image
        try:
            osd_output = pytesseract.image_to_osd(image, lang=self.languages)
        except pytesseract.TesseractError:
            return image
        angle = self._extract_angle(osd_output)
        if angle == 0:
            return image
        LOGGER.info("Applying OSD orientation correction angle=%s", angle)
        return image.rotate(-angle, expand=True, fillcolor=255)

    @staticmethod
    def _extract_angle(osd: str) -> int:
        match = re.search(r"Rotate: (?P<angle>\d+)", osd)
        if not match:
            return 0
        angle = int(match.group("angle"))
        return angle if angle in {0, 90, 180, 270} else 0

