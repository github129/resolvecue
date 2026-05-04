"""囲み枠 (box) エフェクト。

枠線・背景・テキストの3部品を Fusion Composition 上で合成する。
各部品は ``enabled`` フラグや ``content`` の有無で動的に on/off される。

部品レイヤー順 (下から上):
1. Background (Background ノード + Rectangle マスク)
2. Border    (4辺の Rectangle/Polyline、描画アニメ付き)
3. Text+

タイミング:
- 全体: ``duration_sec`` (基底) で保持、``fade_out_sec`` で退場
- 枠線: ``border.draw_duration_sec`` で描画 (cw/ccw/none)
- 背景: 枠線描画と同時に opacity 0→100% でフェードイン
- テキスト: ``text.appearance`` が "after_border" なら枠線完了後、
            "with_border" なら同時に ``text.fade_in_sec`` でフェードイン
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal, TYPE_CHECKING

from cue import config
from cue.effects.base import Effect, EffectParams
from cue.utils import color as color_utils
from cue.utils import units as units_utils

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
    """枠内に重ねるテキスト設定。

    ``content`` が空文字ならテキストノード自体を生成しない。
    """

    content: str = ""
    color: str = config.DEFAULT_TEXT_COLOR
    font_family: str = ""  # 空なら ``utils.fonts.resolve_default_font()``
    size_px: int = config.DEFAULT_TEXT_SIZE_PX
    weight: Literal["Regular", "Bold"] = "Bold"
    align_h: Literal["left", "center", "right"] = "center"
    align_v: Literal["top", "center", "bottom"] = "center"
    padding_px: int = config.DEFAULT_TEXT_PADDING_PX
    appearance: Literal["after_border", "with_border"] = "after_border"
    fade_in_sec: float = config.DEFAULT_TEXT_FADE_IN_SEC


@dataclass
class BoxParams(EffectParams):
    """囲み枠エフェクトのパラメータ。"""

    # 配置 (画面比率 0.0-1.0、(pos_x, pos_y) は箱の中心座標)
    pos_x: float = config.DEFAULT_BOX_POS[0]
    pos_y: float = config.DEFAULT_BOX_POS[1]
    width: float = config.DEFAULT_BOX_SIZE[0]
    height: float = config.DEFAULT_BOX_SIZE[1]

    preset: str = "plain"
    """``config.BOX_PRESETS`` のキー。クリップ名 discriminator にも使う。"""

    border: BorderConfig = field(default_factory=BorderConfig)
    background: BackgroundConfig = field(default_factory=BackgroundConfig)
    text: TextConfig = field(default_factory=TextConfig)


# ----- エフェクト -----


class BoxEffect(Effect):
    """囲み枠 + (任意) 背景 + (任意) テキスト。"""

    name: ClassVar[str] = "box"
    display_name: ClassVar[str] = "囲み枠"
    params_class: ClassVar[type[EffectParams]] = BoxParams
    template_filename: ClassVar[str] = "box.setting"

    @classmethod
    def presets(cls) -> dict[str, dict[str, Any]]:
        """``config.BOX_PRESETS`` をそのまま返す (メタ付き形式)。"""
        return dict(config.BOX_PRESETS)

    @classmethod
    def preset_label(cls, preset_name: str) -> str:
        info = config.BOX_PRESETS.get(preset_name)
        if info is None:
            return preset_name
        return str(info.get("label", preset_name))

    @classmethod
    def disabled_fields_for(cls, preset_name: str) -> list[str]:
        info = config.BOX_PRESETS.get(preset_name)
        if info is None:
            return []
        return list(info.get("disabled_fields", []))

    def _clip_discriminator(self, context: EffectContext) -> list[str]:
        params: BoxParams = self.params  # type: ignore[assignment]
        slots = [params.preset]
        # 枠線がある場合だけ描画方向を識別子に含める
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
            if params.text.align_h not in ("left", "center", "right"):
                errors.append(f"未知のテキスト揃え (横): {params.text.align_h!r}")
            if params.text.align_v not in ("top", "center", "bottom"):
                errors.append(f"未知のテキスト揃え (縦): {params.text.align_v!r}")
            if params.text.appearance not in ("after_border", "with_border"):
                errors.append(f"未知のテキスト出現タイミング: {params.text.appearance!r}")

        return errors

    # ----- Fusion Composition 生成 -----

    def build_fusion_settings(self, context: EffectContext) -> str:
        """テンプレを読み込みつつ、有効な部品のノードだけを差し込んで返す。

        テンプレ ``box.setting`` 内のプレースホルダ:
            ``{{NODES_BACKGROUND}}`` / ``{{NODES_BORDER}}`` / ``{{NODES_TEXT}}``
            ``{{MERGE_BACKGROUND}}`` / ``{{MERGE_BORDER}}`` / ``{{MERGE_TEXT}}``
            ``{{TIMING}}``

        無効な部品は空文字を入れて Fusion 側の ``ordered() {}`` を空に保つ。
        Fusion テンプレの完成は実機作業 (assets/templates/box.setting に詳述)。
        """
        params: BoxParams = self.params  # type: ignore[assignment]
        fps = context.frame_rate
        template = self.load_template()

        replacements = {
            # 配置
            "{{POS_X}}": f"{params.pos_x:.4f}",
            "{{POS_Y}}": f"{1.0 - params.pos_y:.4f}",   # Fusion は左下原点
            "{{WIDTH}}": f"{params.width:.4f}",
            "{{HEIGHT}}": f"{params.height:.4f}",

            # 全体タイミング
            "{{DURATION_FRAMES}}": str(int(round(params.duration_sec * fps))),
            "{{FADE_OUT_FRAMES}}": str(int(round(params.fade_out_sec * fps))),

            # 枠線
            "{{NODES_BORDER}}": self._build_border_nodes(params, fps),
            "{{MERGE_BORDER}}": "Border1" if params.border.enabled else "",

            # 背景
            "{{NODES_BACKGROUND}}": self._build_background_nodes(params, fps),
            "{{MERGE_BACKGROUND}}": (
                "Background1" if params.background.fill_type == "solid" else ""
            ),

            # テキスト
            "{{NODES_TEXT}}": self._build_text_nodes(params, fps),
            "{{MERGE_TEXT}}": "TextNode1" if params.text.content else "",
        }
        for k, v in replacements.items():
            template = template.replace(k, v)
        return template

    # ----- ノード組み立て (実装メモ: 実機テンプレ完成時に詳細化する) -----

    def _build_background_nodes(self, params: BoxParams, fps: float) -> str:
        if params.background.fill_type != "solid":
            return ""
        rgba = color_utils.hex_to_rgba_float(
            params.background.color, params.background.opacity_pct
        )
        appear_frames = int(round(params.border.draw_duration_sec * fps))
        return _BG_NODE_TEMPLATE.format(
            r=rgba[0], g=rgba[1], b=rgba[2], a=rgba[3],
            appear_frames=appear_frames,
        )

    def _build_border_nodes(self, params: BoxParams, fps: float) -> str:
        if not params.border.enabled or params.border.width_px <= 0:
            return ""
        rgb = color_utils.hex_to_rgb_float(params.border.color)
        if params.border.animation == "none":
            draw_sec = config.DEFAULT_BORDER_DRAW_NONE_SEC
        else:
            draw_sec = params.border.draw_duration_sec
        draw_frames = max(1, int(round(draw_sec * fps)))
        return _BORDER_NODE_TEMPLATE.format(
            r=rgb[0], g=rgb[1], b=rgb[2],
            width_px=params.border.width_px,
            radius_px=params.border.radius_px,
            animation=params.border.animation,
            draw_frames=draw_frames,
        )

    def _build_text_nodes(self, params: BoxParams, fps: float) -> str:
        if not params.text.content:
            return ""
        rgb = color_utils.hex_to_rgb_float(params.text.color)
        size_px = units_utils.font_size_to_px(params.text.size_px, unit="px")
        if params.text.appearance == "after_border":
            delay_frames = int(round(params.border.draw_duration_sec * fps))
        else:
            delay_frames = 0
        fade_frames = max(1, int(round(params.text.fade_in_sec * fps)))
        # Lua/setting 文字列向けにエスケープ
        text_escaped = (
            params.text.content
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
        )
        font_family = params.text.font_family or ""
        return _TEXT_NODE_TEMPLATE.format(
            text=text_escaped,
            font=font_family,
            weight=params.text.weight,
            size_px=size_px,
            r=rgb[0], g=rgb[1], b=rgb[2],
            align_h=params.text.align_h,
            align_v=params.text.align_v,
            padding_px=params.text.padding_px,
            delay_frames=delay_frames,
            fade_frames=fade_frames,
        )


# ----- ノードテンプレ片 (Fusion .setting Lua-like 構文の擬似形) -----
# 実機での仕上げ前提のプレースホルダ。assets/templates/box.setting と
# 整合する形で書き出される想定。

_BG_NODE_TEMPLATE = """
        Background1 = Background {{
            Inputs = {{
                Type    = Input {{ Value = "Solid", }},
                TopLeftRed   = Input {{ Value = {r:.4f}, }},
                TopLeftGreen = Input {{ Value = {g:.4f}, }},
                TopLeftBlue  = Input {{ Value = {b:.4f}, }},
                TopLeftAlpha = Input {{ Value = {a:.4f}, }},
                EffectMask   = Input {{ SourceOp = "BoxMask", Source = "Mask", }},
                AppearFrames = Input {{ Value = {appear_frames}, }},
            }},
        }},
