from __future__ import annotations


class Table:
    def __init__(self, title: str | None = None):
        self.title = title
        self.columns: list[str] = []
        self.rows: list[list[str]] = []

    def add_column(self, name: str, **_: object) -> None:
        self.columns.append(name)

    def add_row(self, *values: str) -> None:
        self.rows.append(list(values))
