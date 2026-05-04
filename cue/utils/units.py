"""単位変換の集約点。

MVP では「px のまま返す」関数だけを提供するが、Phase 2 で「枠サイズに対する
相対値モード」を導入するときに、ここの実装だけを差し替えれば対応できるように
してある。

利用側は常にこのモジュール経由で px を取得すること。
"""
from __future__ import annotations

from typing import Literal

FontSizeUnit = Literal["px", "ratio"]


def font_size_to_px(
    size: float,
    *,
    unit: FontSizeUnit = "px",
    screen_height_px: int = 1080,
) -> int:
    """フォントサイズを最終的な px に解決する。

    Parameters
    ----------
    size : 数値。``unit="px"`` ならそのまま、``unit="ratio"`` なら
           ``screen_height_px`` に対する比率 (0.0-1.0)。
    unit : "px" (MVP) / "ratio" (Phase 2)。
    screen_height_px : ratio モードでの基準高さ。HD なら 1080, 4K なら 2160。

    Returns
    -------
    整数 px 値。
    """
    if unit == "px":
        return int(round(size))
    if unit == "ratio":
        return int(round(size * screen_height_px))
    raise ValueError(f"Unknown font size unit: {unit!r}")
