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
from cue.utils import template as template_utils


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
    canvas_size: tuple[int, int] = (1920, 1080)


def _ctx(**kw) -> _StubContext:
    return _StubContext(**kw)


# ----- 完成版テンプレ向け build_fusion_settings 検証 -----


def test_build_resolves_all_placeholders_for_default_params():
    """デフォルト BoxParams ですべてのプレースホルダが解決されること。"""
    eff = BoxEffect(BoxParams())
    out = eff.build_fusion_settings(_ctx())  # type: ignore[arg-type]
    # render_template は strict なので、未解決があれば例外で落ちる。
    # 出力に {{ が残っていなければ全置換できた証拠。
    assert "{{" not in out
    # 主要ノード名はテンプレ由来なのでそのまま残る
    for tool in ("Background1", "Rectangle1", "Background2", "Rectangle2",
                 "Merge4Blend", "Text1", "Merge5Blend"):
        assert tool in out


def test_build_with_solid_background_injects_alpha():
    params = BoxParams()
    params.background.fill_type = "solid"
    params.background.color = "#FF0000"
    params.background.opacity_pct = 50.0
    eff = BoxEffect(params)
    out = eff.build_fusion_settings(_ctx())  # type: ignore[arg-type]
    # Background1 の TopLeftAlpha = 0.5 が現れる
    assert "TopLeftAlpha = Input { Value = 0.500000, }," in out
    # Red = 1.0 (FF / 255)
    assert "TopLeftRed = Input { Value = 1.000000, }," in out


def test_build_with_transparent_background_zeroes_alpha():
    params = BoxParams()
    params.background.fill_type = "transparent"
    eff = BoxEffect(params)
    out = eff.build_fusion_settings(_ctx())  # type: ignore[arg-type]
    # Background1 (背景) は alpha=0 になっているはず
    # Background1 ブロック内の最初の TopLeftAlpha を取り出す
    bg1_section = out.split("Background1 = Background")[1].split("Background2")[0]
    assert "TopLeftAlpha = Input { Value = 0.000000, }," in bg1_section


def test_build_with_disabled_border_zeroes_border_alpha():
    params = BoxParams()
    params.border.enabled = False
    eff = BoxEffect(params)
    out = eff.build_fusion_settings(_ctx())  # type: ignore[arg-type]
    # Background2-5 (枠線) は alpha=0
    bg2_section = out.split("Background2 = Background")[1].split("Rectangle2 ")[0]
    assert "TopLeftAlpha = Input { Value = 0.000000, }," in bg2_section


def test_build_with_text_content_includes_styled_text():
    params = BoxParams()
    params.text.content = "テスト"
    params.text.weight = "Bold"
    eff = BoxEffect(params)
    out = eff.build_fusion_settings(_ctx())  # type: ignore[arg-type]
    assert 'StyledText = Input { Value = "テスト", }' in out
    assert 'Style = Input { Value = "Bold", }' in out


def test_build_escapes_special_characters_in_text():
    params = BoxParams()
    params.text.content = 'line1\nline2 "q"'
    eff = BoxEffect(params)
    out = eff.build_fusion_settings(_ctx())  # type: ignore[arg-type]
    assert 'StyledText = Input { Value = "line1\\nline2 \\"q\\"", }' in out


def test_build_text_justification_uses_integers():
    params = BoxParams()
    params.text.content = "x"
    params.text.align_h = "left"   # → 0
    params.text.align_v = "bottom"  # → 2
    eff = BoxEffect(params)
    out = eff.build_fusion_settings(_ctx())  # type: ignore[arg-type]
    assert "HorizontalJustificationNew = Input { Value = 0, }" in out
    assert "VerticalJustificationNew = Input { Value = 2, }" in out


def test_build_pos_y_inverted_for_fusion_origin():
    """params.pos_y は上から下、Fusion は下から上。1.0 - params.pos_y で渡される。"""
    params = BoxParams(pos_x=0.5, pos_y=0.2)  # 画面上寄り
    eff = BoxEffect(params)
    out = eff.build_fusion_settings(_ctx())  # type: ignore[arg-type]
    # Rectangle1 の Center に Fusion 座標 (0.5, 0.8) が入る
    rect1 = out.split("Rectangle1 = RectangleMask")[1].split("Background2")[0]
    assert "Center = Input { Value = { 0.500000, 0.800000 }" in rect1


def test_build_border_thickness_normalized_to_screen_ratio():
    """border.width_px (px) は canvas_height で正規化される (Q3)。"""
    params = BoxParams()
    params.border.width_px = 4
    eff = BoxEffect(params)
    out = eff.build_fusion_settings(
        _ctx(canvas_size=(1920, 1080))  # type: ignore[arg-type]
    )
    expected = 4 / 1080  # ≈ 0.003704
    assert f"Height = Input {{ Value = {expected:.6f}, }}" in out


