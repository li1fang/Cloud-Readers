"""Ingestion layer for reading source artwork and metadata."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import cv2
import numpy as np


@dataclass
class IngestionConfig:
    """Configuration for ingesting a source image."""

    source: Path
    device: str
    style: str


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
    logger.debug("Ingestion metadata: %s", metadata)
    logger.info("S01 ingestion complete: %s", config.source)
    return IngestionResult(source=config.source, metadata=metadata, image=image)