"""

_BORDER_NODE_TEMPLATE = """
        Border1 = Rectangle {{
            Inputs = {{
                StrokeRed   = Input {{ Value = {r:.4f}, }},
                StrokeGreen = Input {{ Value = {g:.4f}, }},
                StrokeBlue  = Input {{ Value = {b:.4f}, }},
                StrokeWidth = Input {{ Value = {width_px}, }},
                CornerRadius = Input {{ Value = {radius_px}, }},
                AnimationDirection = Input {{ Value = "{animation}", }},
                DrawFrames = Input {{ Value = {draw_frames}, }},
            }},
        }},
"""

_TEXT_NODE_TEMPLATE = """
        TextNode1 = TextPlus {{
            Inputs = {{
                StyledText = Input {{ Value = "{text}", }},
                Font       = Input {{ Value = "{font}", }},
                Style      = Input {{ Value = "{weight}", }},
                Size       = Input {{ Value = {size_px}, }},
                Red        = Input {{ Value = {r:.4f}, }},
                Green      = Input {{ Value = {g:.4f}, }},
                Blue       = Input {{ Value = {b:.4f}, }},
                HorizontalJustification = Input {{ Value = "{align_h}", }},
                VerticalJustification   = Input {{ Value = "{align_v}", }},
                Padding    = Input {{ Value = {padding_px}, }},
                AppearDelayFrames = Input {{ Value = {delay_frames}, }},
                FadeInFrames      = Input {{ Value = {fade_frames}, }},
            }},
        }},
"""
