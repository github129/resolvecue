"""タイムラインのマーカーをトリガーとするクラス。"""
from __future__ import annotations

from typing import Any

from cue.core.markers import Marker, fetch_markers
from cue.triggers.base import Trigger, TriggerPoint


class MarkerTrigger(Trigger):
    """選択した色のマーカー位置をすべて発火点として返す。"""

    name = "marker"

    def __init__(
        self,
        api: Any,
        timeline: Any,
        colors: list[str] | None = None,
    ) -> None:
        """
        Parameters
        ----------
        api : ResolveAPI
        timeline : 対象タイムライン
        colors : フィルタする色のリスト。None または空なら全色対象。
        """
        self.api = api
        self.timeline = timeline
        self.colors = list(colors) if colors else []

    def collect(self) -> list[TriggerPoint]:
        markers: list[Marker] = fetch_markers(self.api, self.timeline)
        if self.colors:
            markers = [m for m in markers if m.color in self.colors]
        return [
            TriggerPoint(
                start_frame=m.frame,
                end_frame=m.frame + m.duration if m.duration > 0 else None,
                color=m.color,
                label=m.name,
                extra={"note": m.note, "custom_data": m.custom_data},
            )
            for m in markers
        ]
