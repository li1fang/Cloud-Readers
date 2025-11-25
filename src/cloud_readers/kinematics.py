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

    points: List[List[float]]
    velocities: np.ndarray
    curvature: np.ndarray
    pressure: np.ndarray
    size: np.ndarray
    timestamps_us: np.ndarray


@dataclass
class KinematicsResult:
    """Combined kinematics and metadata."""

    profile: KinematicProfile
    metadata: Dict[str, float]


def reconstruct_power_law(extraction: ExtractionResult, logger: logging.Logger) -> KinematicsResult:
    """Reconstruct trajectory velocities using the Two-Thirds Power Law."""

    logger.info("S03 kinematics reconstruction starting")
    points = summarize_points(extraction.skeleton)
    if len(points) < 2:
        raise ValueError("No stroke skeleton available for kinematics reconstruction.")

    coords = np.array(points, dtype=float)
    min_xy = coords.min(axis=0)
    span_xy = np.maximum(np.ptp(coords, axis=0), 1e-6)
    normalized_points = (coords - min_xy) / span_xy

    dx_dt = np.gradient(normalized_points[:, 0])
    dy_dt = np.gradient(normalized_points[:, 1])
    ddx_dt = np.gradient(dx_dt)
    ddy_dt = np.gradient(dy_dt)

    denom = np.power(dx_dt**2 + dy_dt**2 + 1e-6, 1.5)
    curvature = np.abs(dx_dt * ddy_dt - dy_dt * ddx_dt) / denom
    curvature = np.clip(curvature, 1e-6, None)

    gain = 0.9
    velocities = gain * np.power(curvature, 1.0 / 3.0)
    logger.debug("Velocity profile min=%.4f max=%.4f", velocities.min(), velocities.max())

    segment_lengths = np.linalg.norm(np.diff(normalized_points, axis=0), axis=1)
    avg_vel = (velocities[:-1] + velocities[1:]) / 2.0
    dt_segments = np.where(avg_vel > 1e-6, segment_lengths / avg_vel, 1e-3)
    timestamps = np.concatenate([[0.0], np.cumsum(dt_segments)])
    timestamps_us = np.round(timestamps * 1_000_000).astype(np.int64)

    vel_norm = (velocities - velocities.min()) / (np.ptp(velocities) or 1.0)
    pressure = np.clip(1.0 - 0.6 * vel_norm, 0.05, 1.0)
    size = np.clip(np.power(curvature / (curvature.max() or 1.0), 0.25), 0.05, 1.0)

    metadata: Dict[str, float] = {
        "power_law_gain": gain,
        "mean_velocity": float(velocities.mean()),
        "max_velocity": float(velocities.max()),
        "duration_us": int(timestamps_us[-1]),
        "median_curvature": float(np.median(curvature)),
        "point_count": int(len(normalized_points)),
    }
    logger.info("S03 kinematics reconstruction complete")

    profile = KinematicProfile(
        points=[[float(x), float(y)] for x, y in normalized_points],
        velocities=velocities,
        curvature=curvature,
        pressure=pressure,
        size=size,
        timestamps_us=timestamps_us,
    )
    return KinematicsResult(profile=profile, metadata=metadata)
