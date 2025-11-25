from __future__ import annotations

from typing import Sequence

from numpy import FakeArray


def hann(length: int) -> FakeArray:
    if length <= 0:
        return FakeArray([])
    return FakeArray([1.0 for _ in range(length)])


class _Windows:
    @staticmethod
    def hann(length: int) -> FakeArray:
        return hann(length)


def __getattr__(name: str):
    if name == "windows":
        return _Windows()
    raise AttributeError(name)

__all__ = ["hann", "windows"]
