"""``conftest.FakeResolveAPI`` の挙動を通じてラッパーが期待する契約をテストする。

実物の ``ResolveAPI`` は Resolve 実機が必要なため、ここでは
ラッパー越しに呼ばれる API 名・戻り値の形が想定どおりかを Fake で確認する。
"""
from __future__ import annotations

from cue import config


def test_ensure_preview_track_creates_named_track(fake_api, fake_timeline):
    track = fake_api.ensure_preview_track(fake_timeline)
    assert track >= config.PREVIEW_TRACK_INDEX
    assert fake_api.get_track_name(fake_timeline, track) == config.PREVIEW_TRACK_NAME


def test_ensure_preview_track_is_idempotent(fake_api, fake_timeline):
    first = fake_api.ensure_preview_track(fake_timeline)
    second = fake_api.ensure_preview_track(fake_timeline)
    assert first == second


def test_ensure_track_grows_until_required(fake_api, fake_timeline):
    fake_api.ensure_track(fake_timeline, 7)
    assert fake_api.get_video_track_count(fake_timeline) >= 7


def test_remove_all_clips_in_track_returns_count(fake_api, fake_timeline):
    track = fake_api.ensure_preview_track(fake_timeline)
    fake_api.place_fusion_clip(
        timeline=fake_timeline,
        track_index=track,
        start_frame=100,
        duration_frames=72,
        clip_name="cue_arrow_Red_f100",
        fusion_settings="dummy",
    )
    fake_api.place_fusion_clip(
        timeline=fake_timeline,
        track_index=track,
        start_frame=300,
        duration_frames=72,
        clip_name="cue_arrow_Red_f300",
        fusion_settings="dummy",
    )
    removed = fake_api.remove_all_clips_in_track(fake_timeline, track)
    assert removed == 2
    assert fake_api.remove_all_clips_in_track(fake_timeline, track) == 0
