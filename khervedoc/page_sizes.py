"""Paper-size constants in inches and the rendered pixel sizes at 96 DPI.

The editor's "page" widget is fixed to these dimensions so the on-screen
sheet has the same proportions as the printed PDF. The same identifiers
flow through to LaTeX's `geometry` package in the preamble.
"""
from __future__ import annotations

from dataclasses import dataclass


DPI = 96  # standard Qt logical DPI


@dataclass(frozen=True)
class PageSize:
    code: str            # short code used in the toolbar combo
    geometry_option: str # value passed to \usepackage[<this>]{geometry}
    width_in: float
    height_in: float

    @property
    def width_px(self) -> int:
        return round(self.width_in * DPI)

    @property
    def height_px(self) -> int:
        return round(self.height_in * DPI)


A4 = PageSize("A4", "a4paper", 8.27, 11.69)
LETTER = PageSize("Letter", "letterpaper", 8.5, 11.0)
LEGAL = PageSize("Legal", "legalpaper", 8.5, 14.0)

ALL: list[PageSize] = [A4, LETTER, LEGAL]


def by_code(code: str) -> PageSize:
    for p in ALL:
        if p.code.lower() == code.lower():
            return p
    return A4
