"""タイムラインのマーカーを取得・整形する。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Marker:
    """1つのマーカーを表す DTO。

    Resolve API の戻り値 (``timeline.GetMarkers()``) を扱いやすい形に整形する。
    """

    frame: int
    color: str = ""
    name: str = ""
    note: str = ""
    duration: int = 0
    custom_data: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def fetch_markers(api: Any, timeline: Any) -> list[Marker]:
    """タイムライン上の全マーカーを ``Marker`` のリストで返す。

    Resolve の ``GetMarkers()`` は ``{frame: {color, name, note, duration, customData}}``
    の辞書を返すので、それを正規化する。
    """
    raw = api.get_markers(timeline) or {}
    markers: list[Marker] = []
    for frame, info in raw.items():
        markers.append(
            Marker(
                frame=int(frame),
                color=str(info.get("color", "")),
                name=str(info.get("name", "")),
                note=str(info.get("note", "")),
                duration=int(info.get("duration", 0) or 0),
                custom_data=str(info.get("customData", "")),
            )
        )
    markers.sort(key=lambda m: m.frame)
    return markers


def filter_by_color(markers: list[Marker], colors: list[str] | None) -> list[Marker]:
    """色でフィルタする。``colors`` が None または空なら全件返す。"""
    if not colors:
        return list(markers)
    color_set = set(colors)
    return [m for m in markers if m.color in color_set]


def collect_used_colors(markers: list[Marker]) -> list[str]:
    """マーカー一覧から実際に使われている色を出現順 (重複排除済み) で返す。"""
    seen: set[str] = set()
    result: list[str] = []
    for m in markers:
        if m.color and m.color not in seen:
            seen.add(m.color)
            result.append(m.color)
    return result
