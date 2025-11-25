"""Extraction layer for skeletonization and feature detection."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np
from skimage import color, filters, morphology

from .ingestion import IngestionResult


@dataclass
class ExtractionResult:
    """Result of feature extraction."""

    skeleton: np.ndarray
    edges: np.ndarray
    metadata: Dict[str, Any]


def extract_features(result: IngestionResult, logger: logging.Logger) -> ExtractionResult:
    """Extract edges and a lightweight skeleton from the ingested image."""

    logger.info("S02 extraction starting")
    grayscale = color.rgb2gray(result.image)
    edges = filters.sobel(grayscale)
    threshold = edges.mean() + edges.std()
    logger.debug("Edge threshold chosen at %.4f", threshold)

    mask = edges > threshold
    skeleton = morphology.skeletonize(mask)

    metadata = dict(result.metadata)
    metadata.update({
        "edge_threshold": float(threshold),
        "edge_density": float(mask.mean()),
    })
    logger.debug("Skeleton pixel count: %d", int(np.count_nonzero(skeleton)))
    logger.info("S02 extraction complete")
    return ExtractionResult(skeleton=skeleton, edges=edges, metadata=metadata)


def summarize_points(skeleton: np.ndarray) -> List[List[int]]:
    """Convert skeleton mask into a list of point coordinates."""

    y_coords, x_coords = np.nonzero(skeleton)
    return [[int(x), int(y)] for x, y in zip(x_coords, y_coords)]
