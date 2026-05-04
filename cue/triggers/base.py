"""Trigger 基底クラス。

「いつ・どこで」エフェクトを発火するかを表現する。

将来の拡張例:
- ``MarkerTrigger``: タイムラインのマーカー (現在の MVP)
- ``ClickTrigger``: 元動画のマウスクリック検出 (将来)
- ``AudioTrigger``: 音量ピーク・無音区間・特定フレーズ検出 (将来)

各 Trigger は ``collect()`` で発火位置のリストを返す。
位置は ``EffectContext`` (の素材) として表現され、Effect 側はそれを受け取って配置する。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TriggerPoint:
    """1つの発火位置を表す。

    ``EffectContext`` を組み立てるときに参照する。
    """

    start_frame: int
    end_frame: int | None = None
    color: str = ""
    """マーカー由来の場合の色。Effect 側でクリップ命名に使う。"""
    label: str = ""
    """マーカー名やラベルなど人間可読の識別子。"""
    extra: dict[str, Any] = field(default_factory=dict)


class Trigger(ABC):
    """発火位置の集合を返す抽象クラス。"""

    name: str = ""
    """トリガー種別の内部識別子 (例: "marker")。"""

    @abstractmethod
    def collect(self) -> list[TriggerPoint]:
        """すべての発火位置を返す。"""
        ...
