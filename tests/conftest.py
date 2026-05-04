"""共通フィクスチャ。

Resolve 実機が無くてもロジックをテストできるよう、
``ResolveAPI`` の振る舞いを再現する ``FakeResolveAPI`` を提供する。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def markers_sample() -> dict[str, dict[str, Any]]:
    data = json.loads((FIXTURES_DIR / "markers_sample.json").read_text(encoding="utf-8"))
    return {int(k): v for k, v in data.items() if k != "_comment"}


@pytest.fixture
def timeline_info_sample() -> dict[str, Any]:
    return json.loads(
        (FIXTURES_DIR / "timeline_info_sample.json").read_text(encoding="utf-8")
    )


class FakeTimeline:
    """テスト用タイムライン。

    Resolve API のうち、本ツールが触る部分だけ最小限に再現する。
    """

    def __init__(self, info: dict[str, Any]) -> None:
        self._info = info
        self._track_count = int(info["video_track_count"])
        self._track_names: dict[int, str] = {
            int(k): v for k, v in info["track_names"].items()
        }
        self._items_by_track: dict[int, list[FakeTimelineItem]] = {
            i: [] for i in range(1, self._track_count + 1)
        }
        self._markers: dict[int, dict[str, Any]] = {}

    def set_markers(self, markers: dict[int, dict[str, Any]]) -> None:
        self._markers = dict(markers)

    # 以下、Resolve API と同じ名前にしている (ラッパー越しに呼ばれるため)
    def GetSetting(self, key: str) -> str:  # noqa: N802
        if key == "timelineFrameRate":
            return self._info["frame_rate"]
        return ""

    def GetTrackCount(self, track_type: str) -> int:  # noqa: N802
        return self._track_count if track_type == "video" else 0

    def GetTrackName(self, track_type: str, idx: int) -> str:  # noqa: N802
        return self._track_names.get(idx, "")

    def SetTrackName(self, track_type: str, idx: int, name: str) -> bool:  # noqa: N802
        self._track_names[idx] = name
        return True

    def AddTrack(self, track_type: str) -> bool:  # noqa: N802
        self._track_count += 1
        self._track_names[self._track_count] = f"Video {self._track_count}"
        self._items_by_track[self._track_count] = []
        return True

    def GetMarkers(self) -> dict[int, dict[str, Any]]:  # noqa: N802
        return dict(self._markers)

    def GetItemListInTrack(self, track_type: str, idx: int):  # noqa: N802
        return list(self._items_by_track.get(idx, []))

    def DeleteClips(self, items, _flag) -> bool:  # noqa: N802
        for item in items:
            for track_items in self._items_by_track.values():
                if item in track_items:
                    track_items.remove(item)
        return True

    def GetStartFrame(self) -> int:  # noqa: N802
        return int(self._info.get("start_frame", 0))


class FakeTimelineItem:
    def __init__(self, name: str, start: int, end: int) -> None:
        self._name = name
        self.start = start
        self.end = end

    def GetName(self) -> str:  # noqa: N802
        return self._name

    def SetName(self, name: str) -> bool:  # noqa: N802
        self._name = name
        return True

    def GetUniqueId(self) -> str:  # noqa: N802
        return f"id-{self._name}"


class FakeMediaPool:
    def __init__(self, timeline: FakeTimeline) -> None:
        self._timeline = timeline

    def AddTimelineFusionConnection(self):  # noqa: N802
        return object()

    def AppendToTimeline(self, clip_infos):  # noqa: N802
        results = []
        for info in clip_infos:
            track = info["trackIndex"]
            item = FakeTimelineItem(
                name=f"clip_{info['startFrame']}",
                start=info["startFrame"],
                end=info["endFrame"],
            )
            self._timeline._items_by_track.setdefault(track, []).append(item)
            results.append(item)
        return results


class FakeResolveAPI:
    """``cue.core.resolve_api.ResolveAPI`` 互換のテスト用ダブル。"""

    def __init__(self, timeline: FakeTimeline) -> None:
        self._timeline = timeline

    # ----- 基本 -----
    def get_current_timeline(self):
        return self._timeline

    def get_frame_rate(self, timeline) -> float:
        return float(timeline.GetSetting("timelineFrameRate"))

    def get_video_track_count(self, timeline) -> int:
        return timeline.GetTrackCount("video")

    def get_track_name(self, timeline, idx: int) -> str:
        return timeline.GetTrackName("video", idx)

    def set_track_name(self, timeline, idx: int, name: str) -> bool:
        return timeline.SetTrackName("video", idx, name)

    def add_video_track(self, timeline) -> int:
        timeline.AddTrack("video")
        return timeline.GetTrackCount("video")

    def ensure_track(self, timeline, idx: int) -> int:
        while timeline.GetTrackCount("video") < idx:
            self.add_video_track(timeline)
        return idx

    def ensure_preview_track(self, timeline) -> int:
        from cue import config
        count = timeline.GetTrackCount("video")
        for i in range(1, count + 1):
            if timeline.GetTrackName("video", i) == config.PREVIEW_TRACK_NAME:
                return i
        target = max(config.PREVIEW_TRACK_INDEX, count + 1)
        self.ensure_track(timeline, target)
        timeline.SetTrackName("video", target, config.PREVIEW_TRACK_NAME)
        return target

    def get_markers(self, timeline) -> dict[int, dict[str, Any]]:
        return timeline.GetMarkers()

    def find_clip_by_name(self, timeline, clip_name: str, track_index: int):
        for item in timeline.GetItemListInTrack("video", track_index):
            if item.GetName() == clip_name:
                return item
        return None

    def remove_clip(self, timeline, clip) -> bool:
        return timeline.DeleteClips([clip], False)

    def remove_all_clips_in_track(self, timeline, track_index: int) -> int:
        items = timeline.GetItemListInTrack("video", track_index)
        if not items:
            return 0
        timeline.DeleteClips(items, False)
        return len(items)

    def place_fusion_clip(
        self,
        timeline,
        track_index: int,
        start_frame: int,
        duration_frames: int,
        clip_name: str,
        fusion_settings: str,
    ) -> str:
        media_pool = FakeMediaPool(timeline)
        clip_info = {
            "mediaPoolItem": media_pool.AddTimelineFusionConnection(),
            "startFrame": start_frame,
            "endFrame": start_frame + max(1, duration_frames),
            "trackIndex": track_index,
            "mediaType": 1,
        }
        items = media_pool.AppendToTimeline([clip_info])
        items[0].SetName(clip_name)
        return items[0].GetUniqueId()


@pytest.fixture
def fake_timeline(timeline_info_sample, markers_sample) -> FakeTimeline:
    tl = FakeTimeline(timeline_info_sample)
    tl.set_markers(markers_sample)
    return tl


@pytest.fixture
def fake_api(fake_timeline) -> FakeResolveAPI:
    return FakeResolveAPI(fake_timeline)
