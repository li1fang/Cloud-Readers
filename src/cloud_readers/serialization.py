"""Serialization helpers for RCP-like bundles."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Sequence, Tuple

import numpy as np
from cloud_readers.protos import rcp_2025_pb2
from cloud_readers.serialization import rcp

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


def _normalize_timestamps(sample_count: int, spacing_us: int = 50_000) -> list[int]:
    return [int(i * spacing_us) for i in range(sample_count)]


def _expand_sequence(values: Sequence[float], length: int, *, default: float = 0.0) -> list[float]:
    if length <= 0:
        return []
    if not values:
        return [default for _ in range(length)]

    output = list(values)
    if len(output) < length:
        output.extend([output[-1]] * (length - len(output)))
    elif len(output) > length:
        output = output[:length]
    return [float(v) for v in output]


def _normalize_to_unit_range(values: Iterable[float], length: int) -> list[float]:
    expanded = _expand_sequence(list(values), length, default=0.0)
    if not expanded:
        return []
    max_abs = max(abs(v) for v in expanded) or 1.0
    return [float(v) / max_abs for v in expanded]


def _bundle_metadata(bundle: ExportBundle) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}
    metadata.update(bundle.extraction.metadata)
    metadata.update(bundle.kinematics.metadata)
    metadata.update(bundle.simulation.metadata)
    return metadata


def bundle_to_manifest(bundle: ExportBundle, version: str, package_id: str | None = None) -> rcp_2025_pb2.Manifest:
    metadata = _bundle_metadata(bundle)
    manifest = rcp_2025_pb2.Manifest(
        version=version,
        package_id=str(package_id or metadata.get("package_id") or uuid.uuid4().hex),
        source=str(metadata.pop("source", metadata.pop("source_path", "artwork"))),
        device_profile=str(metadata.pop("device", "generic")),
        dpi=float(metadata.pop("dpi", 300.0)),
        created_at=str(
            metadata.pop(
                "created_at",
                datetime.now(timezone.utc).replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
            )
        ),
        attributes={str(k): str(v) for k, v in metadata.items()},
    )
    return manifest


def bundle_to_touch_channel(bundle: ExportBundle, spacing_us: int = 50_000) -> rcp_2025_pb2.TouchChannel:
    points = bundle.kinematics.profile.points
    timestamps = _normalize_timestamps(len(points), spacing_us)
    xs: list[float] = []
    ys: list[float] = []
    for point in points:
        if len(point) >= 2:
            xs.append(float(point[0]))
            ys.append(float(point[1]))
        else:
            xs.append(0.0)
            ys.append(0.0)

    pressure = _normalize_to_unit_range(bundle.kinematics.profile.velocities, len(points))
    size = _normalize_to_unit_range(bundle.kinematics.profile.curvature, len(points))

    return rcp_2025_pb2.TouchChannel(t=timestamps, x=xs, y=ys, pressure=pressure, size=size)


def _split_axes(data: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    if data.ndim == 1:
        x = data.astype(float)
        y = np.zeros_like(x)
        z = np.ones_like(x)
    else:
        x = data[:, 0]
        y = data[:, 1] if data.shape[1] > 1 else np.zeros(data.shape[0])
        z = data[:, 2] if data.shape[1] > 2 else np.zeros(data.shape[0])
    return x, y, z


def bundle_to_acc_channel(bundle: ExportBundle, spacing_us: int = 50_000) -> rcp_2025_pb2.AccChannel:
    accel = np.atleast_1d(bundle.simulation.accelerometer)
    x, y, z = _split_axes(accel)
    timestamps = _normalize_timestamps(len(x), spacing_us)
    return rcp_2025_pb2.AccChannel(t=timestamps, x=_encode_array(x), y=_encode_array(y), z=_encode_array(z))


def bundle_to_gyro_channel(bundle: ExportBundle, spacing_us: int = 50_000) -> rcp_2025_pb2.GyroChannel:
    gyro = np.atleast_1d(bundle.simulation.gyroscope)
    x, y, z = _split_axes(gyro)
    timestamps = _normalize_timestamps(len(x), spacing_us)
    return rcp_2025_pb2.GyroChannel(t=timestamps, x=_encode_array(x), y=_encode_array(y), z=_encode_array(z))


def export_bundle(bundle: ExportBundle, output_dir: Path, fmt: str, logger: logging.Logger) -> Path:
    """Serialize bundle to disk in the rcp_2025 package layout."""

    logger.info("S05 serialization starting in %s format", fmt)
    manifest = bundle_to_manifest(bundle, fmt)
    touch = bundle_to_touch_channel(bundle)
    acc = bundle_to_acc_channel(bundle)
    gyro = bundle_to_gyro_channel(bundle)

    rcp.write_package(output_dir, manifest, touch, acc, gyro)
    paths = rcp.package_paths(output_dir)
    logger.info("S05 serialization complete: %s", output_dir)
    return paths.manifest_path


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
