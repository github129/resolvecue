"""``cue.triggers.marker_trigger.MarkerTrigger`` のテスト。"""
from __future__ import annotations

from cue.triggers.marker_trigger import MarkerTrigger


def test_collect_returns_all_when_no_color_filter(fake_api, fake_timeline):
    trig = MarkerTrigger(fake_api, fake_timeline)
    points = trig.collect()
    assert len(points) == len(fake_timeline.GetMarkers())


def test_collect_filters_by_color(fake_api, fake_timeline):
    trig = MarkerTrigger(fake_api, fake_timeline, colors=["Red"])
    points = trig.collect()
    assert all(p.color == "Red" for p in points)
    assert len(points) >= 1


def test_collect_returns_sorted_points(fake_api, fake_timeline):
    trig = MarkerTrigger(fake_api, fake_timeline)
    points = trig.collect()
    frames = [p.start_frame for p in points]
    assert frames == sorted(frames)