def test_build_unresolved_placeholder_raises():
    """テンプレに mapping で埋められないプレースホルダがあれば即座にエラー。"""
    eff = BoxEffect(BoxParams())
    # build_fusion_settings は load_template して mapping を作るので、
    # 完成版テンプレが期待外の placeholder を持つ場合はここで気付ける。
    eff.build_fusion_settings(_ctx())  # type: ignore[arg-type] - エラーが出ないことだけ確認


# ----- 描画アニメ -----


def _animation_for(animation: str, fps: float = 24.0) -> dict:
    """``_compute_border_animation`` を直接呼んでフレーム計算を検証する。"""
    params = BoxParams()
    params.border.animation = animation  # type: ignore[assignment]
    eff = BoxEffect(params)
    return eff._compute_border_animation(
        params, pos_x=0.5, pos_y=0.5, width=0.4, height=0.2, fps=fps,
    )


def test_animation_cw_orders_top_right_bottom_left():
    a = _animation_for("cw")
    assert a["top_start"] < a["right_start"] < a["bottom_start"] < a["left_start"]
    assert a["top_end"] == a["right_start"]
    assert a["right_end"] == a["bottom_start"]
    assert a["bottom_end"] == a["left_start"]


def test_animation_ccw_orders_top_left_bottom_right():
    a = _animation_for("ccw")
    assert a["top_start"] < a["left_start"] < a["bottom_start"] < a["right_start"]


def test_animation_none_all_sides_simultaneous():
    a = _animation_for("none")
    assert a["top_start"] == a["right_start"] == a["bottom_start"] == a["left_start"] == 0
    assert a["top_end"] == a["right_end"] == a["bottom_end"] == a["left_end"]


def test_animation_cw_top_starts_at_left_edge():
    """cw: 上辺は左から右へ。Fusion 座標で左端 = pos_x - width/2。"""
    a = _animation_for("cw")
    assert a["top_x_start"] == pytest.approx(0.5 - 0.4 / 2)


def test_animation_cw_right_starts_at_top_edge_in_fusion_coords():
    """cw: 右辺は上から下へ。Fusion Y は上向きなので上端 = pos_y + height/2。"""
    a = _animation_for("cw")
    assert a["right_y_start"] == pytest.approx(0.5 + 0.2 / 2)


def test_animation_ccw_top_starts_at_right_edge():
    a = _animation_for("ccw")
    assert a["top_x_start"] == pytest.approx(0.5 + 0.4 / 2)


def test_build_keyframe_frames_are_strictly_increasing():
    """Merge4Blend / Merge5Blend のキーフレーム frame は単調増加でなければならない。"""
    params = BoxParams(duration_sec=3.0, fade_out_sec=0.3)
    params.text.content = "x"
    params.text.fade_in_sec = 0.3
    eff = BoxEffect(params)
    out = eff.build_fusion_settings(_ctx())  # type: ignore[arg-type]
    # Merge5Blend のキーフレームを取り出してフレーム番号を確認
    merge5 = _extract_block(out, "Merge5Blend = BezierSpline")
    import re
    frames = [int(m.group(1)) for m in re.finditer(r"\[(\d+)\]", merge5)]
    assert frames == sorted(set(frames))
    assert len(frames) == 4  # BORDER_COMPLETE / TEXT_FADE_IN_END / FADE_OUT_START / END


def _extract_block(text: str, anchor: str) -> str:
    """``anchor`` から始まるブロックを括弧バランスで切り出す。"""
    start = text.index(anchor)
    # 最初の '{' を見つける
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


# ----- プリセットとの統合 -----


def test_chapter_title_preset_renders_full_width_box():
    params = BoxParams(preset="chapter_title")
    BoxEffect.apply_preset(params, "chapter_title")
    eff = BoxEffect(params)
    out = eff.build_fusion_settings(_ctx())  # type: ignore[arg-type]
    rect1 = out.split("Rectangle1 = RectangleMask")[1].split("Background2")[0]
    assert "Width = Input { Value = 1.000000" in rect1
    assert "Height = Input { Value = 0.250000" in rect1


def test_signboard_white_preset_yields_solid_white_alpha_one():
    params = BoxParams(preset="signboard_white")
    BoxEffect.apply_preset(params, "signboard_white")
    eff = BoxEffect(params)
    out = eff.build_fusion_settings(_ctx())  # type: ignore[arg-type]
    bg1 = out.split("Background1 = Background")[1].split("Background2")[0]
    assert "TopLeftRed = Input { Value = 1.000000" in bg1
    assert "TopLeftGreen = Input { Value = 1.000000" in bg1
    assert "TopLeftBlue = Input { Value = 1.000000" in bg1
    assert "TopLeftAlpha = Input { Value = 1.000000" in bg1
