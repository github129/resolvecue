"""``cue.utils.color`` のテスト。"""
from __future__ import annotations

import pytest

from cue.utils import color


def test_parse_hex_full_form():
    assert color.parse_hex("#FFFFFF") == (255, 255, 255)
    assert color.parse_hex("#000000") == (0, 0, 0)
    assert color.parse_hex("FFD700") == (255, 215, 0)


def test_parse_hex_short_form():
    assert color.parse_hex("#FFF") == (255, 255, 255)
    assert color.parse_hex("F0A") == (255, 0, 170)


def test_parse_hex_invalid_raises():
    with pytest.raises(color.InvalidHexColorError):
        color.parse_hex("not a color")
    with pytest.raises(color.InvalidHexColorError):
        color.parse_hex("#GGGGGG")
    with pytest.raises(color.InvalidHexColorError):
        color.parse_hex("#1234")  # 4桁は不正


def test_hex_to_rgb_float():
    r, g, b = color.hex_to_rgb_float("#FFFFFF")
    assert (r, g, b) == (1.0, 1.0, 1.0)
    r, g, b = color.hex_to_rgb_float("#000000")
    assert (r, g, b) == (0.0, 0.0, 0.0)


def test_hex_to_rgba_float_with_opacity():
    r, g, b, a = color.hex_to_rgba_float("#FFFFFF", opacity_pct=80.0)
    assert (r, g, b) == (1.0, 1.0, 1.0)
    assert a == pytest.approx(0.8)


def test_hex_to_rgba_float_rejects_out_of_range_opacity():
    with pytest.raises(ValueError):
        color.hex_to_rgba_float("#FFFFFF", opacity_pct=120.0)
    with pytest.raises(ValueError):
        color.hex_to_rgba_float("#FFFFFF", opacity_pct=-1.0)


def test_rgb_float_to_hex_round_trip():
    h = color.rgb_float_to_hex((1.0, 215 / 255, 0.0))
    assert h == "#FFD700"
