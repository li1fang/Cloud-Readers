"""
Lightweight ctypes-backed Zstandard compression helpers.

We cannot rely on the Python ``zstandard`` wheel being present in the
execution environment, but the base image ships with ``libzstd``.  This
module exposes minimal ``compress`` and ``decompress`` helpers used by the
serialization utilities without introducing an additional runtime
dependency.
"""
from __future__ import annotations

import ctypes
import ctypes.util
from typing import ByteString


_lib_path = ctypes.util.find_library("zstd")
if not _lib_path:
    raise RuntimeError("libzstd is required to perform compression")

_lib = ctypes.CDLL(_lib_path)

# Configure function signatures we rely on.
_lib.ZSTD_compressBound.restype = ctypes.c_size_t
_lib.ZSTD_compressBound.argtypes = [ctypes.c_size_t]

_lib.ZSTD_compress.restype = ctypes.c_size_t
_lib.ZSTD_compress.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]

_lib.ZSTD_decompress.restype = ctypes.c_size_t
_lib.ZSTD_decompress.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]

_lib.ZSTD_isError.restype = ctypes.c_uint
_lib.ZSTD_isError.argtypes = [ctypes.c_size_t]

_lib.ZSTD_getErrorName.restype = ctypes.c_char_p
_lib.ZSTD_getErrorName.argtypes = [ctypes.c_size_t]

_lib.ZSTD_getFrameContentSize.restype = ctypes.c_ulonglong
_lib.ZSTD_getFrameContentSize.argtypes = [ctypes.c_void_p, ctypes.c_size_t]


ZSTD_CONTENTSIZE_ERROR = ctypes.c_ulonglong(~0).value
ZSTD_CONTENTSIZE_UNKNOWN = ctypes.c_ulonglong(~1).value


def _check_error(result: int) -> None:
    if _lib.ZSTD_isError(result):
        message = _lib.ZSTD_getErrorName(result)
        raise RuntimeError(message.decode("utf-8"))


def compress(data: ByteString, level: int = 3) -> bytes:
    """Compress a byte sequence using libzstd.

    Args:
        data: Raw bytes to compress.
        level: Compression level passed to ``ZSTD_compress``.

    Returns:
        Compressed byte sequence.
    """

    src = ctypes.create_string_buffer(bytes(data))
    src_size = len(data)
    dest_size = _lib.ZSTD_compressBound(src_size)
    dest = (ctypes.c_char * dest_size)()
    written = _lib.ZSTD_compress(dest, dest_size, ctypes.cast(src, ctypes.c_void_p), src_size, level)
    _check_error(written)
    return bytes(dest[:written])


def decompress(data: ByteString) -> bytes:
    """Decompress a zstandard frame produced by :func:`compress`."""

    src = ctypes.create_string_buffer(bytes(data))
    src_size = len(data)

    content_size = _lib.ZSTD_getFrameContentSize(ctypes.cast(src, ctypes.c_void_p), src_size)
    if content_size == ZSTD_CONTENTSIZE_ERROR:
        raise RuntimeError("Invalid zstd frame")
    if content_size == ZSTD_CONTENTSIZE_UNKNOWN:
        # Fallback to a modest growth strategy when the content size is
        # not embedded in the frame header.
        content_size = max(src_size * 4, 1024)

    while True:
        dest = (ctypes.c_char * content_size)()
        decoded = _lib.ZSTD_decompress(dest, content_size, ctypes.cast(src, ctypes.c_void_p), src_size)
        if not _lib.ZSTD_isError(decoded):
            return bytes(dest[:decoded])
        # Grow the output buffer and retry.
        content_size *= 2
        if content_size > (1 << 30):
            # Avoid unbounded allocations.
            message = _lib.ZSTD_getErrorName(decoded)
            raise RuntimeError(message.decode("utf-8"))
