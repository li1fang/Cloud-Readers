"""Serialization helpers for RCP-like bundles."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import numpy as np
import zstandard as zstd

from .extraction import ExtractionResult
from .kinematics import KinematicProfile, KinematicsResult
from .simulation import ChannelColumns, SimulationResult


@dataclass
class ExportBundle:
    """Aggregate of all pipeline outputs."""

    extraction: ExtractionResult
    kinematics: KinematicsResult
    simulation: SimulationResult


def _encode_array(array: np.ndarray) -> list[float]:
    return [float(v) for v in array.ravel()]


def _encode_channel(channel: ChannelColumns) -> Dict[str, list[float]]:
    return {
        "t": [int(v) for v in channel.t.ravel()],
        "x": _encode_array(channel.x),
        "y": _encode_array(channel.y),
        "z": _encode_array(channel.z),
    }


def persist_stage(data: Dict[str, Any], output_dir: Path, name: str, logger: logging.Logger) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{name}.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    logger.debug("Saved %s", path)
    return path


def export_bundle(bundle: ExportBundle, output_dir: Path, fmt: str, logger: logging.Logger) -> Path:
    """Serialize bundle to disk with lightweight compression."""

    logger.info("S05 serialization starting in %s format", fmt)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "format": fmt,
        "metadata": {
            **bundle.extraction.metadata,
            **bundle.kinematics.metadata,
            **bundle.simulation.metadata,
        },
        "counts": {
            "points": len(bundle.kinematics.profile.points),
            "accelerometer": len(bundle.simulation.accelerometer.t),
            "gyroscope": len(bundle.simulation.gyroscope.t),
        },
    }
    manifest_path = persist_stage(manifest, output_dir, "manifest", logger)

    channel_payload = {
        "points": bundle.kinematics.profile.points,
        "velocity": _encode_array(bundle.kinematics.profile.velocities),
        "curvature": _encode_array(bundle.kinematics.profile.curvature),
        "accelerometer": _encode_channel(bundle.simulation.accelerometer),
        "gyroscope": _encode_channel(bundle.simulation.gyroscope),
    }
    blob = json.dumps(channel_payload).encode("utf-8")
    compressed_path = output_dir / "channels.pbz"
    with compressed_path.open("wb") as handle:
        compressor = zstd.ZstdCompressor()
        handle.write(compressor.compress(blob))
    logger.debug("Saved compressed channels to %s", compressed_path)
    logger.info("S05 serialization complete")
    return manifest_path


def export_intermediate(extraction: ExtractionResult, output_dir: Path, logger: logging.Logger) -> Path:
    data = {
        "metadata": extraction.metadata,
        "skeleton_points": [[int(v) for v in pair] for pair in np.argwhere(extraction.skeleton)],
    }
    return persist_stage(data, output_dir, "extraction", logger)


def export_kinematics(kinematics: KinematicsResult, output_dir: Path, logger: logging.Logger) -> Path:
    data = {
        "metadata": kinematics.metadata,
        "points": kinematics.profile.points,
        "velocity": _encode_array(kinematics.profile.velocities),
        "curvature": _encode_array(kinematics.profile.curvature),
    }
    return persist_stage(data, output_dir, "kinematics", logger)


def export_simulation(simulation: SimulationResult, output_dir: Path, logger: logging.Logger) -> Path:
    data = {
        "metadata": simulation.metadata,
        "accelerometer": _encode_channel(simulation.accelerometer),
        "gyroscope": _encode_channel(simulation.gyroscope),
    }
    return persist_stage(data, output_dir, "simulation", logger)


def load_simulation(path: Path, logger: logging.Logger) -> SimulationResult:
    """Load simulation data stored by :func:`export_simulation`."""

    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)

    def _load_channel(payload: Dict[str, Any]) -> ChannelColumns:
        t = np.array(payload.get("t", []), dtype=np.int64)
        x = np.array(payload.get("x", []), dtype=float)
        y = np.array(payload.get("y", []), dtype=float)
        z = np.array(payload.get("z", []), dtype=float)

        if len(t) and (len(t) != len(x) or len(t) != len(y) or len(t) != len(z)):
            raise ValueError("Simulation channels must align t/x/y/z lengths")

        if len(t) > 1 and np.any(np.diff(t) <= 0):
            order = np.argsort(t, kind="stable")
            t, x, y, z = (arr[order] for arr in (t, x, y, z))

        if len(t) > 1:
            fixed_t = t.copy()
            for idx in range(1, len(fixed_t)):
                if fixed_t[idx] <= fixed_t[idx - 1]:
                    fixed_t[idx] = fixed_t[idx - 1] + 1
            t = fixed_t

        return ChannelColumns(t=t, x=x, y=y, z=z)

    accelerometer = _load_channel(data.get("accelerometer", {}))
    gyroscope = _load_channel(data.get("gyroscope", {}))
    metadata: Dict[str, Any] = data.get("metadata", {})
    logger.debug("Loaded simulation from %s", path)
    return SimulationResult(accelerometer=accelerometer, gyroscope=gyroscope, metadata=metadata)


def load_kinematics(path: Path, logger: logging.Logger) -> KinematicsResult:
    """Load kinematics data stored by :func:`export_kinematics`."""

    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)

    profile = KinematicProfile(
        points=data.get("points", []),
        velocities=np.array(data.get("velocity", []), dtype=float),
        curvature=np.array(data.get("curvature", []), dtype=float),
    )
    metadata: Dict[str, Any] = data.get("metadata", {})
    logger.debug("Loaded kinematics from %s", path)
    return KinematicsResult(profile=profile, metadata=metadata)
