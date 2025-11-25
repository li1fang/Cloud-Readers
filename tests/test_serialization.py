from __future__ import annotations

import json
from pathlib import Path
import logging
import sys
import importlib.util

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from typer.testing import CliRunner

from cloud_readers.protos import rcp_2025_pb2
from cloud_readers.cli import app
from cloud_readers.serialization import rcp

_serialization_path = Path(__file__).resolve().parents[1] / "src" / "cloud_readers" / "serialization.py"
_serialization_spec = importlib.util.spec_from_file_location("cloud_readers.serialization_runtime", _serialization_path)
serialization = importlib.util.module_from_spec(_serialization_spec)
assert _serialization_spec and _serialization_spec.loader
sys.modules[_serialization_spec.name] = serialization
_serialization_spec.loader.exec_module(serialization)


EXAMPLE_MANIFEST = rcp_2025_pb2.Manifest(
    version="rcp_2025",
    package_id="demo-package",
    source="van_gogh/sketch", 
    device_profile="pixel_4",
    dpi=300.0,
    created_at="2025-01-02T03:04:05Z",
    attributes={"style": "aggressive", "locale": "zh-CN"},
)

EXAMPLE_TOUCH = rcp_2025_pb2.TouchChannel(
    t=[0, 50_000, 100_000],
    x=[0.0, 1.0, 2.0],
    y=[0.0, 1.5, 3.0],
    pressure=[0.5, 0.55, 0.6],
    size=[1.0, 1.1, 1.2],
)

EXAMPLE_ACC = rcp_2025_pb2.AccChannel(
    t=[0, 50_000, 100_000],
    x=[0.0, 0.01, 0.02],
    y=[-0.01, -0.005, 0.0],
    z=[1.0, 1.0, 1.0],
)

EXAMPLE_GYRO = rcp_2025_pb2.GyroChannel(
    t=[0, 40_000, 80_000],
    x=[0.0, 0.1, 0.2],
    y=[0.0, 0.05, 0.1],
    z=[0.0, 0.025, 0.05],
)


def test_write_and_read_round_trip(tmp_path: Path) -> None:
    package_root = tmp_path / "rcp_sample"
    index = rcp.write_package(package_root, EXAMPLE_MANIFEST, EXAMPLE_TOUCH, EXAMPLE_ACC, EXAMPLE_GYRO)

    # Verify channel round-trip.
    loaded_touch = rcp.read_channel_pbz(package_root / "channels" / "touch.pbz", rcp_2025_pb2.TouchChannel)
    loaded_acc = rcp.read_channel_pbz(package_root / "channels" / "acc.pbz", rcp_2025_pb2.AccChannel)
    loaded_gyro = rcp.read_channel_pbz(package_root / "channels" / "gyro.pbz", rcp_2025_pb2.GyroChannel)

    assert loaded_touch.t == EXAMPLE_TOUCH.t
    assert loaded_touch.x == pytest.approx(EXAMPLE_TOUCH.x)
    assert loaded_touch.y == pytest.approx(EXAMPLE_TOUCH.y)
    assert loaded_touch.pressure == pytest.approx(EXAMPLE_TOUCH.pressure)
    assert loaded_touch.size == pytest.approx(EXAMPLE_TOUCH.size)

    assert loaded_acc.t == EXAMPLE_ACC.t
    assert loaded_acc.x == pytest.approx(EXAMPLE_ACC.x)
    assert loaded_acc.y == pytest.approx(EXAMPLE_ACC.y)
    assert loaded_acc.z == pytest.approx(EXAMPLE_ACC.z)

    assert loaded_gyro.t == EXAMPLE_GYRO.t
    assert loaded_gyro.x == pytest.approx(EXAMPLE_GYRO.x)
    assert loaded_gyro.y == pytest.approx(EXAMPLE_GYRO.y)
    assert loaded_gyro.z == pytest.approx(EXAMPLE_GYRO.z)

    manifest_json = json.loads((package_root / "manifest.json").read_text())
    assert manifest_json["package_id"] == "demo-package"
    assert manifest_json["attributes"]["style"] == "aggressive"

    index_json = json.loads((package_root / "index.json").read_text())
    assert index_json["touch_samples"] == 3
    assert index_json["duration_seconds"] == index.duration_seconds
    assert len(index_json["checksums"]) == 4

    checksum_lines = (package_root / "checksums.txt").read_text().strip().splitlines()
    assert all("  " in line for line in checksum_lines)


