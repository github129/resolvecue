"""``cue.effects.arrow.ArrowEffect`` のロジックテスト。

Resolve 実機を使わず、``conftest`` の ``FakeResolveAPI`` 越しに動作確認する。
アセット PNG が無い環境では ``apply()`` の前段バリデーションでエラーになることを許容する。
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from cue import config
from cue.effects.arrow import ArrowEffect, ArrowParams


def test_presets_cover_all_directions():
    presets = ArrowEffect.presets()
    assert set(presets.keys()) == set(config.ARROW_DIRECTIONS.keys())


def test_apply_preset_updates_pos_xy():
    params = ArrowParams()
    ArrowEffect.apply_preset(params, "bottom_left")
    assert params.direction == "bottom_left"
    info = config.ARROW_DIRECTIONS["bottom_left"]
    assert params.pos_x == info["pos_x"]
    assert params.pos_y == info["pos_y"]


def test_validate_rejects_negative_duration():
    eff = ArrowEffect(ArrowParams(duration_sec=-1.0))
    errors = eff.validate()
    assert any("表示時間" in e for e in errors)


def test_validate_rejects_fade_longer_than_duration():
    eff = ArrowEffect(ArrowParams(duration_sec=1.0, fade_in_sec=0.6, fade_out_sec=0.6))
    errors = eff.validate()
    assert any("フェード" in e for e in errors)


def test_validate_rejects_unknown_direction():
    eff = ArrowEffect(ArrowParams(direction="diagonal_42deg"))
    errors = eff.validate()
    assert any("direction" in e for e in errors)


def test_clip_name_format_with_discriminator():
    name = config.make_clip_name("arrow", 1234, "tr")
    assert name == "cue_arrow_1234_tr"
    assert config.is_cue_clip(name)
    assert config.is_cue_clip(name, effect_name="arrow")
    assert not config.is_cue_clip(name, effect_name="frame")


def test_clip_name_format_without_discriminator():
    name = config.make_clip_name("zoom", 9999)
    assert name == "cue_zoom_9999"


# ----- build_fusion_settings (完成版テンプレ) -----


@dataclass
class _StubContext:
    frame_rate: float = 24.0
    start_frame: int = 0
    canvas_size: tuple[int, int] = (1920, 1080)


def test_build_fusion_settings_resolves_all_placeholders():
    """完成版 arrow.setting のすべてのプレースホルダが解決されること。

    PNG が無い環境では PNG 寸法はデフォルトにフォールバックする。
    どちらの場合でも未解決プレースホルダ ``{{...}}`` が残ってはならない。
    """
    eff = ArrowEffect(ArrowParams())
    out = eff.build_fusion_settings(_StubContext())  # type: ignore[arg-type]
    # プレースホルダ ``{{...}}`` がすべて埋まっていること
    assert "{{" not in out
    # 値の埋め込み確認 (FORMAT_TYPE = "Picture" のように、Lua キー名としては残る)
    assert 'MEDIA_FORMAT_TYPE = "Picture"' in out


def test_build_fusion_settings_fade_keyframes_strictly_increasing():
    """Merge1Blend のキーフレームは frame 番号が単調増加。"""
    params = ArrowParams(duration_sec=3.0, fade_in_sec=0.3, fade_out_sec=0.3)
    eff = ArrowEffect(params)
    out = eff.build_fusion_settings(_StubContext())  # type: ignore[arg-type]
    import re
    spline = _extract_block(out, "Merge1Blend = BezierSpline")
    frames = [int(m.group(1)) for m in re.finditer(r"\[(\d+)\]", spline)]
    assert frames == sorted(set(frames))
    assert len(frames) == 4  # START / FADE_IN_END / FADE_OUT_START / END


def _extract_block(text: str, anchor: str) -> str:
    """``anchor`` から始まるブロックを ``{...}`` の括弧バランスで切り出す。"""
    start = text.index(anchor)
    open_idx = text.index("{", start)
    depth = 0
    for i in range(open_idx, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return text[start:]


def test_build_fusion_settings_pos_y_inverted():
    """params.pos_y (上原点) → Fusion Y (下原点) に反転される。"""
    params = ArrowParams(pos_x=0.8, pos_y=0.2)
    eff = ArrowEffect(params)
    out = eff.build_fusion_settings(_StubContext())  # type: ignore[arg-type]
    transform = out.split("Transform1 = Transform")[1].split("Merge1")[0]
    assert "Center = Input { Value = { 0.800000, 0.800000 }" in transform


def test_arrow_clip_discriminator_uses_direction_abbr():
    eff = ArrowEffect(ArrowParams(direction="bottom_left"))
    assert eff._clip_discriminator(context=None) == "bl"  # type: ignore[arg-type]
