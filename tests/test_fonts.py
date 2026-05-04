"""``cue.utils.fonts`` のテスト。

実機のフォント有無に依存しないよう、内部関数をモック差し替えしてテストする。
"""
from __future__ import annotations

import pytest

from cue import config
from cue.utils import fonts as font_utils


def test_categorize_separates_recommended_and_others():
    all_fonts = ["Arial", "Noto Sans JP", "Comic Sans MS", "Yu Gothic UI", "Verdana"]
    rec, others = font_utils.categorize_fonts(all_fonts)
    # 推奨はインストール済みのものだけ、推奨リストの順序を保つ
    assert rec == ["Noto Sans JP", "Yu Gothic UI"]
    # その他はアルファベット順
    assert others == ["Arial", "Comic Sans MS", "Verdana"]


def test_categorize_empty_recommended_returns_all_in_others():
    all_fonts = ["Arial", "Verdana"]
    rec, others = font_utils.categorize_fonts(all_fonts, recommended=())
    assert rec == []
    assert others == ["Arial", "Verdana"]


def test_resolve_default_font_picks_first_available():
    # Yu Gothic UI が無く Meiryo がある → Meiryo (推奨リスト順で先のものから)
    all_fonts = ["Arial", "Meiryo"]
    assert font_utils.resolve_default_font(all_fonts) == "Meiryo"


def test_resolve_default_font_falls_back_when_no_recommended_present():
    all_fonts = ["Arial"]
    # 一つも推奨が無ければ RECOMMENDED_FONTS[0] を返す (Resolve 側で最終フォールバック)
    assert font_utils.resolve_default_font(all_fonts) == config.RECOMMENDED_FONTS[0]


def test_list_system_fonts_falls_back_when_all_fail(monkeypatch):
    """全てのバックエンドが失敗したら RECOMMENDED_FONTS が返る。"""
    monkeypatch.setattr(font_utils, "_try_tkinter_fonts", lambda: [])
    monkeypatch.setattr(font_utils, "_try_matplotlib_fonts", lambda: [])
    result = font_utils.list_system_fonts()
    assert result == list(config.RECOMMENDED_FONTS)


def test_list_system_fonts_uses_tkinter_when_available(monkeypatch):
    monkeypatch.setattr(
        font_utils, "_try_tkinter_fonts", lambda: ["Arial", "Verdana", ""]
    )
    monkeypatch.setattr(font_utils, "_try_matplotlib_fonts", lambda: ["should not call"])
    result = font_utils.list_system_fonts()
    # 空文字は dedupe で除去される
    assert result == ["Arial", "Verdana"]


def test_list_system_fonts_falls_through_to_matplotlib(monkeypatch):
    monkeypatch.setattr(font_utils, "_try_tkinter_fonts", lambda: [])
    monkeypatch.setattr(
        font_utils, "_try_matplotlib_fonts",
        lambda: ["Arial", "Arial", "Verdana"],
    )
    result = font_utils.list_system_fonts()
    assert result == ["Arial", "Verdana"]  # 重複排除
