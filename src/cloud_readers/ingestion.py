"""Ingestion layer for reading source artwork and metadata."""

from __future__ import annotations

import logging
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import cv2
import numpy as np


@dataclass
class IngestionConfig:
    """Configuration for ingesting a source image."""

    source: Path
    device: str
    style: str
    dpi: Optional[float] = None
    device_profile_path: Optional[Path] = None
    json_config: Optional[Path] = None
    enable_generative_labels: bool = True
    gemini_model: str = "gemini-1.5-flash"


@dataclass
class IngestionResult:
    """Result of ingestion stage."""

    source: Path
    metadata: Dict[str, Any]
    image: np.ndarray


def ingest(config: IngestionConfig, logger: logging.Logger) -> IngestionResult:
    """Load the source image and attach metadata.

    Args:
        config: User supplied configuration.
        logger: Logger configured by the CLI.

    Returns:
        IngestionResult containing the raw image and contextual metadata.
    """

    logger.info("S01 ingestion starting for %s", config.source)
    if not config.source.exists():
        raise FileNotFoundError(f"Source image not found: {config.source}")

    image = cv2.imread(str(config.source))
    if image is None:
        raise ValueError(f"Unable to decode image at {config.source}")

    metadata = {
        "device": config.device,
        "style": config.style,
        "shape": image.shape,
    }
    if config.dpi is not None:
        metadata["dpi"] = float(config.dpi)
    if config.device_profile_path is not None:
        metadata["device_profile_path"] = str(config.device_profile_path)

    if config.json_config is not None:
        with config.json_config.open(encoding="utf-8") as handle:
            try:
                config_payload = json.load(handle)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON config at {config.json_config}: {exc}") from exc

        shape_params = config_payload.get("shape")
        noise_params = config_payload.get("noise")
        if shape_params is not None:
            metadata["shape_params"] = shape_params
        if noise_params is not None:
            metadata["noise_params"] = noise_params

    metadata.update(_attach_generative_labels(image, config, logger))
    logger.debug("Ingestion metadata: %s", metadata)
    logger.info("S01 ingestion complete: %s", config.source)
    return IngestionResult(source=config.source, metadata=metadata, image=image)


def _attach_generative_labels(image: np.ndarray, config: IngestionConfig, logger: logging.Logger) -> Dict[str, Any]:
    """Optionally enrich metadata with labels from Gemini.

    If ``config.enable_generative_labels`` is False or the API key is missing,
    the function returns an empty dictionary without raising.
    """

    if not config.enable_generative_labels:
        logger.info("Gemini labeling disabled by flag; skipping")
        return {}

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.info("GEMINI_API_KEY not set; skipping Gemini labeling")
        return {}

    try:
        import google.generativeai as genai
    except ImportError:
        logger.warning("google-generativeai not installed; skipping Gemini labeling")
        return {}

    try:
        success, buffer = cv2.imencode(".png", image)
        if not success:
            logger.warning("Could not encode image for Gemini; skipping")
            return {}

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(config.gemini_model)
        prompt = (
            "Generate concise JSON with 'image_labels' and 'style_labels' arrays "
            "describing the image content. Do not include any prose; only return valid JSON. "
            f"Style context: {config.style}"
        )
        response = model.generate_content(
            [
                prompt,
                {
                    "mime_type": "image/png",
                    "data": buffer.tobytes(),
                },
            ]
        )
        labels_text = response.text or ""
        labels = json.loads(labels_text)
        if not isinstance(labels, dict):
            logger.warning("Gemini response was not a JSON object; skipping")
            return {}
        return {
            "image_labels": labels.get("image_labels", []),
            "style_labels": labels.get("style_labels", []),
        }
    except Exception as exc:  # pragma: no cover - external service protection
        logger.warning("Gemini labeling failed: %s", exc)
        return {}
