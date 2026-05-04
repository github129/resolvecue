"""Effect 基底クラスとパラメータ/結果の DTO。

設計方針:

- 各エフェクト (矢印, 囲み枠, 注釈, …) は ``Effect`` を継承する。
- パラメータは ``EffectParams`` を継承した ``@dataclass`` で定義し、
  ``Effect.params_class`` に紐付ける。GUI 側はこれを動的に読み取って
  フォームを生成するため、新しい Effect を追加しても UI コードを書き直さない。
- プリセットは ``presets()`` でクラス単位に提供する (矢印の "右上" など)。
- Resolve への配置は ``apply()`` で行うが、
  「Fusion Composition のテンプレを読み込んでパラメータ差し替え」
  という共通処理は ``build_fusion_settings()`` に切り出している。
  サブクラスは原則 ``build_fusion_settings()`` を実装するだけでよい。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields
from typing import Any, ClassVar, TYPE_CHECKING

from cue import config

if TYPE_CHECKING:
    from cue.effects.context import EffectContext


@dataclass
class EffectParams:
    """全エフェクト共通のパラメータ。

    各エフェクトはこれを継承して固有項目を追加する。
    """

    duration_sec: float = config.DEFAULT_DURATION_SEC
    fade_in_sec: float = config.DEFAULT_FADE_IN_SEC
    fade_out_sec: float = config.DEFAULT_FADE_OUT_SEC
    track_index: int = config.DEFAULT_TARGET_TRACK
    overwrite_existing: bool = False
    """同じトリガー位置に既に同種エフェクトがあれば上書きするか。False ならスキップ。"""

    def to_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass
class EffectResult:
    """エフェクト適用の結果。GUI へのフィードバックや将来の undo 情報の元。"""

    success: bool
    timeline_item_ids: list[str] = field(default_factory=list)
    skipped: bool = False
    """既存があり overwrite=False でスキップした場合 True。"""
    message: str = ""


class Effect(ABC):
    """全エフェクトの基底クラス。

    サブクラスが提供すべきもの:

    1. クラス変数 ``name`` / ``display_name`` / ``params_class``
    2. ``presets()`` (オプション)
    3. ``validate()`` で固有のバリデーション
    4. ``build_fusion_settings()`` で Fusion テンプレ ``.setting`` の読み込みと
       パラメータ差し替えを行い、Fusion Composition 用の文字列 (or ファイルパス) を返す
    """

    # ----- クラスメタデータ -----
    name: ClassVar[str] = ""
    """内部識別子。クリップ命名規約に使う (例: "arrow")。"""

    display_name: ClassVar[str] = ""
    """GUI 表示名 (例: "矢印")。"""

    params_class: ClassVar[type[EffectParams]] = EffectParams
    """このエフェクトが受け取るパラメータの dataclass。"""

    template_filename: ClassVar[str] = ""
    """``cue/assets/templates/`` 配下の Fusion テンプレファイル名 (例: "arrow.setting")。"""

    # ----- インスタンス -----
    def __init__(self, params: EffectParams) -> None:
        if not isinstance(params, self.params_class):
            raise TypeError(
                f"{type(self).__name__} expects {self.params_class.__name__}, "
                f"got {type(params).__name__}"
            )
        self.params = params

    # ----- プリセット (サブクラスでオーバーライド) -----
    @classmethod
    def presets(cls) -> dict[str, dict[str, Any]]:
        """プリセット名 -> パラメータ部分辞書。

        GUI のドロップダウン / ボタンとして表示し、選んだ瞬間に数値入力欄へ反映する。
        """
        return {}

    @classmethod
    def apply_preset(cls, params: EffectParams, preset_name: str) -> EffectParams:
        """プリセットの値を ``params`` に書き込んで返す。

        プリセット定義の構造は2形式をサポートする:

        1. **フラット形式** (矢印など単純なエフェクト):
           ``{"top_right": {"direction": "top_right", "pos_x": 0.8, ...}}``
        2. **メタ付き形式** (箱などプリセットにラベルや disabled_fields を持たせたい場合):
           ``{"plain": {"label": "...", "values": {...}, "disabled_fields": [...]}}``

        ``values`` のキーはドット区切りでネストされたフィールドにアクセスできる
        (例: ``"border.color"``, ``"text.size_px"``)。
        プリセットに無いフィールドは元の値を維持する。
        """
        preset = cls.presets().get(preset_name)
        if preset is None:
            raise KeyError(f"Unknown preset: {preset_name!r}")
        values = preset["values"] if "values" in preset else preset
        for dotted_key, value in values.items():
            _set_nested(params, dotted_key, value)
        return params

    # ----- バリデーション -----
    def validate(self) -> list[str]:
        """エラーメッセージのリスト。空なら適用 OK。

        共通項目だけここで検証し、サブクラスは ``super().validate()`` を呼んだ上で
        固有項目を追加チェックする。
        """
        errors: list[str] = []
        p = self.params
        if p.duration_sec <= 0:
            errors.append("表示時間は 0 より大きい値を指定してください。")
        if p.fade_in_sec < 0 or p.fade_out_sec < 0:
            errors.append("フェード時間は 0 以上で指定してください。")
        if p.fade_in_sec + p.fade_out_sec > p.duration_sec:
            errors.append("フェードイン+フェードアウトが表示時間を超えています。")
        if p.track_index < 1:
            errors.append("トラック番号は 1 以上で指定してください。")
        return errors

    # ----- Fusion Composition 生成 (サブクラスで実装) -----
    @abstractmethod
    def build_fusion_settings(self, context: EffectContext) -> str:
        """Fusion Composition の ``.setting`` 形式テキストを返す。

        テンプレファイル ``cue/assets/templates/<template_filename>`` を読み込み、
        ``params`` と ``context`` の値で置換する。

        Returns
        -------
        Fusion がそのまま受け付けられる ``.setting`` 形式の文字列。
        """
        ...

    # ----- 適用 -----
    def apply(self, context: EffectContext) -> EffectResult:
        """``context`` の位置にエフェクトを配置する。

        共通フロー:

        1. ``validate()`` でパラメータをチェック
        2. クリップ名を組み立てて衝突を検出
        3. ``build_fusion_settings()`` で Fusion 設定を構築
        4. ``ResolveAPI`` 経由でタイムラインに配置
        5. Fusion Composition を貼り付け、パラメータをキーフレーム化

        サブクラスでこれをオーバーライドする必要は通常ない。
        """
        errors = self.validate()
        if errors:
            return EffectResult(success=False, message="; ".join(errors))

        clip_name = config.make_clip_name(
            self.name,
            context.start_frame,
            self._clip_discriminator(context),
        )
        existing = context.api.find_clip_by_name(
            timeline=context.timeline,
            clip_name=clip_name,
            track_index=self.params.track_index,
        )
        if existing is not None:
            if not self.params.overwrite_existing:
                return EffectResult(
                    success=True,
                    skipped=True,
                    message=f"既存の {clip_name} をスキップ。",
                )
            context.api.remove_clip(timeline=context.timeline, clip=existing)

        fusion_settings = self.build_fusion_settings(context)

        item_id = context.api.place_fusion_clip(
            timeline=context.timeline,
            track_index=self.params.track_index,
            start_frame=context.start_frame,
            duration_frames=int(round(self.params.duration_sec * context.frame_rate)),
            clip_name=clip_name,
            fusion_settings=fusion_settings,
        )

        return EffectResult(
            success=True,
            timeline_item_ids=[item_id] if item_id else [],
            message=f"{self.display_name} を {clip_name} として配置。",
        )

    def preview(self, context: EffectContext) -> EffectResult:
        """プレビュー専用トラックに仮配置する。

        デフォルト実装は ``apply()`` と同じだが、トラックインデックスを
        プレビュー用に上書きする。サブクラス側で重い処理を簡略化したい場合のみ
        オーバーライドする。
        """
        original_track = self.params.track_index
        original_overwrite = self.params.overwrite_existing
        try:
            self.params.track_index = context.api.ensure_preview_track(context.timeline)
            self.params.overwrite_existing = True
            return self.apply(context)
        finally:
            self.params.track_index = original_track
            self.params.overwrite_existing = original_overwrite

    # ----- クリップ命名 (サブクラスでオーバーライド) -----
    def _clip_discriminator(self, context: EffectContext) -> str | list[str]:
        """クリップ名末尾に付与するエフェクト固有の識別子を返す。

        - ``str``: 単一スロット (例: 矢印の "tr")
        - ``list[str]``: 複数スロット (例: 箱の ``["plain", "cw"]``)

        空文字 / 空リストを返すと ``cue_<effect>_<frame>`` のみのフラットな名前になる。
        スロット数は ``config.MAX_DISCRIMINATOR_SLOTS`` 以内が望ましい。
        """
        return ""

    # ----- ユーティリティ (サブクラスから利用) -----
    def load_template(self) -> str:
        """``template_filename`` のテンプレを読み込んで文字列で返す。"""
        if not self.template_filename:
            raise ValueError(f"{type(self).__name__}.template_filename is empty.")
        path = config.TEMPLATES_DIR / self.template_filename
        return path.read_text(encoding="utf-8")


def _set_nested(obj: Any, dotted_key: str, value: Any) -> bool:
    """``"a.b.c"`` 形式のキーで ``obj`` のネストされた属性を設定する。

    途中で属性が見つからない場合は何もせず False を返す。dataclass / 通常クラス
    どちらでも使える (setattr で書き込める前提)。
    """
    keys = dotted_key.split(".")
    target = obj
    for key in keys[:-1]:
        if not hasattr(target, key):
            return False
        target = getattr(target, key)
    last = keys[-1]
    if not hasattr(target, last):
        return False
    setattr(target, last, value)
    return True
