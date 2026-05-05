"""定数・パス・デフォルト値の集約。

ここを書き換えるだけで、命名規約・トラック番号・アセットパスなどを変更できる。
"""
from __future__ import annotations

import logging
from pathlib import Path

_log = logging.getLogger(__name__)

MAX_DISCRIMINATOR_SLOTS: int = 3
"""クリップ名 discriminator の推奨最大スロット数。これを超えると識別子の見直しサイン。"""

# ----- パス -----

PACKAGE_ROOT: Path = Path(__file__).resolve().parent
ASSETS_DIR: Path = PACKAGE_ROOT / "assets"
ARROWS_DIR: Path = ASSETS_DIR / "arrows"
TEMPLATES_DIR: Path = ASSETS_DIR / "templates"


# ----- クリップ命名規約 -----

CLIP_NAME_PREFIX: str = "cue"
"""本ツールが配置するクリップに付ける接頭辞。

完全な命名規約: ``cue_<effect>_<frame>_<discriminator>``
例: ``cue_arrow_1234_tr`` (フレーム1234にある右上矢印)

``discriminator`` はエフェクト固有の識別子。矢印なら方向略称 (tr / r / br / ...)。
省略時は ``cue_<effect>_<frame>`` のみ。
"""


def make_clip_name(
    effect_name: str,
    frame: int,
    discriminator: str | list[str] = "",
) -> str:
    """衝突検出用のクリップ名を生成する。

    Parameters
    ----------
    effect_name : 例 "arrow"
    frame : マーカーのフレーム位置。
    discriminator :
        エフェクト固有の識別子。

        - ``str`` の場合: そのまま単一スロットとして付加 (例: 矢印の "tr")
        - ``list[str]`` の場合: アンダースコア結合し複数スロットとして付加
          (例: 箱の ``["plain", "cw"]`` → ``cue_box_<frame>_plain_cw``)

        スロット数が ``MAX_DISCRIMINATOR_SLOTS`` を超えると警告ログを出す
        (見直しサイン)。
    """
    parts = [CLIP_NAME_PREFIX, effect_name, str(int(frame))]
    if isinstance(discriminator, list):
        slots = [s.replace(" ", "") for s in discriminator if s]
        if len(slots) > MAX_DISCRIMINATOR_SLOTS:
            _log.warning(
                "clip name discriminator has %d slots (recommended max: %d): %s",
                len(slots),
                MAX_DISCRIMINATOR_SLOTS,
                slots,
            )
        if slots:
            parts.append("_".join(slots))
    elif discriminator:
        parts.append(discriminator.replace(" ", ""))
    return "_".join(parts)


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
#
# 8方向 (top_right / right / ... ) は画面の縁から中央被写体を指す矢印。
# "center" だけは別系統で、"画面中央付近の被写体を真上から指す pin/tag 風"。
# 用途: 中央寄りの被写体に「ここ!」と注意を向けたいとき。
# ユーザーは pos_y を下げて (例 0.35) 被写体の真上に来るよう調整して使う想定。

ARROW_DIRECTIONS: dict[str, dict[str, float | str]] = {
    "top_right":    {"asset": "arrow_tr.png", "abbr": "tr", "pos_x": 0.80, "pos_y": 0.20, "label": "右上"},
    "right":        {"asset": "arrow_r.png",  "abbr": "r",  "pos_x": 0.85, "pos_y": 0.50, "label": "右"},
    "bottom_right": {"asset": "arrow_br.png", "abbr": "br", "pos_x": 0.80, "pos_y": 0.80, "label": "右下"},
    "bottom":       {"asset": "arrow_b.png",  "abbr": "b",  "pos_x": 0.50, "pos_y": 0.85, "label": "下"},
    "bottom_left":  {"asset": "arrow_bl.png", "abbr": "bl", "pos_x": 0.20, "pos_y": 0.80, "label": "左下"},
    "left":         {"asset": "arrow_l.png",  "abbr": "l",  "pos_x": 0.15, "pos_y": 0.50, "label": "左"},
    "top_left":     {"asset": "arrow_tl.png", "abbr": "tl", "pos_x": 0.20, "pos_y": 0.20, "label": "左上"},
    "top":          {"asset": "arrow_t.png",  "abbr": "t",  "pos_x": 0.50, "pos_y": 0.15, "label": "上"},
    "center":       {"asset": "arrow_c.png",  "abbr": "c",  "pos_x": 0.50, "pos_y": 0.50, "label": "下向き(中央)"},
}


