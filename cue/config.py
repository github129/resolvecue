"""定数・パス・デフォルト値の集約。

ここを書き換えるだけで、命名規約・トラック番号・アセットパスなどを変更できる。
"""
from __future__ import annotations

from pathlib import Path

# ----- パス -----

PACKAGE_ROOT: Path = Path(__file__).resolve().parent
ASSETS_DIR: Path = PACKAGE_ROOT / "assets"
ARROWS_DIR: Path = ASSETS_DIR / "arrows"
TEMPLATES_DIR: Path = ASSETS_DIR / "templates"


# ----- クリップ命名規約 -----

CLIP_NAME_PREFIX: str = "cue"
"""本ツールが配置するクリップに付ける接頭辞。

完全な命名規約: ``cue_<effect>_<color>_f<frame>``
例: ``cue_arrow_Red_f12345``
"""


def make_clip_name(effect_name: str, color: str, frame: int) -> str:
    """衝突検出用のクリップ名を生成する。

    Parameters
    ----------
    effect_name : 例 "arrow"
    color : マーカー色 (例 "Red"). Resolve のマーカー色文字列をそのまま使う。
    frame : マーカーのフレーム位置。
    """
    safe_color = color.replace(" ", "")
    return f"{CLIP_NAME_PREFIX}_{effect_name}_{safe_color}_f{frame}"


def is_cue_clip(clip_name: str, effect_name: str | None = None) -> bool:
    """クリップ名が本ツール由来かを判定する。

    ``effect_name`` を指定すると、そのエフェクトのみを対象にする。
    """
    if not clip_name.startswith(f"{CLIP_NAME_PREFIX}_"):
        return False
    if effect_name is None:
        return True
    return clip_name.startswith(f"{CLIP_NAME_PREFIX}_{effect_name}_")


# ----- トラック -----

DEFAULT_TARGET_TRACK: int = 3
"""「全マーカーに適用」時のデフォルト配置先 (V3)。"""

PREVIEW_TRACK_NAME: str = "cue_preview"
"""プレビュー専用トラックの名前。"""

PREVIEW_TRACK_INDEX: int = 10
"""プレビュー専用トラックの希望インデックス (V10)。実環境のトラック数次第で末尾に丸める。"""


# ----- エフェクトのデフォルト -----

DEFAULT_DURATION_SEC: float = 3.0
DEFAULT_FADE_IN_SEC: float = 0.3
DEFAULT_FADE_OUT_SEC: float = 0.3
DEFAULT_SCALE: float = 1.0


# ----- 矢印プリセット -----
# 「矢印の根元位置 (画面のどこに矢印が表示されるか)」基準。
# pos_x, pos_y は 0.0-1.0 の正規化座標 (左上原点, Resolve の標準とは別途変換する)。

ARROW_DIRECTIONS: dict[str, dict[str, float | str]] = {
    "top_right":     {"asset": "arrow_tr.png", "pos_x": 0.80, "pos_y": 0.20, "label": "右上"},
    "right":         {"asset": "arrow_r.png",  "pos_x": 0.85, "pos_y": 0.50, "label": "右"},
    "bottom_right":  {"asset": "arrow_br.png", "pos_x": 0.80, "pos_y": 0.80, "label": "右下"},
    "bottom":        {"asset": "arrow_b.png",  "pos_x": 0.50, "pos_y": 0.85, "label": "下"},
    "bottom_left":   {"asset": "arrow_bl.png", "pos_x": 0.20, "pos_y": 0.80, "label": "左下"},
    "left":          {"asset": "arrow_l.png",  "pos_x": 0.15, "pos_y": 0.50, "label": "左"},
    "top_left":      {"asset": "arrow_tl.png", "pos_x": 0.20, "pos_y": 0.20, "label": "左上"},
    "top":           {"asset": "arrow_t.png",  "pos_x": 0.50, "pos_y": 0.15, "label": "上"},
    "center":        {"asset": "arrow_c.png",  "pos_x": 0.50, "pos_y": 0.50, "label": "中央指し"},
}


# ----- Resolve のマーカー色一覧 -----
# Resolve UI が公式に提供する色名。GUI のフィルタで使う。
RESOLVE_MARKER_COLORS: tuple[str, ...] = (
    "Blue",
    "Cyan",
    "Green",
    "Yellow",
    "Red",
    "Pink",
    "Purple",
    "Fuchsia",
    "Rose",
    "Lavender",
    "Sky",
    "Mint",
    "Lemon",
    "Sand",
    "Cocoa",
    "Cream",
)
