from __future__ import annotations

import logging

import numpy as np

from cloud_readers.extraction import ExtractionResult
from cloud_readers.kinematics import reconstruct_power_law


LOGGER = logging.getLogger("test-kinematics")


def _make_diagonal_skeleton(size: int = 12) -> np.ndarray:
    skeleton = np.zeros((size, size), dtype=bool)
    for idx in range(2, size - 2):
        skeleton[idx, idx] = True
        skeleton[idx, max(1, idx - 2)] = True
    return skeleton


def test_two_thirds_power_law_monotonic_time() -> None:
    skeleton = _make_diagonal_skeleton()
    extraction = ExtractionResult(skeleton=skeleton, edges=np.zeros_like(skeleton, dtype=float), metadata={})

    result = reconstruct_power_law(extraction, LOGGER)

    assert np.all(np.diff(result.profile.timestamps_us) > 0)

    curvature_third = np.power(result.profile.curvature, 1.0 / 3.0)
    corr = np.corrcoef(curvature_third, result.profile.velocities)[0, 1]
    assert corr > 0.8
    assert result.profile.pressure.min() >= 0.0
    assert result.metadata["duration_us"] > 0
