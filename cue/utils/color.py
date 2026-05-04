"""色の表現変換。

UI では HEX 文字列 ("#FFFFFF") を扱い、Fusion の Text+ や Background ノードでは
RGB float (0.0-1.0) のタプルが必要なので、その間を変換する。
"""
from __future__ import annotations

import re

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")


class InvalidHexColorError(ValueError):
    """HEX 文字列の形式が不正なときに送出される。"""


def parse_hex(hex_color: str) -> tuple[int, int, int]:
    """``"#RRGGBB"`` または ``"#RGB"`` を ``(r, g, b)`` (0-255) に変換する。"""
    if not isinstance(hex_color, str):
        raise InvalidHexColorError(f"hex color must be str, got {type(hex_color).__name__}")
    m = _HEX_RE.match(hex_color.strip())
    if not m:
        raise InvalidHexColorError(f"invalid hex color: {hex_color!r}")
    body = m.group(1)
    if len(body) == 3:
        body = "".join(c * 2 for c in body)
    return int(body[0:2], 16), int(body[2:4], 16), int(body[4:6], 16)


def hex_to_rgb_float(hex_color: str) -> tuple[float, float, float]:
    """``"#FFFFFF"`` → ``(1.0, 1.0, 1.0)``。"""
    r, g, b = parse_hex(hex_color)
    return (r / 255.0, g / 255.0, b / 255.0)


def hex_to_rgba_float(
    hex_color: str, opacity_pct: float = 100.0
) -> tuple[float, float, float, float]:
    """``"#FFFFFF"`` + 透明度 (%) → ``(r, g, b, a)`` の 0.0-1.0 タプル。"""
    if not 0.0 <= opacity_pct <= 100.0:
        raise ValueError(f"opacity_pct must be in [0, 100], got {opacity_pct}")
    r, g, b = hex_to_rgb_float(hex_color)
    return (r, g, b, opacity_pct / 100.0)


def rgb_float_to_hex(rgb: tuple[float, float, float]) -> str:
    """``(1.0, 1.0, 1.0)`` → ``"#FFFFFF"``。"""
    r, g, b = (max(0, min(255, int(round(v * 255)))) for v in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"
