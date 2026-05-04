"""``cue.core.markers`` の単体テスト。"""
from __future__ import annotations

from cue.core.markers import collect_used_colors, fetch_markers, filter_by_color


def test_fetch_markers_normalizes_and_sorts(fake_api, fake_timeline):
    markers = fetch_markers(fake_api, fake_timeline)
    assert [m.frame for m in markers] == sorted(m.frame for m in markers)
    assert all(m.color for m in markers)


def test_filter_by_color_returns_matching_only(fake_api, fake_timeline):
    markers = fetch_markers(fake_api, fake_timeline)
    red_only = filter_by_color(markers, ["Red"])
    assert all(m.color == "Red" for m in red_only)
    assert len(red_only) >= 1


def test_filter_by_color_empty_means_all(fake_api, fake_timeline):
    markers = fetch_markers(fake_api, fake_timeline)
    assert filter_by_color(markers, None) == markers
    assert filter_by_color(markers, []) == markers


def test_collect_used_colors_preserves_order(fake_api, fake_timeline):
    markers = fetch_markers(fake_api, fake_timeline)
    colors = collect_used_colors(markers)
    assert len(set(colors)) == len(colors)  # 重複なし
    assert all(c for c in colors)
