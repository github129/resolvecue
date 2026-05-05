"""エフェクト適用時のコンテキスト。

Effect.apply() の引数を統一し、トリガー側 (マーカー / クリック / 音声…) から
Effect 側へ必要な情報を疎結合に渡すための DTO。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from cue.core.resolve_api import ResolveAPI


@dataclass
class EffectContext:
    """Effect.apply() に渡される実行時コンテキスト。

    Parameters
    ----------
    api : Resolve API ラッパー。テスト時はモックを差し込む。
    timeline : 操作対象の Resolve Timeline オブジェクト。
    frame_rate : タイムラインのフレームレート (例: 23.976, 29.97, 60.0)。
    start_frame : トリガー発火位置。マーカーならそのフレーム位置。
    end_frame : 持続トリガー (将来の音声検出区間など) で使う終端フレーム。
    canvas_size : タイムラインのレンダリング解像度 (width_px, height_px)。
                  実機未取得時は (1920, 1080)。Fusion テンプレ内では
                  ``UseFrameFormatSettings = 1`` でこの値は上書きされるため、
                  px → 画面比率変換の分母として使う用途が主。
    extra : トリガー固有のメタ情報 (マーカー色や名前など)。
    """

    api: ResolveAPI
    timeline: Any
    frame_rate: float
    start_frame: int
    end_frame: int | None = None
    canvas_size: tuple[int, int] = (1920, 1080)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def color(self) -> str:
        """マーカートリガーの場合の色。無ければ空文字。"""
        return str(self.extra.get("color", ""))
