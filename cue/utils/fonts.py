"""システムフォント列挙と推奨フォント分離。

3段階フォールバック:

1. ``tkinter.font.families()``  (標準ライブラリ、GUI不要)
2. ``matplotlib.font_manager`` のキャッシュ
3. ``config.RECOMMENDED_FONTS`` 固定リスト

UI 側はこのモジュールが返す ``(recommended_present, others)`` を使い、
「よく使う」セクションを上に固定表示する。
"""
from __future__ import annotations

import logging

from cue import config

_log = logging.getLogger(__name__)


def list_system_fonts() -> list[str]:
    """システムにインストールされているフォント名のリスト。

    取得に失敗した場合でも空リストを返さず、最終的には ``RECOMMENDED_FONTS``
    の固定リストを返す。
    """
    fonts = _try_tkinter_fonts()
    if fonts:
        return _dedupe(fonts)

    fonts = _try_matplotlib_fonts()
    if fonts:
        return _dedupe(fonts)

    _log.info("system font enumeration failed; falling back to RECOMMENDED_FONTS")
    return list(config.RECOMMENDED_FONTS)


def categorize_fonts(
    all_fonts: list[str],
    recommended: tuple[str, ...] | None = None,
) -> tuple[list[str], list[str]]:
    """``(recommended_present, others)`` に分割して返す。

    - ``recommended_present``: ``recommended`` のうち実際にインストール済みのもの。
      推奨リストでの記載順を保つ。
    - ``others``: それ以外の全フォント。アルファベット昇順。
    """
    rec = recommended if recommended is not None else config.RECOMMENDED_FONTS
    installed = set(all_fonts)
    rec_present = [f for f in rec if f in installed]
    rec_set = set(rec_present)
    others = sorted(f for f in all_fonts if f not in rec_set)
    return rec_present, others


def resolve_default_font(all_fonts: list[str] | None = None) -> str:
    """既定フォント (推奨リスト先頭からインストール済みを探す)。

    一つもインストールされていなければ ``RECOMMENDED_FONTS[0]`` を返す
    (この場合は Resolve 側で最終フォールバックされる想定)。
    """
    fonts = all_fonts if all_fonts is not None else list_system_fonts()
    installed = set(fonts)
    for f in config.RECOMMENDED_FONTS:
        if f in installed:
            return f
    return config.RECOMMENDED_FONTS[0]


# ----- internal -----


def _try_tkinter_fonts() -> list[str]:
    try:
        import tkinter
        from tkinter import font as tkfont
    except ImportError:
        return []
    try:
        root = tkinter.Tk()
        try:
            families = list(tkfont.families(root))
        finally:
            root.destroy()
    except Exception as e:  # noqa: BLE001
        _log.debug("tkinter font enumeration failed: %s", e)
        return []
    return families


def _try_matplotlib_fonts() -> list[str]:
    try:
        from matplotlib import font_manager  # type: ignore[import-not-found]
    except ImportError:
        return []
    try:
        return [f.name for f in font_manager.fontManager.ttflist]
    except Exception as e:  # noqa: BLE001
        _log.debug("matplotlib font enumeration failed: %s", e)
        return []


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
