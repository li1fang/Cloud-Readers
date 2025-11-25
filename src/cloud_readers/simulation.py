"""Simulation layer to synthesize IMU-like data."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Tuple

import numpy as np

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
    noise_std: float = 0.05
    gravity_vector: Tuple[float, float, float] = (0.0, 0.0, -9.81)
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


def _resample_series(values: np.ndarray, source_t: np.ndarray, target_t: np.ndarray) -> np.ndarray:
    """Resample a 1D series defined on microsecond timestamps to a new grid."""

    if len(values) != len(source_t):
        raise ValueError("Values and timestamps must share length for resampling")
    return np.interp(target_t, source_t, values)


def simulate_motion(
    kinematics: KinematicsResult,
    physics_engine: str,
    logger: logging.Logger,
    config: SimulationConfig | None = None,
) -> SimulationResult:
    """Generate synthetic IMU data from kinematic profiles.

    The synthesized channels follow the ``t/x/y/z`` layout used by RCP
    columnar definitions. Acceleration includes a gravity component (m/s^2)
    aligned to ``config.gravity_vector`` and gyroscope outputs are expressed
    in rad/s.
    """

    cfg = config or SimulationConfig()
    rng = np.random.default_rng(cfg.noise_seed)
    logger.info("S04 simulation starting using %s engine", physics_engine)

    base_times = kinematics.profile.timestamps_us
    if len(base_times) < 2:
        raise ValueError("Kinematics contain insufficient samples for simulation.")

    dt_us = int(round(1_000_000.0 / cfg.sample_rate_hz))
    target_times = np.arange(0, int(base_times[-1]) + dt_us, dt_us, dtype=np.int64)
    dt_seconds = 1.0 / cfg.sample_rate_hz

    points = np.array(kinematics.profile.points, dtype=float)
    x = _resample_series(points[:, 0], base_times, target_times)
    y = _resample_series(points[:, 1], base_times, target_times)
    speeds = _resample_series(kinematics.profile.velocities, base_times, target_times)

    dx = np.gradient(x, dt_seconds)
    dy = np.gradient(y, dt_seconds)
    direction = np.column_stack((dx, dy))
    direction_norm = np.linalg.norm(direction, axis=1, keepdims=True)
    direction_norm[direction_norm == 0] = 1.0
    velocity_vectors = (speeds[:, None] * direction) / direction_norm

    ax = np.gradient(velocity_vectors[:, 0], dt_seconds)
    ay = np.gradient(velocity_vectors[:, 1], dt_seconds)
    accel_body = np.column_stack((ax, ay, np.zeros_like(ax)))

    gravity_vec = np.array(cfg.gravity_vector, dtype=float)
    gravity_vec = gravity_vec if gravity_vec.shape == (3,) else _unit_vector(gravity_vec)
    accel = accel_body + gravity_vec
    accel += rng.normal(0.0, cfg.noise_std, size=accel.shape)

    heading = np.arctan2(velocity_vectors[:, 1], velocity_vectors[:, 0])
    gyro_z = np.gradient(heading, dt_seconds)
    gyro = np.column_stack((np.zeros_like(gyro_z), np.zeros_like(gyro_z), gyro_z))
    gyro += rng.normal(0.0, cfg.noise_std, size=gyro.shape)

    metadata: Dict[str, Any] = {
        "physics_engine": physics_engine,
        "accel_peak": float(np.max(np.abs(accel))) if accel.size else 0.0,
        "gyro_peak": float(np.max(np.abs(gyro))) if gyro.size else 0.0,
        "sample_rate_hz": float(cfg.sample_rate_hz),
        "gravity_vector": gravity_vec.tolist(),
        "noise_std": float(cfg.noise_std),
        "duration_us": int(target_times[-1]),
    }
    if cfg.noise_seed is not None:
        metadata["noise_seed"] = int(cfg.noise_seed)

    logger.debug(
        "Simulated accel peak=%.4f gyro peak=%.4f with sample_rate=%.1f",
        metadata["accel_peak"],
        metadata["gyro_peak"],
        cfg.sample_rate_hz,
    )
    logger.info("S04 simulation complete")

    return SimulationResult(
        accelerometer=ChannelColumns(t=target_times, x=accel[:, 0], y=accel[:, 1], z=accel[:, 2]),
        gyroscope=ChannelColumns(t=target_times, x=gyro[:, 0], y=gyro[:, 1], z=gyro[:, 2]),
        metadata=metadata,
    )
