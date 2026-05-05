"""矢印エフェクト。

8方向 + 中央指しの離散プリセットから1つを選ぶと、
対応する PNG を ``cue/assets/arrows/`` から読み込んで Fusion Composition に流し込む。

Phase 2 で「自由角度」「target_x/y による任意指し先」を有効化する想定。
そのため ``ArrowParams`` には ``target_x/target_y`` をフィールドとして残しているが、
MVP では UI 側で非公開、内部でも参照しない。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, TYPE_CHECKING

from cue import config
from cue.effects.base import Effect, EffectParams
from cue.utils import png_meta, template as template_utils

if TYPE_CHECKING:
    from cue.effects.context import EffectContext


@dataclass
class ArrowParams(EffectParams):
    """矢印エフェクト固有のパラメータ。

    MVP で UI に公開するのは:
    - direction (8方向 + center プリセット名)
    - scale
    - duration_sec, fade_in_sec, fade_out_sec, track_index (基底由来)

    UI 非公開 (Phase 2 で公開予定):
    - target_x, target_y
    - pos_x, pos_y は direction から自動計算され、表示用にミラーされる
    """

    direction: str = "top_right"
    """``config.ARROW_DIRECTIONS`` のキー。"""

    pos_x: float = 0.80
    """矢印の表示位置 (画面横方向 0.0-1.0)。direction プリセットで自動上書き。"""

    pos_y: float = 0.20
    """矢印の表示位置 (画面縦方向 0.0-1.0, 上が 0)。"""

    scale: float = config.DEFAULT_SCALE

    target_x: float = 0.50
    """指し先 (Phase 2 用、MVP では未使用)。"""

    target_y: float = 0.50


class ArrowEffect(Effect):
    """矢印エフェクト本体。"""

    name: ClassVar[str] = "arrow"
    display_name: ClassVar[str] = "矢印"
    params_class: ClassVar[type[EffectParams]] = ArrowParams
    template_filename: ClassVar[str] = "arrow.setting"

    @classmethod
    def presets(cls) -> dict[str, dict[str, Any]]:
        """``config.ARROW_DIRECTIONS`` から GUI 用のプリセット辞書を構築する。"""
        result: dict[str, dict[str, Any]] = {}
        for key, info in config.ARROW_DIRECTIONS.items():
            result[key] = {
                "direction": key,
                "pos_x": info["pos_x"],
                "pos_y": info["pos_y"],
            }
        return result

    @classmethod
    def preset_label(cls, preset_name: str) -> str:
        """GUI 表示用の日本語ラベル ("右上" など)。"""
        info = config.ARROW_DIRECTIONS.get(preset_name)
        return str(info["label"]) if info else preset_name

    def validate(self) -> list[str]:
        errors = super().validate()
        params: ArrowParams = self.params  # type: ignore[assignment]
        if params.direction not in config.ARROW_DIRECTIONS:
            errors.append(f"未知の direction: {params.direction!r}")
        if params.scale <= 0:
            errors.append("矢印のサイズ (scale) は 0 より大きい値を指定してください。")
        for name, value in (("pos_x", params.pos_x), ("pos_y", params.pos_y)):
            if not 0.0 <= value <= 1.0:
                errors.append(f"{name} は 0.0-1.0 の範囲で指定してください。")
        if not self._asset_path().exists():
            errors.append(
                f"矢印素材が見つかりません: {self._asset_path()}. "
                "cue/assets/arrows/ に PNG を配置してください。"
            )
        return errors

    def build_fusion_settings(self, context: EffectContext) -> str:
        """完成版の ``arrow.setting`` プレースホルダを計算値で埋める。

        テンプレが期待するプレースホルダ:
        - **メディア**: ``MEDIA_FORMAT_TYPE``, ``MEDIA_HEIGHT``, ``MEDIA_WIDTH``,
          ``MEDIA_NAME``, ``MEDIA_NUM_FRAMES``, ``ARROW_PNG``
        - **配置**: ``POS_X``, ``POS_Y`` (Fusion 左下原点), ``SCALE``
        - **タイミング**: ``FRAME_START``, ``FRAME_FADE_IN_END``,
          ``FRAME_FADE_OUT_START``, ``FRAME_END``
        """
        params: ArrowParams = self.params  # type: ignore[assignment]
        fps = context.frame_rate

        duration_frames = max(1, int(round(params.duration_sec * fps)))
        fade_in_frames = max(0, int(round(params.fade_in_sec * fps)))
        fade_out_frames = max(0, int(round(params.fade_out_sec * fps)))

        # キーフレームが単調増加になるようクランプ
        frame_start = 0
        frame_fade_in_end = max(frame_start + 1, fade_in_frames)
        frame_fade_out_start = max(
            frame_fade_in_end + 1, duration_frames - fade_out_frames
        )
        frame_end = max(frame_fade_out_start + 1, duration_frames)

        # PNG メタ情報 (失敗したらデフォルト)
        asset_path = self._asset_path()
        try:
            media_w, media_h = png_meta.read_png_dimensions(asset_path)
        except (FileNotFoundError, png_meta.NotAPngError):
            media_w, media_h = 1920, 1080

        mapping = {
            # メディア
            "MEDIA_FORMAT_TYPE": "Picture",
            "MEDIA_NAME":        template_utils.escape_lua_string(asset_path.name),
            "MEDIA_NUM_FRAMES":  1,
            "MEDIA_WIDTH":       media_w,
            "MEDIA_HEIGHT":      media_h,
            "ARROW_PNG":         template_utils.escape_lua_string(
                str(asset_path).replace("\\", "/")
            ),
            # 配置 (Fusion 左下原点)
            "POS_X":             params.pos_x,
            "POS_Y":             1.0 - params.pos_y,
            "SCALE":             params.scale,
            # タイミング
            "FRAME_START":           frame_start,
            "FRAME_FADE_IN_END":     frame_fade_in_end,
            "FRAME_FADE_OUT_START":  frame_fade_out_start,
            "FRAME_END":             frame_end,
        }

        return template_utils.render_template(self.load_template(), mapping)

    def _clip_discriminator(self, context: EffectContext) -> str:
        params: ArrowParams = self.params  # type: ignore[assignment]
        info = config.ARROW_DIRECTIONS.get(params.direction)
        return str(info["abbr"]) if info else ""

    def _asset_path(self):
        params: ArrowParams = self.params  # type: ignore[assignment]
        info = config.ARROW_DIRECTIONS.get(params.direction)
        filename = str(info["asset"]) if info else "arrow_tr.png"
        return config.ARROWS_DIR / filename
