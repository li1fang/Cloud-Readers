"""
Lightweight protobuf-compatible message classes for the RCP 2025 schema.

The standard ``google.protobuf`` Python runtime is not available in the
execution environment, so this module implements a minimal subset of the
serialization logic required by the Cloud Readers tooling. The wire format
follows standard protobuf encoding rules for the supported field types.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Tuple


# --- Wire helpers ---------------------------------------------------------

def _encode_tag(field_number: int, wire_type: int) -> bytes:
    return _encode_varint((field_number << 3) | wire_type)


def _encode_varint(value: int) -> bytes:
    out = bytearray()
    while True:
        to_write = value & 0x7F
        value >>= 7
        if value:
            out.append(to_write | 0x80)
        else:
            out.append(to_write)
            break
    return bytes(out)


def _decode_varint(data: bytes, pos: int) -> Tuple[int, int]:
    shift = 0
    result = 0
    while True:
        if pos >= len(data):
            raise ValueError("Truncated varint")
        byte = data[pos]
        result |= (byte & 0x7F) << shift
        pos += 1
        if not (byte & 0x80):
            break
        shift += 7
    return result, pos


def _encode_length_delimited(payload: bytes) -> bytes:
    return _encode_varint(len(payload)) + payload


def _decode_length_delimited(data: bytes, pos: int) -> Tuple[bytes, int]:
    length, pos = _decode_varint(data, pos)
    end = pos + length
    return data[pos:end], end


def _encode_double(value: float) -> bytes:
    return struct.pack("<d", value)


def _decode_double(data: bytes, pos: int) -> Tuple[float, int]:
    end = pos + 8
    return struct.unpack("<d", data[pos:end])[0], end


def _encode_float(value: float) -> bytes:
    return struct.pack("<f", value)


def _decode_float(data: bytes, pos: int) -> Tuple[float, int]:
    end = pos + 4
    return struct.unpack("<f", data[pos:end])[0], end


# --- Message definitions --------------------------------------------------


@dataclass
class Checksum:
    path: str = ""
    sha256: str = ""

    def SerializeToString(self) -> bytes:
        parts = []
        if self.path:
            parts.append(_encode_tag(1, 2) + _encode_length_delimited(self.path.encode()))
        if self.sha256:
            parts.append(_encode_tag(2, 2) + _encode_length_delimited(self.sha256.encode()))
        return b"".join(parts)

    def ParseFromString(self, data: bytes) -> None:
        pos = 0
        self.path = ""
        self.sha256 = ""
        while pos < len(data):
            tag, pos = _decode_varint(data, pos)
            field_no, wire_type = tag >> 3, tag & 0x07
            if field_no == 1 and wire_type == 2:
                raw, pos = _decode_length_delimited(data, pos)
                self.path = raw.decode()
            elif field_no == 2 and wire_type == 2:
                raw, pos = _decode_length_delimited(data, pos)
                self.sha256 = raw.decode()
            else:
                raise ValueError(f"Unexpected field {field_no}")

    def to_dict(self) -> dict:
        return {"path": self.path, "sha256": self.sha256}


@dataclass
class Manifest:
    version: str = ""
    package_id: str = ""
    source: str = ""
    device_profile: str = ""
    dpi: float = 0.0
    created_at: str = ""
    attributes: Dict[str, str] = field(default_factory=dict)

    def SerializeToString(self) -> bytes:
        parts = []
        if self.version:
            parts.append(_encode_tag(1, 2) + _encode_length_delimited(self.version.encode()))
        if self.package_id:
            parts.append(_encode_tag(2, 2) + _encode_length_delimited(self.package_id.encode()))
        if self.source:
            parts.append(_encode_tag(3, 2) + _encode_length_delimited(self.source.encode()))
        if self.device_profile:
            parts.append(_encode_tag(4, 2) + _encode_length_delimited(self.device_profile.encode()))
        if self.dpi:
            parts.append(_encode_tag(5, 1) + _encode_double(self.dpi))
        if self.created_at:
            parts.append(_encode_tag(6, 2) + _encode_length_delimited(self.created_at.encode()))
        for key, value in self.attributes.items():
            entry = (
                _encode_tag(1, 2) + _encode_length_delimited(key.encode()) +
                _encode_tag(2, 2) + _encode_length_delimited(value.encode())
            )
            parts.append(_encode_tag(7, 2) + _encode_length_delimited(entry))
        return b"".join(parts)

    def ParseFromString(self, data: bytes) -> None:
        self.version = self.package_id = self.source = self.device_profile = self.created_at = ""
        self.dpi = 0.0
        self.attributes.clear()
        pos = 0
        while pos < len(data):
            tag, pos = _decode_varint(data, pos)
            field_no, wire_type = tag >> 3, tag & 0x07
            if field_no in {1, 2, 3, 4, 6} and wire_type == 2:
                raw, pos = _decode_length_delimited(data, pos)
                value = raw.decode()
                if field_no == 1:
                    self.version = value
                elif field_no == 2:
                    self.package_id = value
                elif field_no == 3:
                    self.source = value
                elif field_no == 4:
                    self.device_profile = value
                elif field_no == 6:
                    self.created_at = value
            elif field_no == 5 and wire_type == 1:
                self.dpi, pos = _decode_double(data, pos)
            elif field_no == 7 and wire_type == 2:
                raw, pos = _decode_length_delimited(data, pos)
                self._parse_attribute_entry(raw)
            else:
                raise ValueError(f"Unexpected field {field_no}")

    def _parse_attribute_entry(self, entry: bytes) -> None:
        pos = 0
        key = value = ""
        while pos < len(entry):
            tag, pos = _decode_varint(entry, pos)
            field_no, wire_type = tag >> 3, tag & 0x07
            if field_no in {1, 2} and wire_type == 2:
                raw, pos = _decode_length_delimited(entry, pos)
                if field_no == 1:
                    key = raw.decode()
                else:
                    value = raw.decode()
            else:
                raise ValueError("Unexpected map entry field")
        if key:
            self.attributes[key] = value

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "package_id": self.package_id,
            "source": self.source,
            "device_profile": self.device_profile,
            "dpi": self.dpi,
            "created_at": self.created_at,
            "attributes": dict(self.attributes),
        }


@dataclass
class Index:
    touch_samples: int = 0
    acc_samples: int = 0
    gyro_samples: int = 0
    duration_seconds: float = 0.0
    checksums: List[Checksum] = field(default_factory=list)

    def SerializeToString(self) -> bytes:
        parts = [
            _encode_tag(1, 0) + _encode_varint(self.touch_samples),
            _encode_tag(2, 0) + _encode_varint(self.acc_samples),
            _encode_tag(3, 0) + _encode_varint(self.gyro_samples),
            _encode_tag(4, 1) + _encode_double(self.duration_seconds),
        ]
        for checksum in self.checksums:
            payload = checksum.SerializeToString()
            parts.append(_encode_tag(5, 2) + _encode_length_delimited(payload))
        return b"".join(parts)

    def ParseFromString(self, data: bytes) -> None:
        self.touch_samples = self.acc_samples = self.gyro_samples = 0
        self.duration_seconds = 0.0
        self.checksums.clear()
        pos = 0
        while pos < len(data):
            tag, pos = _decode_varint(data, pos)
            field_no, wire_type = tag >> 3, tag & 0x07
            if field_no in {1, 2, 3} and wire_type == 0:
                value, pos = _decode_varint(data, pos)
                if field_no == 1:
                    self.touch_samples = value
                elif field_no == 2:
                    self.acc_samples = value
                else:
                    self.gyro_samples = value
            elif field_no == 4 and wire_type == 1:
                self.duration_seconds, pos = _decode_double(data, pos)
            elif field_no == 5 and wire_type == 2:
                raw, pos = _decode_length_delimited(data, pos)
                checksum = Checksum()
                checksum.ParseFromString(raw)
                self.checksums.append(checksum)
            else:
                raise ValueError(f"Unexpected field {field_no}")

    def to_dict(self) -> dict:
        return {
            "touch_samples": self.touch_samples,
            "acc_samples": self.acc_samples,
            "gyro_samples": self.gyro_samples,
            "duration_seconds": self.duration_seconds,
            "checksums": [c.to_dict() for c in self.checksums],
        }


@dataclass
class TouchChannel:
    t: List[int] = field(default_factory=list)
    x: List[float] = field(default_factory=list)
    y: List[float] = field(default_factory=list)
    pressure: List[float] = field(default_factory=list)
    size: List[float] = field(default_factory=list)

    def SerializeToString(self) -> bytes:
        parts = []
        parts.extend(_encode_tag(1, 0) + _encode_varint(value) for value in self.t)
        parts.extend(_encode_tag(2, 5) + _encode_float(value) for value in self.x)
        parts.extend(_encode_tag(3, 5) + _encode_float(value) for value in self.y)
        parts.extend(_encode_tag(4, 5) + _encode_float(value) for value in self.pressure)
        parts.extend(_encode_tag(5, 5) + _encode_float(value) for value in self.size)
        return b"".join(parts)

    def ParseFromString(self, data: bytes) -> None:
        self.t.clear(); self.x.clear(); self.y.clear(); self.pressure.clear(); self.size.clear()
        pos = 0
        while pos < len(data):
            tag, pos = _decode_varint(data, pos)
            field_no, wire_type = tag >> 3, tag & 0x07
            if field_no == 1 and wire_type == 0:
                value, pos = _decode_varint(data, pos)
                self.t.append(value)
            elif field_no == 2 and wire_type == 5:
                value, pos = _decode_float(data, pos)
                self.x.append(value)
            elif field_no == 3 and wire_type == 5:
                value, pos = _decode_float(data, pos)
                self.y.append(value)
            elif field_no == 4 and wire_type == 5:
                value, pos = _decode_float(data, pos)
                self.pressure.append(value)
            elif field_no == 5 and wire_type == 5:
                value, pos = _decode_float(data, pos)
                self.size.append(value)
            else:
                raise ValueError(f"Unexpected field {field_no}")

    def to_dict(self) -> dict:
        return {
            "t": list(self.t),
            "x": list(self.x),
            "y": list(self.y),
            "pressure": list(self.pressure),
            "size": list(self.size),
        }


@dataclass
class AccChannel:
    t: List[int] = field(default_factory=list)
    x: List[float] = field(default_factory=list)
    y: List[float] = field(default_factory=list)
    z: List[float] = field(default_factory=list)

    def SerializeToString(self) -> bytes:
        parts = []
        parts.extend(_encode_tag(1, 0) + _encode_varint(value) for value in self.t)
        parts.extend(_encode_tag(2, 5) + _encode_float(value) for value in self.x)
        parts.extend(_encode_tag(3, 5) + _encode_float(value) for value in self.y)
        parts.extend(_encode_tag(4, 5) + _encode_float(value) for value in self.z)
        return b"".join(parts)

    def ParseFromString(self, data: bytes) -> None:
        self.t.clear(); self.x.clear(); self.y.clear(); self.z.clear()
        pos = 0
        while pos < len(data):
            tag, pos = _decode_varint(data, pos)
            field_no, wire_type = tag >> 3, tag & 0x07
            if field_no == 1 and wire_type == 0:
                value, pos = _decode_varint(data, pos)
                self.t.append(value)
            elif field_no == 2 and wire_type == 5:
                value, pos = _decode_float(data, pos)
                self.x.append(value)
            elif field_no == 3 and wire_type == 5:
                value, pos = _decode_float(data, pos)
                self.y.append(value)
            elif field_no == 4 and wire_type == 5:
                value, pos = _decode_float(data, pos)
                self.z.append(value)
            else:
                raise ValueError(f"Unexpected field {field_no}")

    def to_dict(self) -> dict:
        return {"t": list(self.t), "x": list(self.x), "y": list(self.y), "z": list(self.z)}


@dataclass
class GyroChannel:
    t: List[int] = field(default_factory=list)
    x: List[float] = field(default_factory=list)
    y: List[float] = field(default_factory=list)
    z: List[float] = field(default_factory=list)

    def SerializeToString(self) -> bytes:
        parts = []
        parts.extend(_encode_tag(1, 0) + _encode_varint(value) for value in self.t)
        parts.extend(_encode_tag(2, 5) + _encode_float(value) for value in self.x)
        parts.extend(_encode_tag(3, 5) + _encode_float(value) for value in self.y)
        parts.extend(_encode_tag(4, 5) + _encode_float(value) for value in self.z)
        return b"".join(parts)

    def ParseFromString(self, data: bytes) -> None:
        self.t.clear(); self.x.clear(); self.y.clear(); self.z.clear()
        pos = 0
        while pos < len(data):
            tag, pos = _decode_varint(data, pos)
            field_no, wire_type = tag >> 3, tag & 0x07
            if field_no == 1 and wire_type == 0:
                value, pos = _decode_varint(data, pos)
                self.t.append(value)
            elif field_no == 2 and wire_type == 5:
                value, pos = _decode_float(data, pos)
                self.x.append(value)
            elif field_no == 3 and wire_type == 5:
                value, pos = _decode_float(data, pos)
                self.y.append(value)
            elif field_no == 4 and wire_type == 5:
                value, pos = _decode_float(data, pos)
                self.z.append(value)
            else:
                raise ValueError(f"Unexpected field {field_no}")

    def to_dict(self) -> dict:
        return {"t": list(self.t), "x": list(self.x), "y": list(self.y), "z": list(self.z)}
