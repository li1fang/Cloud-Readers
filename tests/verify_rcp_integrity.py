from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pytest

from cloud_readers.protos import rcp_2025_pb2
from cloud_readers.serialization import rcp

pytestmark = pytest.mark.skip(reason="Utility script for Argo regression verification")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_monotonic(values: Iterable[int]) -> None:
    arr = np.array(list(values), dtype=np.int64)
    if len(arr) > 1:
        assert np.all(np.diff(arr) > 0), "timestamps must be strictly increasing"


def verify_package(package_root: Path) -> None:
    paths = rcp.package_paths(package_root)
    manifest = json.loads(paths.manifest_path.read_text())
    index = json.loads(paths.index_path.read_text())

    touch = rcp.read_channel_pbz(paths.channels.touch_path, rcp_2025_pb2.TouchChannel)
    acc = rcp.read_channel_pbz(paths.channels.acc_path, rcp_2025_pb2.AccChannel)
    gyro = rcp.read_channel_pbz(paths.channels.gyro_path, rcp_2025_pb2.GyroChannel)

    assert len(touch.t) == index["touch_samples"]
    _assert_monotonic(touch.t)
    _assert_monotonic(acc.t)
    _assert_monotonic(gyro.t)

    assert np.all(np.isfinite(acc.x))
    assert np.all(np.isfinite(gyro.z))

    checksum_lines = paths.checksums_path.read_text().strip().splitlines()
    assert checksum_lines, "checksums.txt must not be empty"
    checksum_map = {line.split("  ", 1)[1]: line.split("  ", 1)[0] for line in checksum_lines}

    for file_name, path in {
        "manifest.json": paths.manifest_path,
        "index.json": paths.index_path,
        "channels/touch.pbz": paths.channels.touch_path,
        "channels/acc.pbz": paths.channels.acc_path,
        "channels/gyro.pbz": paths.channels.gyro_path,
    }.items():
        assert file_name in checksum_map, f"Missing checksum for {file_name}"
        expected = checksum_map[file_name]
        actual = _hash_file(path)
        assert expected == actual, f"Checksum mismatch for {file_name}"  # pragma: no cover

    assert manifest["version"] == "rcp_2025"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate Cloud Readers RCP package integrity")
    parser.add_argument("--package", type=Path, required=True, help="Path to export directory")
    args = parser.parse_args()
    verify_package(args.package)