def test_cli_export_produces_rcp_package(tmp_path: Path) -> None:
    runner = CliRunner()
    extraction_dir = tmp_path / "extraction"
    simulation_dir = tmp_path / "simulation"
    package_root = tmp_path / "cli_package"
    extraction_dir.mkdir()
    simulation_dir.mkdir()

    extraction_payload = {
        "metadata": {
            "device": "pixel_4",
            "style": "calm",
            "source": "unit-test",
            "dpi": 320.0,
            "created_at": "2025-01-01T00:00:00Z",
        },
        "skeleton_points": [[0, 0], [1, 1], [2, 2]],
    }
    (extraction_dir / "extraction.json").write_text(json.dumps(extraction_payload))

    kinematics_payload = {
        "metadata": {"mean_velocity": 0.4},
        "points": [[0, 0], [1, 2], [2, 3], [3, 3]],
        "velocity": [0.1, 0.2, 0.3, 0.2],
        "curvature": [0.2, 0.25, 0.3, 0.35],
        "pressure": [0.9, 0.8, 0.7, 0.6],
        "size": [0.4, 0.5, 0.6, 0.7],
        "timestamps_us": [0, 50_000, 100_000, 150_000],
    }
    (extraction_dir / "kinematics.json").write_text(json.dumps(kinematics_payload))

    simulation_payload = {
        "metadata": {"physics_engine": "internal"},
        "accelerometer": {
            "t": [0, 5_000, 10_000, 15_000],
            "x": [0.0, 0.05, 0.1, 0.15],
            "y": [0.0, 0.0, 0.0, 0.0],
            "z": [-9.81, -9.80, -9.82, -9.80],
        },
        "gyroscope": {
            "t": [0, 5_000, 10_000, 15_000],
            "x": [0.0, 0.0, 0.0, 0.0],
            "y": [0.0, 0.0, 0.0, 0.0],
            "z": [0.0, 0.01, 0.02, 0.03],
        },
    }
    (simulation_dir / "simulation.json").write_text(json.dumps(simulation_payload))

    result = runner.invoke(
        app,
        [
            "export",
            "--extraction-dir",
            str(extraction_dir),
            "--simulation-dir",
            str(simulation_dir),
            "--out",
            str(package_root),
        ],
    )
    assert result.exit_code == 0, result.output

    paths = rcp.package_paths(package_root)
    assert paths.manifest_path.exists()
    assert paths.index_path.exists()
    assert paths.checksums_path.exists()
    assert paths.channels.touch_path.exists()

    touch = rcp.read_channel_pbz(paths.channels.touch_path, rcp_2025_pb2.TouchChannel)
    acc = rcp.read_channel_pbz(paths.channels.acc_path, rcp_2025_pb2.AccChannel)
    gyro = rcp.read_channel_pbz(paths.channels.gyro_path, rcp_2025_pb2.GyroChannel)

    assert touch.t == kinematics_payload["timestamps_us"]
    assert list(acc.t) == simulation_payload["accelerometer"]["t"]
    assert list(gyro.t) == simulation_payload["gyroscope"]["t"]
    assert acc.x[1] == pytest.approx(0.05)
    assert gyro.z[-1] == pytest.approx(0.03)

    manifest_json = json.loads(paths.manifest_path.read_text())
    assert manifest_json["version"] == "rcp_2025"
    assert manifest_json["attributes"]["style"] == "calm"

    index_json = json.loads(paths.index_path.read_text())
    assert index_json["touch_samples"] == len(kinematics_payload["points"])
    assert len(index_json["checksums"]) == 4
    assert "index.json" in paths.checksums_path.read_text()


def test_length_mismatch_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.pbz"
    bad_touch = rcp_2025_pb2.TouchChannel(t=[0, 1], x=[0.0], y=[0.0], pressure=[0.1], size=[0.2])
    try:
        rcp.write_channel_pbz(bad_touch, path)
    except ValueError:
        return
    assert False, "Expected length mismatch to raise"


def test_load_simulation_enforces_monotonic_timestamps(tmp_path: Path) -> None:
    payload = {
        "metadata": {"sample_rate_hz": 50},
        "accelerometer": {"t": [30, 10, 10], "x": [0, 1, 2], "y": [0, 1, 2], "z": [0, 1, 2]},
        "gyroscope": {"t": [5, 2, 4], "x": [0, 0, 0], "y": [0, 0, 0], "z": [1, 1, 1]},
    }
    sim_path = tmp_path / "simulation.json"
    sim_path.write_text(json.dumps(payload))

    logger = logging.getLogger("test")
    result = serialization.load_simulation(sim_path, logger)

    assert list(result.accelerometer.t) == [10, 11, 30]
    assert list(result.gyroscope.t) == [2, 4, 5]
