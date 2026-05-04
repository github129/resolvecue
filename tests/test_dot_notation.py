"""``Effect.apply_preset`` のドット記法対応テスト + ``_set_nested`` ヘルパ。"""
from __future__ import annotations

from dataclasses import dataclass, field

from cue.effects.base import _set_nested


@dataclass
class _Nested:
    value: int = 0
    color: str = ""


@dataclass
class _Outer:
    name: str = ""
    nested: _Nested = field(default_factory=_Nested)


def test_set_nested_writes_to_top_level_field():
    obj = _Outer()
    assert _set_nested(obj, "name", "hello") is True
    assert obj.name == "hello"


def test_set_nested_writes_to_nested_field():
    obj = _Outer()
    assert _set_nested(obj, "nested.value", 42) is True
    assert obj.nested.value == 42


def test_set_nested_returns_false_for_missing_field():
    obj = _Outer()
    assert _set_nested(obj, "missing", 1) is False


def test_set_nested_returns_false_for_missing_intermediate():
    obj = _Outer()
    assert _set_nested(obj, "missing.nested", 1) is False


def test_set_nested_handles_multi_level_paths():
    @dataclass
    class _DeepInner:
        x: int = 0

    @dataclass
    class _DeepMid:
        inner: _DeepInner = field(default_factory=_DeepInner)

    @dataclass
    class _DeepOuter:
        mid: _DeepMid = field(default_factory=_DeepMid)

    obj = _DeepOuter()
    assert _set_nested(obj, "mid.inner.x", 99) is True
    assert obj.mid.inner.x == 99
