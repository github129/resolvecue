"""``cue.effects.arrow.ArrowEffect`` のロジックテスト。

Resolve 実機を使わず、``conftest`` の ``FakeResolveAPI`` 越しに動作確認する。
アセット PNG が無い環境では ``apply()`` の前段バリデーションでエラーになることを許容する。
"""
from __future__ import annotations

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


def test_arrow_clip_discriminator_uses_direction_abbr():
    eff = ArrowEffect(ArrowParams(direction="bottom_left"))
    assert eff._clip_discriminator(context=None) == "bl"  # type: ignore[arg-type]
