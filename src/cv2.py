from __future__ import annotations

from numpy import FakeArray


def imread(path: str):
    # Return a dummy RGB pixel
    return FakeArray([[[0, 0, 0]]])
