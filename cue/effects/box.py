"""囲み枠 (box) エフェクト。

完成版の ``box.setting`` (Fusion 出力) のプレースホルダを Python 側で計算した
値で埋めて返す。テンプレ構造:

- ``Background1``     : 内側塗り (BG_COLOR_*)
- ``Rectangle1``      : 内側塗り用マスク (POS_X/Y, WIDTH, HEIGHT)
- ``Background2-5``   : 4辺の枠線 (BORDER_COLOR_*)
- ``Rectangle2-5``    : 各辺の形状マスク (BORDER_THICKNESS + キーフレーム)
- ``Rectangle*CenterX/Y, Rectangle*Width/Height`` : 各辺の描画アニメ
- ``Merge1-3``        : 背景 + 4辺の合成 (静的、Blend なし)
- ``Merge4Blend``     : 全体フェード (退場用)
- ``Text1``           : 中央テキスト (TEXT_*)
- ``Merge5Blend``     : テキスト出現フェード

部品の有効/無効は **Alpha=0 / 空文字列** で表現する (ノードは削除しない)。
これにより Merge1-5 の SourceOp 参照を壊さない。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal, TYPE_CHECKING

from cue import config
from cue.effects.base import Effect, EffectParams
from cue.utils import color as color_utils
from cue.utils import template as template_utils

if TYPE_CHECKING:
    from cue.effects.context import EffectContext


# ----- サブコンフィグ -----


@dataclass
class BorderConfig:
    """枠線の見た目とアニメーション設定。"""

    enabled: bool = True
    color: str = config.DEFAULT_BORDER_COLOR
    width_px: int = config.DEFAULT_BORDER_WIDTH_PX
    radius_px: int = config.DEFAULT_BORDER_RADIUS_PX
    """※ 現在のテンプレでは角丸はサポート外 (Phase 2)。値は保持するがレンダリングには反映されない。"""
    animation: Literal["cw", "ccw", "none"] = "cw"
    draw_duration_sec: float = config.DEFAULT_BORDER_DRAW_SEC


@dataclass
class BackgroundConfig:
    """枠の内側を塗る背景設定。"""

    fill_type: Literal["transparent", "solid"] = "transparent"
    color: str = config.DEFAULT_BG_COLOR
    opacity_pct: float = config.DEFAULT_BG_OPACITY_PCT  # solid 時のみ有効


@dataclass
class TextConfig:
    """枠内に重ねるテキスト設定。``content`` が空ならレンダリングされない。"""

    content: str = ""
    color: str = config.DEFAULT_TEXT_COLOR
    font_family: str = ""  # 空なら ``utils.fonts.resolve_default_font()`` を使うのは UI 側の責務
    size_px: int = config.DEFAULT_TEXT_SIZE_PX
    weight: Literal["Regular", "Bold"] = "Bold"
    align_h: Literal["left", "center", "right"] = "center"
    align_v: Literal["top", "center", "bottom"] = "center"
    padding_px: int = config.DEFAULT_TEXT_PADDING_PX
    """※ 現テンプレは Text+ ノードの Padding 入力を参照していないため Phase 2。"""
    appearance: Literal["after_border", "with_border"] = "after_border"
    fade_in_sec: float = config.DEFAULT_TEXT_FADE_IN_SEC


@dataclass
class BoxParams(EffectParams):
    """囲み枠エフェクトのパラメータ。"""

    pos_x: float = config.DEFAULT_BOX_POS[0]
    pos_y: float = config.DEFAULT_BOX_POS[1]
    width: float = config.DEFAULT_BOX_SIZE[0]
    height: float = config.DEFAULT_BOX_SIZE[1]

    preset: str = "plain"
    border: BorderConfig = field(default_factory=BorderConfig)
    background: BackgroundConfig = field(default_factory=BackgroundConfig)
    text: TextConfig = field(default_factory=TextConfig)


# ----- 定数 (Fusion Text+ の Justification 整数値) -----

_H_JUSTIFY: dict[str, int] = {"left": 0, "center": 1, "right": 2}
_V_JUSTIFY: dict[str, int] = {"top": 0, "center": 1, "bottom": 2}


# ----- エフェクト -----


class BoxEffect(Effect):
    """囲み枠 + (任意) 背景 + (任意) テキスト。"""

    name: ClassVar[str] = "box"
    display_name: ClassVar[str] = "囲み枠"
    params_class: ClassVar[type[EffectParams]] = BoxParams
    template_filename: ClassVar[str] = "box.setting"

    @classmethod
    def presets(cls) -> dict[str, dict[str, Any]]:
        return dict(config.BOX_PRESETS)

    @classmethod
    def preset_label(cls, preset_name: str) -> str:
        info = config.BOX_PRESETS.get(preset_name)
        return str(info.get("label", preset_name)) if info else preset_name

    @classmethod
    def disabled_fields_for(cls, preset_name: str) -> list[str]:
        info = config.BOX_PRESETS.get(preset_name)
        return list(info.get("disabled_fields", [])) if info else []

    def _clip_discriminator(self, context: EffectContext) -> list[str]:
        params: BoxParams = self.params  # type: ignore[assignment]
        slots = [params.preset]
        if params.border.enabled and params.border.width_px > 0:
            slots.append(params.border.animation)
        return slots

    # ----- バリデーション -----

    def validate(self) -> list[str]:
        errors = super().validate()
        params: BoxParams = self.params  # type: ignore[assignment]

        for name, value in (
            ("pos_x", params.pos_x), ("pos_y", params.pos_y),
            ("width", params.width), ("height", params.height),
        ):
            if not 0.0 <= value <= 1.0:
                errors.append(f"{name} は 0.0-1.0 の範囲で指定してください。")

        if params.preset not in config.BOX_PRESETS:
            errors.append(f"未知の用途プリセット: {params.preset!r}")

        if params.border.enabled:
            try:
                color_utils.parse_hex(params.border.color)
            except color_utils.InvalidHexColorError as e:
                errors.append(f"枠線の色が不正: {e}")
            if params.border.width_px < 0:
                errors.append("枠線の太さは 0 以上で指定してください。")
            if params.border.radius_px < 0:
                errors.append("角丸 R は 0 以上で指定してください。")
            if params.border.animation not in ("cw", "ccw", "none"):
                errors.append(f"未知の描画アニメ: {params.border.animation!r}")
            if params.border.draw_duration_sec < 0:
                errors.append("枠線の描画秒数は 0 以上で指定してください。")

        if params.background.fill_type == "solid":
            try:
                color_utils.parse_hex(params.background.color)
            except color_utils.InvalidHexColorError as e:
                errors.append(f"背景色が不正: {e}")
            if not 0.0 <= params.background.opacity_pct <= 100.0:
                errors.append("背景の不透明度は 0-100 の範囲で指定してください。")

        if params.text.content:
            try:
                color_utils.parse_hex(params.text.color)
            except color_utils.InvalidHexColorError as e:
                errors.append(f"テキスト色が不正: {e}")
            if params.text.size_px <= 0:
                errors.append("フォントサイズは 0 より大きい値を指定してください。")
            if params.text.weight not in ("Regular", "Bold"):
                errors.append(f"未知のフォントウェイト: {params.text.weight!r}")
            if params.text.align_h not in _H_JUSTIFY:
                errors.append(f"未知のテキスト揃え (横): {params.text.align_h!r}")
            if params.text.align_v not in _V_JUSTIFY:
                errors.append(f"未知のテキスト揃え (縦): {params.text.align_v!r}")
            if params.text.appearance not in ("after_border", "with_border"):
                errors.append(f"未知のテキスト出現タイミング: {params.text.appearance!r}")

        return errors

    # ----- Fusion Composition 生成 -----

    def build_fusion_settings(self, context: EffectContext) -> str:
        params: BoxParams = self.params  # type: ignore[assignment]
        fps = context.frame_rate
        canvas_w, canvas_h = context.canvas_size

        # ----- フレーム数 (1 以上にクランプ、キーフレーム衝突を避ける) -----
        duration_frames = max(1, int(round(params.duration_sec * fps)))
        fade_out_frames = max(0, int(round(params.fade_out_sec * fps)))
        text_fade_in_frames = max(1, int(round(params.text.fade_in_sec * fps)))

        # ----- 配置 (Fusion 左下原点に変換, Q4) -----
        pos_x_f = params.pos_x
        pos_y_f = 1.0 - params.pos_y
        width_f = params.width
        height_f = params.height

        # 枠線の太さは画面比率 (Q3)。BoxParams は px なので canvas_h で正規化。
        border_thickness = params.border.width_px / max(1, canvas_h)

        # ----- 4辺の描画アニメ -----
        anim = self._compute_border_animation(
            params, pos_x_f, pos_y_f, width_f, height_f, fps,
        )

        # ----- フェードタイミング -----
        if params.border.enabled and params.text.appearance == "after_border":
            frame_border_complete = anim["complete"]
        else:
            frame_border_complete = 0

        # フェードアウト開始は border 完了後 + テキスト fade-in 完了後
        # 各キーフレームの frame 番号は単調増加でなければならない (Fusion 制約)
        frame_text_fade_in_end = frame_border_complete + text_fade_in_frames
        frame_fade_out_start = max(
            frame_text_fade_in_end + 1,
            duration_frames - fade_out_frames,
        )
        # FRAME_END は最低でも fade_out_start より後
        frame_end = max(frame_fade_out_start + 1, duration_frames)

        # ----- 色 -----
        bg_color_rgba = self._compute_background_color(params)
        border_color_rgba = self._compute_border_color(params)
        text_rgb = color_utils.hex_to_rgb_float(
            params.text.color if params.text.content else config.DEFAULT_TEXT_COLOR
        )

        # ----- テキスト -----
        text_size = params.text.size_px / max(1, canvas_h)  # Fusion Text+ Size は画面比率系
        text_h_justify = _H_JUSTIFY.get(params.text.align_h, 1)
        text_v_justify = _V_JUSTIFY.get(params.text.align_v, 1)

        mapping: dict[str, Any] = {
            # Canvas / 全体
            "CANVAS_WIDTH":  canvas_w,
            "CANVAS_HEIGHT": canvas_h,
            "FRAME_END":     frame_end,
            # 配置
            "POS_X":   pos_x_f,
            "POS_Y":   pos_y_f,
            "WIDTH":   width_f,
            "HEIGHT":  height_f,
            "BORDER_THICKNESS": border_thickness,
            # 色
            "BG_COLOR_R": bg_color_rgba[0], "BG_COLOR_G": bg_color_rgba[1],
            "BG_COLOR_B": bg_color_rgba[2], "BG_COLOR_A": bg_color_rgba[3],
            "BORDER_COLOR_R": border_color_rgba[0], "BORDER_COLOR_G": border_color_rgba[1],
            "BORDER_COLOR_B": border_color_rgba[2], "BORDER_COLOR_A": border_color_rgba[3],
            # 4辺アニメ
            "FRAME_TOP_START":    anim["top_start"],
            "FRAME_TOP_END":      anim["top_end"],
            "TOP_X_START":        anim["top_x_start"],
            "FRAME_RIGHT_START":  anim["right_start"],
            "FRAME_RIGHT_END":    anim["right_end"],
            "RIGHT_Y_START":      anim["right_y_start"],
            "FRAME_BOTTOM_START": anim["bottom_start"],
            "FRAME_BOTTOM_END":   anim["bottom_end"],
            "BOTTOM_X_START":     anim["bottom_x_start"],
            "FRAME_LEFT_START":   anim["left_start"],
            "FRAME_LEFT_END":     anim["left_end"],
            "LEFT_Y_START":       anim["left_y_start"],
            # フェード
            "FRAME_BORDER_COMPLETE":  frame_border_complete,
            "FRAME_FADE_OUT_START":   frame_fade_out_start,
            "FRAME_TEXT_FADE_IN_END": frame_text_fade_in_end,
            # テキスト
            "TEXT_CONTENT":   template_utils.escape_lua_string(params.text.content),
            "TEXT_FONT":      template_utils.escape_lua_string(params.text.font_family),
            "TEXT_STYLE":     template_utils.escape_lua_string(params.text.weight),
            "TEXT_SIZE":      text_size,
            "TEXT_COLOR_R":   text_rgb[0],
            "TEXT_COLOR_G":   text_rgb[1],
            "TEXT_COLOR_B":   text_rgb[2],
            "TEXT_POS_X":     pos_x_f,
            "TEXT_POS_Y":     pos_y_f,
            "TEXT_V_JUSTIFY": text_v_justify,
            "TEXT_H_JUSTIFY": text_h_justify,
        }

        return template_utils.render_template(self.load_template(), mapping)

    # ----- 内部ヘルパ -----

    def _compute_background_color(self, params: BoxParams) -> tuple[float, float, float, float]:
        """背景の RGBA を返す。透過時は Alpha=0。"""
        if params.background.fill_type == "solid":
            return color_utils.hex_to_rgba_float(
                params.background.color, params.background.opacity_pct
            )
        # transparent: 色は何でも良いが、安定性のため黒を入れる
        r, g, b = color_utils.hex_to_rgb_float(config.DEFAULT_BG_COLOR)
        return (r, g, b, 0.0)

    def _compute_border_color(self, params: BoxParams) -> tuple[float, float, float, float]:
        """枠線の RGBA。enabled=False または width=0 のときは Alpha=0 で透明化。"""
        if params.border.enabled and params.border.width_px > 0:
            r, g, b = color_utils.hex_to_rgb_float(params.border.color)
            return (r, g, b, 1.0)
        r, g, b = color_utils.hex_to_rgb_float(config.DEFAULT_BORDER_COLOR)
        return (r, g, b, 0.0)

    def _compute_border_animation(
        self,
        params: BoxParams,
        pos_x: float, pos_y: float,
        width: float, height: float,
        fps: float,
    ) -> dict[str, float | int]:
        """4辺の描画アニメに必要なフレーム番号と開始座標を計算する。

        各辺の rectangle は ``Width`` (or ``Height``) を 0 から完成サイズに伸ばす。
        ``Center`` 座標は「辺の端」から「箱の中心」へ移動することで、
        端から伸びるラインとして見えるようにする (Fusion Y は左下原点 = 上向き)。
        """
        anim_kind = params.border.animation
        # none のときは config の専用デフォルト秒数を使う
        if anim_kind == "none":
            total_sec = config.DEFAULT_BORDER_DRAW_NONE_SEC
        else:
            total_sec = params.border.draw_duration_sec
        total_frames = max(1, int(round(total_sec * fps)))

        # 辺の端 (Fusion 座標系)
        left_x   = pos_x - width  / 2.0
        right_x  = pos_x + width  / 2.0
        top_y    = pos_y + height / 2.0  # Fusion: Y 大が上
        bottom_y = pos_y - height / 2.0

        # 各辺の START / END フレーム
        if anim_kind == "cw":
            # 上 → 右 → 下 → 左
            seg = max(1, total_frames // 4)
            top_s,    top_e    = 0,         seg
            right_s,  right_e  = seg,       seg * 2
            bottom_s, bottom_e = seg * 2,   seg * 3
            left_s,   left_e   = seg * 3,   seg * 4
            top_x_start    = left_x       # 上辺: 左端から
            right_y_start  = top_y        # 右辺: 上端から
            bottom_x_start = right_x      # 下辺: 右端から
            left_y_start   = bottom_y     # 左辺: 下端から
            complete = seg * 4
        elif anim_kind == "ccw":
            # 上 → 左 → 下 → 右
            seg = max(1, total_frames // 4)
            top_s,    top_e    = 0,         seg
            left_s,   left_e   = seg,       seg * 2
            bottom_s, bottom_e = seg * 2,   seg * 3
            right_s,  right_e  = seg * 3,   seg * 4
            top_x_start    = right_x      # 上辺: 右端から
            left_y_start   = top_y        # 左辺: 上端から
            bottom_x_start = left_x       # 下辺: 左端から
            right_y_start  = bottom_y     # 右辺: 下端から
            complete = seg * 4
        else:
            # none: 4辺同時
            top_s = right_s = bottom_s = left_s = 0
            top_e = right_e = bottom_e = left_e = total_frames
            top_x_start    = pos_x
            right_y_start  = pos_y
            bottom_x_start = pos_x
            left_y_start   = pos_y
            complete = total_frames

        return {
            "top_start":     top_s,    "top_end":     top_e,    "top_x_start":    top_x_start,
            "right_start":   right_s,  "right_end":   right_e,  "right_y_start":  right_y_start,
            "bottom_start":  bottom_s, "bottom_end":  bottom_e, "bottom_x_start": bottom_x_start,
            "left_start":    left_s,   "left_end":    left_e,   "left_y_start":   left_y_start,
            "complete":      complete,
        }