# ----- 囲み枠 (box) のデフォルト -----

DEFAULT_BORDER_COLOR: str = "#FFFFFF"
DEFAULT_BORDER_WIDTH_PX: int = 4
DEFAULT_BORDER_RADIUS_PX: int = 8
DEFAULT_BORDER_DRAW_SEC: float = 0.8        # cw / ccw のとき
DEFAULT_BORDER_DRAW_NONE_SEC: float = 0.3   # 4辺同時 (none) のとき

DEFAULT_BG_COLOR: str = "#000000"
DEFAULT_BG_OPACITY_PCT: float = 80.0

DEFAULT_TEXT_COLOR: str = "#FFFFFF"
DEFAULT_TEXT_SIZE_PX: int = 24
DEFAULT_TEXT_PADDING_PX: int = 16
DEFAULT_TEXT_FADE_IN_SEC: float = 0.3

DEFAULT_BOX_POS: tuple[float, float] = (0.5, 0.5)
DEFAULT_BOX_SIZE: tuple[float, float] = (0.3, 0.2)


RECOMMENDED_FONTS: tuple[str, ...] = (
    "Noto Sans JP",
    "Yu Gothic UI",
    "Meiryo",
    "Hiragino Sans",
)
"""よく使うフォント。UI でセクション分けして上に固定表示する。"""


# ----- 囲み枠 (box) の用途プリセット -----
# 値はドット記法でネストされた BoxParams 属性を指す (例: "border.color")。
# ``apply_preset()`` がこれを解釈する。

BOX_PRESETS: dict[str, dict] = {
    "plain": {
        "label": "囲み枠のみ",
        "values": {},  # 全てデフォルト
        "disabled_fields": [],
    },
    "highlight_label": {
        "label": "ハイライト枠 + ラベル",
        "values": {
            "border.color": "#FFD700",
            "text.color": "#FFFFFF",
            "text.weight": "Bold",
            "text.size_px": 24,
        },
        "disabled_fields": [],
    },
    "signboard_white": {
        "label": "看板テロップ (白)",
        "values": {
            "background.fill_type": "solid",
            "background.color": "#FFFFFF",
            "background.opacity_pct": 100.0,
            "border.enabled": False,
            "text.color": "#000000",
            "text.weight": "Bold",
            "text.size_px": 28,
            "text.align_h": "center",
            "text.align_v": "center",
        },
        "disabled_fields": [
            "border.color", "border.width_px", "border.radius_px",
            "border.animation", "border.draw_duration_sec",
        ],
    },
    "signboard_black": {
        "label": "看板テロップ (黒)",
        "values": {
            "background.fill_type": "solid",
            "background.color": "#000000",
            "background.opacity_pct": 100.0,
            "border.enabled": True,
            "border.color": "#FFFFFF",
            "border.width_px": 2,
            "text.color": "#FFFFFF",
            "text.weight": "Bold",
            "text.size_px": 28,
            "text.align_h": "center",
            "text.align_v": "center",
        },
        "disabled_fields": [],
    },
    "translucent_panel": {
        "label": "半透過パネル",
        "values": {
            "background.fill_type": "solid",
            "background.color": "#000000",
            "background.opacity_pct": 70.0,
            "border.enabled": False,
            "text.color": "#FFFFFF",
            "text.weight": "Regular",
            "text.size_px": 22,
            "text.align_h": "left",
        },
        "disabled_fields": [
            "border.color", "border.width_px", "border.radius_px",
            "border.animation", "border.draw_duration_sec",
        ],
    },
    "chapter_title": {
        "label": "章タイトルカード",
        "values": {
            "pos_x": 0.5,
            "pos_y": 0.5,
            "width": 1.0,
            "height": 0.25,
            "background.fill_type": "solid",
            "background.color": "#000000",
            "background.opacity_pct": 90.0,
            "border.enabled": False,
            "border.animation": "none",
            "text.color": "#FFFFFF",
            "text.weight": "Bold",
            "text.size_px": 48,
            "text.align_h": "center",
            "text.align_v": "center",
            "duration_sec": 3.0,
            "fade_out_sec": 0.5,
        },
        "disabled_fields": [
            "border.color", "border.width_px", "border.radius_px",
            "border.animation", "border.draw_duration_sec",
        ],
    },
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
