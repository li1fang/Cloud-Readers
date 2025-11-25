"""Simulation layer to synthesize IMU-like data."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict

import numpy as np
from scipy import signal

from .kinematics import KinematicsResult


@dataclass
class SimulationResult:
    """Simulated sensor channels derived from kinematic data."""

    accelerometer: np.ndarray
    gyroscope: np.ndarray
    metadata: Dict[str, float]


def simulate_motion(kinematics: KinematicsResult, physics_engine: str, logger: logging.Logger) -> SimulationResult:
    """Generate synthetic IMU data from kinematic profiles."""

    logger.info("S04 simulation starting using %s engine", physics_engine)
    velocities = kinematics.profile.velocities
    window = signal.windows.hann(min(len(velocities), 32))
    accel = np.convolve(velocities, window, mode="same")
    gyro = np.gradient(velocities)

    metadata = {
        "physics_engine": physics_engine,
        "accel_peak": float(np.max(accel)),
        "gyro_peak": float(np.max(np.abs(gyro))),
    }
    logger.debug("Simulated accel peak=%.4f gyro peak=%.4f", metadata["accel_peak"], metadata["gyro_peak"])
    logger.info("S04 simulation complete")

    return SimulationResult(
        accelerometer=accel,
        gyroscope=gyro,
        metadata=metadata,
    )
