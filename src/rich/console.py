from __future__ import annotations

class Console:
    def print(self, *args, **kwargs):  # noqa: D401
        """Lightweight print passthrough."""
        print(*args)
