"""Simulation layer to synthesize IMU-like data."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Tuple

import numpy as np
from scipy import signal

from .kinematics import KinematicsResult


@dataclass
class ChannelColumns:
    """Column-wise channel representation aligned to RCP fields."""

    t: np.ndarray
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray


@dataclass
class SimulationConfig:
    """Configuration controlling the IMU synthesis."""

    sample_rate_hz: float = 200.0
    noise_std: float = 0.01
    gravity_direction: Tuple[float, float, float] = (0.0, 0.0, -1.0)
    noise_seed: int | None = None


@dataclass
class SimulationResult:
    """Simulated sensor channels derived from kinematic data."""

    accelerometer: ChannelColumns
    gyroscope: ChannelColumns
    metadata: Dict[str, Any]


def _unit_vector(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    if norm == 0:
        return np.array([0.0, 0.0, -1.0])
    return vector / norm


def _unitize_columns(columns: np.ndarray) -> np.ndarray:
    max_abs = np.max(np.abs(columns)) if columns.size else 1.0
    if max_abs == 0:
        return columns
    return columns / max_abs


def simulate_motion(
    kinematics: KinematicsResult,
    physics_engine: str,
    logger: logging.Logger,
    config: SimulationConfig | None = None,
) -> SimulationResult:
    """Generate synthetic IMU data from kinematic profiles.

    The synthesized channels follow the ``t/x/y/z`` layout used by RCP
    columnar definitions. Acceleration includes a gravity component aligned
    to ``config.gravity_direction`` and all channels are normalized to
    unitless ranges for downstream compatibility.
    """

    cfg = config or SimulationConfig()
    rng = np.random.default_rng(cfg.noise_seed)
    logger.info("S04 simulation starting using %s engine", physics_engine)

    velocities = kinematics.profile.velocities
    dt = 1.0 / cfg.sample_rate_hz
    if velocities.size == 0:
        raise ValueError("Kinematics contain no velocity samples for simulation.")

    window = signal.windows.hann(min(len(velocities), 32))
    window = window / window.sum() if window.sum() else window
    smoothed_vel = signal.convolve(velocities, window, mode="same")

    points = np.array(kinematics.profile.points, dtype=float)
    directions = np.diff(points, axis=0)
    if directions.size == 0:
        directions = np.zeros((len(velocities), 2))
    unit_dirs = directions / np.linalg.norm(directions, axis=1, keepdims=True)
    unit_dirs[~np.isfinite(unit_dirs)] = 0.0

    accel_mag = np.gradient(smoothed_vel, dt, edge_order=1)
    accel_xy = accel_mag[:, None] * unit_dirs

    gravity_vec = _unit_vector(np.array(cfg.gravity_direction, dtype=float))
    accel = np.column_stack(
        (
            accel_xy[:, 0] + gravity_vec[0],
            accel_xy[:, 1] + gravity_vec[1],
            np.full(len(accel_mag), gravity_vec[2]),
        )
    )
    accel += rng.normal(0, cfg.noise_std, size=accel.shape)
    accel = _unitize_columns(accel)

    heading = np.arctan2(unit_dirs[:, 1], unit_dirs[:, 0])
    gyro_z = np.gradient(heading, dt, edge_order=1)
    gyro = np.column_stack((np.zeros_like(gyro_z), np.zeros_like(gyro_z), gyro_z))
    gyro += rng.normal(0, cfg.noise_std, size=gyro.shape)
    gyro = _unitize_columns(gyro)

    dt_us = int(round(1_000_000.0 / cfg.sample_rate_hz))
    times = np.arange(len(smoothed_vel), dtype=np.int64) * dt_us

    metadata: Dict[str, Any] = {
        "physics_engine": physics_engine,
        "accel_peak": float(np.max(np.abs(accel))) if accel.size else 0.0,
        "gyro_peak": float(np.max(np.abs(gyro))) if gyro.size else 0.0,
        "sample_rate_hz": float(cfg.sample_rate_hz),
        "filter": "hann",
        "noise_std": float(cfg.noise_std),
    }
    if cfg.noise_seed is not None:
        metadata["noise_seed"] = float(cfg.noise_seed)

    logger.debug(
        "Simulated accel peak=%.4f gyro peak=%.4f with sample_rate=%.1f",
        metadata["accel_peak"],
        metadata["gyro_peak"],
        cfg.sample_rate_hz,
    )
    logger.info("S04 simulation complete")

    return SimulationResult(
        accelerometer=ChannelColumns(t=times, x=accel[:, 0], y=accel[:, 1], z=accel[:, 2]),
        gyroscope=ChannelColumns(t=times, x=gyro[:, 0], y=gyro[:, 1], z=gyro[:, 2]),
        metadata=metadata,
    )
