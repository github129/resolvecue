"""タイムライン操作のヘルパー。

``ResolveAPI`` のラッパーが提供する低レベル操作を組み合わせて、
よく使う高レベル操作を提供する。
"""
from __future__ import annotations

from typing import Any

from cue import config


def clear_preview_track(api: Any, timeline: Any) -> int:
    """プレビュー専用トラックを確保し、その上のクリップを全削除する。

    Returns
    -------
    削除したクリップ数。
    """
    track = api.ensure_preview_track(timeline)
    return api.remove_all_clips_in_track(timeline, track)


def get_preview_track_index(api: Any, timeline: Any) -> int:
    """プレビュー専用トラックを (なければ作成して) インデックスを返す。"""
    return api.ensure_preview_track(timeline)


def ensure_target_track(api: Any, timeline: Any, track_index: int) -> int:
    """配置先のトラックが無ければ作成する。"""
    return api.ensure_track(timeline, track_index)


def seconds_to_frames(seconds: float, frame_rate: float) -> int:
    """秒をフレーム数に変換 (四捨五入)。"""
    return int(round(seconds * frame_rate))


def get_default_target_track() -> int:
    return config.DEFAULT_TARGET_TRACK
