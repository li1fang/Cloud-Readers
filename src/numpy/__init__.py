"""Minimal numpy compatibility layer for restricted environments."""
from __future__ import annotations

import builtins
import math
from typing import Iterable, List, Sequence, Tuple


class FakeArray(list):
    def ravel(self):
        return list(_flatten(self))

    def astype(self, typ):
        return FakeArray([typ(v) for v in _flatten(self)])

    @property
    def ndim(self) -> int:
        if self and all(isinstance(v, (list, FakeArray)) for v in self):
            return 2
        return 1

    @property
    def shape(self) -> Tuple[int, ...]:
        if self.ndim == 2 and self:
            inner = self[0]
            inner_len = len(inner) if isinstance(inner, (list, FakeArray)) else 0
            return (len(self), inner_len)
        return (len(self),)


def _flatten(seq: Iterable) -> Iterable:
    for item in seq:
        if isinstance(item, (list, tuple, FakeArray)):
            yield from _flatten(item)
        else:
            yield item


def array(values, dtype=float):
    if isinstance(values, FakeArray):
        base = list(values)
    else:
        base = []
        for v in values:
            if isinstance(v, (list, tuple, FakeArray)):
                base.append(array(v, dtype))
            else:
                base.append(dtype(v))
    return FakeArray(base)


def zeros_like(values: Sequence) -> FakeArray:
    return FakeArray([0 for _ in values])


def ones_like(values: Sequence) -> FakeArray:
    return FakeArray([1 for _ in values])


def zeros(length: int) -> FakeArray:
    return FakeArray([0 for _ in range(length)])


def atleast_1d(values) -> FakeArray:
    if isinstance(values, (list, tuple, FakeArray)):
        return FakeArray(values)
    return FakeArray([values])


def argwhere(mask: Sequence[Sequence]) -> FakeArray:
    coords: List[List[int]] = []
    for i, row in enumerate(mask):
        for j, val in enumerate(row):
            if val:
                coords.append([i, j])
    return FakeArray(coords)


def nonzero(mask: Sequence[Sequence]) -> Tuple[FakeArray, FakeArray]:
    ys: List[int] = []
    xs: List[int] = []
    for y, row in enumerate(mask):
        for x, val in enumerate(row):
            if val:
                ys.append(y)
                xs.append(x)
    return FakeArray(ys), FakeArray(xs)


def count_nonzero(values: Sequence) -> int:
    return sum(1 for v in _flatten(values) if v)


def diff(values: Sequence[Sequence[float]], axis: int = 0) -> FakeArray:
    if axis != 0:
        raise NotImplementedError("Only axis=0 supported in fake numpy")
    return FakeArray([_subtract(b, a) for a, b in zip(values, values[1:])])


def _subtract(b, a):
    if isinstance(a, (list, FakeArray)) and isinstance(b, (list, FakeArray)):
        return FakeArray([bb - aa for aa, bb in zip(a, b)])
    return b - a


def hypot(x_vals: Sequence[float], y_vals: Sequence[float]) -> FakeArray:
    return FakeArray([math.hypot(x, y) for x, y in zip(x_vals, y_vals)])


def power(values: Sequence[float], exponent: float) -> FakeArray:
    return FakeArray([math.pow(v, exponent) for v in values])


def convolve(data: Sequence[float], window: Sequence[float], mode: str = "same") -> FakeArray:
    data_list = list(data)
    window_list = list(window)
    pad = len(window_list) // 2
    padded = [0.0] * pad + data_list + [0.0] * pad
    result: List[float] = []
    for i in range(len(data_list)):
        segment = padded[i : i + len(window_list)]
        acc = sum(a * b for a, b in zip(segment, window_list))
        result.append(acc)
    return FakeArray(result)


def gradient(data: Sequence[float]) -> FakeArray:
    data_list = list(data)
    if len(data_list) < 2:
        return FakeArray([0.0 for _ in data_list])
    grads = [data_list[1] - data_list[0]]
    for i in range(1, len(data_list) - 1):
        grads.append((data_list[i + 1] - data_list[i - 1]) / 2)
    grads.append(data_list[-1] - data_list[-2])
    return FakeArray(grads)


def max(values: Sequence[float]):  # type: ignore[override]
    return builtins.max(_flatten(values))


    def abs(values: Sequence[float]):  # type: ignore[override]
        return FakeArray([builtins.abs(v) for v in _flatten(values)])


def isscalar(value: object) -> bool:
    return not isinstance(value, (list, tuple, FakeArray))


ndarray = FakeArray
bool_ = bool


__all__ = [
    "FakeArray",
    "array",
    "zeros",
    "zeros_like",
    "ones_like",
    "atleast_1d",
    "argwhere",
    "nonzero",
    "count_nonzero",
    "diff",
    "hypot",
    "power",
    "convolve",
    "gradient",
    "max",
    "abs",
    "isscalar",
    "ndarray",
    "bool_",
]
