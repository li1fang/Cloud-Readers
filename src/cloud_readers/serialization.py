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
from .simulation import SimulationResult


@dataclass
class ExportBundle:
    """Aggregate of all pipeline outputs."""

    extraction: ExtractionResult
    kinematics: KinematicsResult
    simulation: SimulationResult


def _encode_array(array: np.ndarray) -> list[float]:
    return [float(v) for v in array.ravel()]


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
            "accelerometer": len(bundle.simulation.accelerometer),
            "gyroscope": len(bundle.simulation.gyroscope),
        },
    }
    manifest_path = persist_stage(manifest, output_dir, "manifest", logger)

    channel_payload = {
        "points": bundle.kinematics.profile.points,
        "velocity": _encode_array(bundle.kinematics.profile.velocities),
        "curvature": _encode_array(bundle.kinematics.profile.curvature),
        "accelerometer": _encode_array(bundle.simulation.accelerometer),
        "gyroscope": _encode_array(bundle.simulation.gyroscope),
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
        "accelerometer": _encode_array(simulation.accelerometer),
        "gyroscope": _encode_array(simulation.gyroscope),
    }
    return persist_stage(data, output_dir, "simulation", logger)


def load_simulation(path: Path, logger: logging.Logger) -> SimulationResult:
    """Load simulation data stored by :func:`export_simulation`."""

    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)

    accelerometer = np.array(data.get("accelerometer", []), dtype=float)
    gyroscope = np.array(data.get("gyroscope", []), dtype=float)
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
