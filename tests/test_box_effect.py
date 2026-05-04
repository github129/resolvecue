"""``cue.effects.box.BoxEffect`` のテスト。"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from cue import config
from cue.effects.box import (
    BackgroundConfig,
    BorderConfig,
    BoxEffect,
    BoxParams,
    TextConfig,
)


# ----- プリセット適用 -----


def test_all_box_presets_apply_without_error():
    for preset_key in config.BOX_PRESETS:
        params = BoxParams(preset=preset_key)
        BoxEffect.apply_preset(params, preset_key)


def test_signboard_white_preset_sets_solid_white_bg():
    params = BoxParams(preset="signboard_white")
    BoxEffect.apply_preset(params, "signboard_white")
    assert params.background.fill_type == "solid"
    assert params.background.color == "#FFFFFF"
    assert params.background.opacity_pct == 100.0
    assert params.border.enabled is False
    assert params.text.color == "#000000"
    assert params.text.weight == "Bold"
    assert params.text.size_px == 28


def test_signboard_black_preset_keeps_thin_white_border():
    params = BoxParams(preset="signboard_black")
    BoxEffect.apply_preset(params, "signboard_black")
    assert params.background.fill_type == "solid"
    assert params.background.color == "#000000"
    assert params.border.enabled is True
    assert params.border.color == "#FFFFFF"
    assert params.border.width_px == 2


def test_chapter_title_preset_full_width():
    params = BoxParams(preset="chapter_title")
    BoxEffect.apply_preset(params, "chapter_title")
    assert params.width == 1.0
    assert params.height == 0.25
    assert params.background.fill_type == "solid"
    assert params.background.opacity_pct == 90.0
    assert params.border.enabled is False
    assert params.text.size_px == 48


def test_translucent_panel_preset_left_aligned():
    params = BoxParams(preset="translucent_panel")
    BoxEffect.apply_preset(params, "translucent_panel")
    assert params.background.fill_type == "solid"
    assert params.background.opacity_pct == 70.0
    assert params.text.align_h == "left"
    assert params.text.weight == "Regular"
    assert params.border.enabled is False


def test_disabled_fields_for_chapter_title():
    fields = BoxEffect.disabled_fields_for("chapter_title")
    assert "border.color" in fields
    assert "border.animation" in fields
    assert "border.draw_duration_sec" in fields


def test_apply_preset_dot_notation_writes_to_nested_field():
    params = BoxParams()
    BoxEffect.apply_preset(params, "signboard_white")
    # ドット記法で background.* に書き込めていること
    assert params.background.fill_type == "solid"
    assert params.background.color == "#FFFFFF"


# ----- クリップ名 discriminator -----


def test_clip_discriminator_includes_preset_and_animation():
    params = BoxParams(preset="plain")
    params.border.animation = "cw"
    eff = BoxEffect(params)
    slots = eff._clip_discriminator(context=None)  # type: ignore[arg-type]
    assert slots == ["plain", "cw"]


def test_clip_discriminator_omits_animation_when_no_border():
    params = BoxParams(preset="signboard_white")
    params.border.enabled = False
    eff = BoxEffect(params)
    slots = eff._clip_discriminator(context=None)  # type: ignore[arg-type]
    assert slots == ["signboard_white"]


def test_clip_name_full_format():
    name = config.make_clip_name("box", 1234, ["plain", "cw"])
    assert name == "cue_box_1234_plain_cw"


def test_clip_name_warns_over_three_slots(caplog):
    import logging
    caplog.set_level(logging.WARNING)
    config.make_clip_name("test", 1, ["a", "b", "c", "d"])
    assert any("recommended max" in rec.message for rec in caplog.records)


# ----- バリデーション -----


def test_validate_rejects_negative_width():
    params = BoxParams(width=-0.1)
    eff = BoxEffect(params)
    errors = eff.validate()
    assert any("width" in e for e in errors)


def test_validate_rejects_invalid_border_color():
    params = BoxParams()
    params.border.color = "not-a-color"
    eff = BoxEffect(params)
    errors = eff.validate()
    assert any("枠線" in e or "color" in e.lower() for e in errors)


def test_validate_rejects_unknown_preset():
    params = BoxParams(preset="not_a_preset")
    eff = BoxEffect(params)
    errors = eff.validate()
    assert any("プリセット" in e for e in errors)


def test_validate_rejects_invalid_text_weight():
    params = BoxParams()
    params.text.content = "hello"
    params.text.weight = "Heavy"  # type: ignore[assignment]
    eff = BoxEffect(params)
    errors = eff.validate()
    assert any("ウェイト" in e for e in errors)


def test_validate_rejects_invalid_alignment():
    params = BoxParams()
    params.text.content = "hello"
    params.text.align_v = "middle"  # type: ignore[assignment]
    eff = BoxEffect(params)
    errors = eff.validate()
    assert any("揃え" in e for e in errors)


def test_validate_skips_text_checks_when_content_is_empty():
    params = BoxParams()
    params.text.content = ""
    # 空でも text.color が不正なら検証されない (フィールドを参照しない)
    params.text.color = "garbage"
    eff = BoxEffect(params)
    errors = eff.validate()
    assert not any("テキスト色" in e for e in errors)


# ----- build_fusion_settings の出力差分 -----


@dataclass
class _StubContext:
    frame_rate: float = 24.0
    start_frame: int = 0


def _ctx() -> _StubContext:
    return _StubContext()


def test_build_fusion_settings_no_text_no_background():
    params = BoxParams()
    params.background.fill_type = "transparent"
    params.text.content = ""
    eff = BoxEffect(params)
    out = eff.build_fusion_settings(_ctx())  # type: ignore[arg-type]
    assert "Border1" in out  # border は有効なので含まれる
    assert "Background1" not in out
    assert "TextNode1" not in out


def test_build_fusion_settings_text_only_no_background():
    params = BoxParams()
    params.background.fill_type = "transparent"
    params.text.content = "Hello"
    eff = BoxEffect(params)
    out = eff.build_fusion_settings(_ctx())  # type: ignore[arg-type]
    assert "TextNode1" in out
    assert "Background1" not in out
    assert "Hello" in out


def test_build_fusion_settings_with_solid_background():
    params = BoxParams()
    params.background.fill_type = "solid"
    params.background.color = "#FF0000"
    params.background.opacity_pct = 50.0
    params.text.content = ""
    eff = BoxEffect(params)
    out = eff.build_fusion_settings(_ctx())  # type: ignore[arg-type]
    assert "Background1" in out
    # opacity 50% → alpha 0.5
    assert "0.5000" in out


def test_build_fusion_settings_full_combo():
    params = BoxParams()
    params.background.fill_type = "solid"
    params.text.content = "テスト"
    params.border.enabled = True
    eff = BoxEffect(params)
    out = eff.build_fusion_settings(_ctx())  # type: ignore[arg-type]
    assert "Background1" in out
    assert "Border1" in out
    assert "TextNode1" in out
    assert "テスト" in out


def test_build_fusion_settings_border_disabled():
    params = BoxParams()
    params.border.enabled = False
    params.background.fill_type = "transparent"
    params.text.content = ""
    eff = BoxEffect(params)
    out = eff.build_fusion_settings(_ctx())  # type: ignore[arg-type]
    assert "Border1" not in out


def test_build_fusion_settings_escapes_special_chars():
    params = BoxParams()
    params.text.content = 'line1\nline2 "quoted"'
    eff = BoxEffect(params)
    out = eff.build_fusion_settings(_ctx())  # type: ignore[arg-type]
    assert "line1\\nline2" in out
    assert '\\"quoted\\"' in out
