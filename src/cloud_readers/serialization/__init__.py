"""Expose helpers from the sibling ``serialization.py`` module."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_module_path = Path(__file__).resolve().parent.parent / "serialization.py"
_spec = importlib.util.spec_from_file_location("cloud_readers.serialization_module", _module_path)
_module = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)  # type: ignore[arg-type]

ExportBundle = _module.ExportBundle
bundle_to_acc_channel = _module.bundle_to_acc_channel
bundle_to_gyro_channel = _module.bundle_to_gyro_channel
bundle_to_manifest = _module.bundle_to_manifest
bundle_to_touch_channel = _module.bundle_to_touch_channel
export_bundle = _module.export_bundle
export_intermediate = _module.export_intermediate
export_kinematics = _module.export_kinematics
export_simulation = _module.export_simulation
load_kinematics = _module.load_kinematics
load_simulation = _module.load_simulation

__all__ = [
    "ExportBundle",
    "bundle_to_acc_channel",
    "bundle_to_gyro_channel",
    "bundle_to_manifest",
    "bundle_to_touch_channel",
    "export_bundle",
    "export_intermediate",
    "export_kinematics",
    "export_simulation",
    "load_kinematics",
    "load_simulation",
]
