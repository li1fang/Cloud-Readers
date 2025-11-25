from __future__ import annotations

from pathlib import Path

from cloud_readers.protos import rcp_2025_pb2
from cloud_readers.serialization import rcp


def build_manifest() -> rcp_2025_pb2.Manifest:
    return rcp_2025_pb2.Manifest(
        version="rcp_2025",
        package_id="sample-uuid",
        source="demo/calligraphy",
        device_profile="pixel_4",
        dpi=320.0,
        created_at="2025-05-06T07:08:09Z",
        attributes={"style": "demo", "author": "cloud_readers"},
    )


def build_channels():
    touch = rcp_2025_pb2.TouchChannel(
        t=[0, 20_000, 40_000, 60_000],
        x=[0.0, 0.5, 1.0, 1.5],
        y=[0.0, 0.25, 0.5, 0.75],
        pressure=[0.4, 0.45, 0.5, 0.55],
        size=[0.9, 0.95, 1.0, 1.05],
    )
    acc = rcp_2025_pb2.AccChannel(
        t=[0, 20_000, 40_000, 60_000],
        x=[0.0, 0.01, 0.02, 0.03],
        y=[0.0, -0.01, -0.02, -0.03],
        z=[1.0, 1.0, 1.0, 1.0],
    )
    gyro = rcp_2025_pb2.GyroChannel(
        t=[0, 20_000, 40_000, 60_000],
        x=[0.0, 0.02, 0.04, 0.06],
        y=[0.0, 0.01, 0.02, 0.03],
        z=[0.0, -0.01, -0.02, -0.03],
    )
    return touch, acc, gyro


def main() -> None:
    root = Path(__file__).parent / "rcp_2025_sample"
    manifest = build_manifest()
    touch, acc, gyro = build_channels()
    rcp.write_package(root, manifest, touch, acc, gyro)
    print(f"Sample package written to {root}")


if __name__ == "__main__":
    main()
