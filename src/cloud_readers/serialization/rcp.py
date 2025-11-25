"""
RCP 2025 columnar serialization utilities.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple, Type

from cloud_readers.protos import rcp_2025_pb2
from cloud_readers.serialization import zstd_codec


@dataclass
class ChannelArtifacts:
    touch_path: Path
    acc_path: Path
    gyro_path: Path


@dataclass
class PackagePaths:
    root: Path
    channels: ChannelArtifacts
    manifest_path: Path
    index_path: Path
    checksums_path: Path


ChannelMessage = rcp_2025_pb2.TouchChannel | rcp_2025_pb2.AccChannel | rcp_2025_pb2.GyroChannel


def _ensure_lengths_match(values: Sequence[Sequence]) -> None:
    lengths = {len(v) for v in values}
    if len(lengths) > 1:
        raise ValueError(f"Mismatched column lengths: {sorted(lengths)}")


def _channel_duration(maybe_times: Sequence[int]) -> float:
    if not maybe_times:
        return 0.0
    if len(maybe_times) == 1:
        return maybe_times[0] / 1_000_000.0
    return (maybe_times[-1] - maybe_times[0]) / 1_000_000.0


def _message_to_json(payload) -> str:
    content = payload.to_dict()
    return json.dumps(content, indent=2, sort_keys=True)


def write_channel_pbz(channel: ChannelMessage, path: Path, compression_level: int = 3) -> None:
    """Serialize and compress a channel into ``.pbz`` format."""

    if isinstance(channel, rcp_2025_pb2.TouchChannel):
        _ensure_lengths_match([channel.t, channel.x, channel.y, channel.pressure, channel.size])
    elif isinstance(channel, (rcp_2025_pb2.AccChannel, rcp_2025_pb2.GyroChannel)):
        _ensure_lengths_match([channel.t, channel.x, channel.y, channel.z])

    raw = channel.SerializeToString()
    compressed = zstd_codec.compress(raw, level=compression_level)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(compressed)


def read_channel_pbz(path: Path, channel_cls: Type[ChannelMessage]) -> ChannelMessage:
    """Load and inflate a channel from disk."""

    compressed = path.read_bytes()
    raw = zstd_codec.decompress(compressed)
    message_obj = channel_cls()
    message_obj.ParseFromString(raw)
    return message_obj


def write_manifest(manifest: rcp_2025_pb2.Manifest, path: Path) -> None:
    path.write_text(_message_to_json(manifest))


def write_index(index: rcp_2025_pb2.Index, path: Path) -> None:
    path.write_text(_message_to_json(index))


def compute_checksums(paths: Iterable[Tuple[str, Path]], root: Path) -> List[rcp_2025_pb2.Checksum]:
    checksums: List[rcp_2025_pb2.Checksum] = []
    for relative, full in paths:
        digest = hashlib.sha256(full.read_bytes()).hexdigest()
        checksums.append(rcp_2025_pb2.Checksum(path=str(relative), sha256=digest))
    return checksums


def write_checksum_file(entries: Sequence[rcp_2025_pb2.Checksum], path: Path) -> None:
    lines = [f"{entry.sha256}  {entry.path}" for entry in entries]
    path.write_text("\n".join(lines) + "\n")


def build_index(
    manifest: rcp_2025_pb2.Manifest,
    channels: ChannelArtifacts,
) -> rcp_2025_pb2.Index:
    touch = read_channel_pbz(channels.touch_path, rcp_2025_pb2.TouchChannel)
    acc = read_channel_pbz(channels.acc_path, rcp_2025_pb2.AccChannel)
    gyro = read_channel_pbz(channels.gyro_path, rcp_2025_pb2.GyroChannel)

    durations = [
        _channel_duration(touch.t),
        _channel_duration(acc.t),
        _channel_duration(gyro.t),
    ]
    duration = max(durations) if durations else 0.0

    index = rcp_2025_pb2.Index(
        touch_samples=len(touch.t),
        acc_samples=len(acc.t),
        gyro_samples=len(gyro.t),
        duration_seconds=duration,
    )

    # Populate checksums after the caller has written the JSON metadata so
    # we can capture their digests accurately.
    return index


def package_paths(root: Path) -> PackagePaths:
    channels_dir = root / "channels"
    return PackagePaths(
        root=root,
        channels=ChannelArtifacts(
            touch_path=channels_dir / "touch.pbz",
            acc_path=channels_dir / "acc.pbz",
            gyro_path=channels_dir / "gyro.pbz",
        ),
        manifest_path=root / "manifest.json",
        index_path=root / "index.json",
        checksums_path=root / "checksums.txt",
    )


def write_package(
    root: Path,
    manifest: rcp_2025_pb2.Manifest,
    touch: rcp_2025_pb2.TouchChannel,
    acc: rcp_2025_pb2.AccChannel,
    gyro: rcp_2025_pb2.GyroChannel,
    compression_level: int = 3,
) -> rcp_2025_pb2.Index:
    paths = package_paths(root)
    paths.root.mkdir(parents=True, exist_ok=True)

    write_channel_pbz(touch, paths.channels.touch_path, compression_level)
    write_channel_pbz(acc, paths.channels.acc_path, compression_level)
    write_channel_pbz(gyro, paths.channels.gyro_path, compression_level)

    write_manifest(manifest, paths.manifest_path)

    index = build_index(manifest, paths.channels)

    checksum_inputs = [
        ("manifest.json", paths.manifest_path),
        ("channels/touch.pbz", paths.channels.touch_path),
        ("channels/acc.pbz", paths.channels.acc_path),
        ("channels/gyro.pbz", paths.channels.gyro_path),
    ]
    index.checksums.extend(compute_checksums(checksum_inputs, paths.root))

    write_index(index, paths.index_path)

    # Append the index checksum for the text file on disk.
    checksum_inputs.append(("index.json", paths.index_path))
    checksum_entries = compute_checksums(checksum_inputs, paths.root)
    write_checksum_file(checksum_entries, paths.checksums_path)

    return index
