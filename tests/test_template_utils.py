"""``cue.utils.template`` の単体テスト。"""
from __future__ import annotations

import pytest

from cue.utils import template


# ----- format_value -----


def test_format_value_int():
    assert template.format_value(42) == "42"
    assert template.format_value(0) == "0"
    assert template.format_value(-3) == "-3"


def test_format_value_bool_returns_numeric_string():
    """Fusion はブールを 1/0 で表現するので、True/False の str ではなく 1/0。"""
    assert template.format_value(True) == "1"
    assert template.format_value(False) == "0"


def test_format_value_float_uses_six_digits():
    assert template.format_value(0.5) == "0.500000"
    assert template.format_value(1.0) == "1.000000"
    assert template.format_value(-0.123456789) == "-0.123457"  # 丸め


def test_format_value_string_passthrough():
    assert template.format_value("hello") == "hello"


# ----- render_template -----


def test_render_replaces_simple_placeholders():
    out = template.render_template("a={{X}}, b={{Y}}", {"X": 1, "Y": 2.5})
    assert out == "a=1, b=2.500000"


def test_render_strict_raises_on_missing():
    with pytest.raises(template.UnresolvedPlaceholderError) as ei:
        template.render_template("hello {{NAME}}", {})
    assert "NAME" in str(ei.value)


def test_render_strict_aggregates_all_missing():
    with pytest.raises(template.UnresolvedPlaceholderError) as ei:
        template.render_template("{{A}} {{B}} {{A}} {{C}}", {"B": 1})
    msg = str(ei.value)
    assert "A" in msg and "C" in msg
    # B は解決できているので含まれない
    assert "{{B}}" not in msg


def test_render_non_strict_keeps_unresolved():
    out = template.render_template("{{A}} {{B}}", {"A": 1}, strict=False)
    assert out == "1 {{B}}"


def test_render_ignores_lower_case_pseudo_placeholders():
    """``{{x}}`` (小文字) はプレースホルダ正規表現にマッチしない。"""
    out = template.render_template("{{x}} and {{X}}", {"X": 9})
    # 小文字 x はそのまま、大文字 X だけ置換される
    assert out == "{{x}} and 9"


def test_find_placeholders_dedupes_and_preserves_order():
    found = template.find_placeholders("{{A}} {{B}} {{A}} {{C}}")
    assert found == ["A", "B", "C"]


# ----- escape_lua_string -----


def test_escape_lua_string_handles_backslash_first():
    assert template.escape_lua_string("a\\b") == "a\\\\b"


def test_escape_lua_string_quotes_and_newlines():
    s = 'line1\nline2 "quoted"\ttab'
    out = template.escape_lua_string(s)
    assert out == 'line1\\nline2 \\"quoted\\"\\ttab'


def test_escape_lua_string_strips_carriage_return():
    """CRLF は LF に正規化される (Windows コピペ対策)。"""
    out = template.escape_lua_string("a\r\nb")
    assert out == "a\\nb"
