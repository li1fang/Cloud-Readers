"""Kinematics reconstruction leveraging the Two-Thirds Power Law."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List

import numpy as np

from .extraction import ExtractionResult, summarize_points


@dataclass
class KinematicProfile:
    """Velocity and curvature profile reconstructed from the artwork."""

    points: List[List[int]]
    velocities: np.ndarray
    curvature: np.ndarray


@dataclass
class KinematicsResult:
    """Combined kinematics and metadata."""

    profile: KinematicProfile
    metadata: Dict[str, float]


def reconstruct_power_law(extraction: ExtractionResult, logger: logging.Logger) -> KinematicsResult:
    """Reconstruct trajectory velocities using the Two-Thirds Power Law."""

    logger.info("S03 kinematics reconstruction starting")
    points = summarize_points(extraction.skeleton)
    if not points:
        raise ValueError("No stroke skeleton available for kinematics reconstruction.")

    arr = np.array(points, dtype=float)
    diffs = np.diff(arr, axis=0)
    curvature = np.hypot(diffs[:, 0], diffs[:, 1])
    curvature[curvature == 0] = 1e-6

    gain = 0.8
    velocities = gain * np.power(curvature, -1 / 3)
    logger.debug("Velocity profile min=%.4f max=%.4f", velocities.min(), velocities.max())

    metadata: Dict[str, float] = {
        "power_law_gain": gain,
        "mean_velocity": float(velocities.mean()),
        "max_velocity": float(velocities.max()),
    }
    logger.info("S03 kinematics reconstruction complete")

    profile = KinematicProfile(points=points, velocities=velocities, curvature=curvature)
    return KinematicsResult(profile=profile, metadata=metadata)
