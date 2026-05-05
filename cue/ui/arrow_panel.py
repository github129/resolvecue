"""矢印エフェクト用の設定パネル。

UIManager の AttributeBlock として組み立てられ、main_window から
GroupBox の中身として配置される。

設計のポイント:

- 8方向プリセットは ``ArrowEffect.presets()`` から動的に生成する
  → 矢印を増やしても UI コードの修正不要
- プリセットを選んだ瞬間に数値入力欄へ自動反映する (ユーザーは数値で微調整可能)
- 詳細設定 (duration / fade / scale / track) は折りたたみ可能なグループに格納
"""
from __future__ import annotations

from typing import Any

from cue import config
from cue.effects.arrow import ArrowEffect, ArrowParams


class ArrowPanel:
    """矢印設定パネル。

    Resolve の UIManager (Fusion UI) を使うため、ID プレフィクスを与えて
    main_window 側のコールバックと衝突しないようにする。
    """

    ID = {
        "preset_combo": "ArrowPresetCombo",
        "scale": "ArrowScale",
        "duration": "ArrowDuration",
        "fade_in": "ArrowFadeIn",
        "fade_out": "ArrowFadeOut",
        "track": "ArrowTrack",
        "pos_x": "ArrowPosX",
        "pos_y": "ArrowPosY",
        "advanced_group": "ArrowAdvancedGroup",
        "overwrite": "ArrowOverwrite",
    }

    CUSTOM_LABEL = "(カスタム)"
    """プリセットを選択した後にユーザーが値を変更したことを示すコンボ表示。"""

    def __init__(self, fusion: Any, bmd: Any) -> None:
        """
        Parameters
        ----------
        fusion : Resolve の Fusion オブジェクト。``UIManager`` の取得元。
        bmd    : Resolve 注入の ``bmd`` モジュール。``UIDispatcher`` 等を
                 サブパネル単独で扱う必要が出た場合のために保持する
                 (現状の MVP では未使用)。
        """
        self.fusion = fusion
        self.bmd = bmd
        self.ui = fusion.UIManager
        self._preset_keys: list[str] = list(ArrowEffect.presets().keys())
        # プリセットを選んでパラメータを書き込んでいる最中の "カスタム" 切り替えを抑止するフラグ
        self._applying_preset: bool = False
        # 「カスタム」表示でも asset 解決のため direction を保持しておく必要がある
        self._last_preset_key: str = self._preset_keys[0] if self._preset_keys else "top_right"

    # ----- レイアウト構築 -----

    def build(self) -> Any:
        """このパネルのレイアウト (UIManager のツリー) を返す。"""
        ui = self.ui
        return ui.VGroup({"Spacing": 6}, [
            # ----- プリセット -----
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "方向プリセット", "Weight": 0.3}),
                ui.ComboBox({
                    "ID": self.ID["preset_combo"],
                    "Weight": 0.7,
                }),
            ]),

            # ----- 詳細設定 (折りたたみ) -----
            ui.VGroup({
                "ID": self.ID["advanced_group"],
                "Weight": 0,
            }, [
                ui.Label({"Text": "詳細設定", "Weight": 0}),

                ui.HGroup({"Weight": 0}, [
                    ui.Label({"Text": "サイズ (倍率)", "Weight": 0.4}),
                    ui.DoubleSpinBox({
                        "ID": self.ID["scale"],
                        "Minimum": 0.1, "Maximum": 5.0,
                        "SingleStep": 0.1, "Decimals": 2,
                        "Value": config.DEFAULT_SCALE,
                        "Weight": 0.6,
                    }),
                ]),

                ui.HGroup({"Weight": 0}, [
                    ui.Label({"Text": "表示時間 (秒)", "Weight": 0.4}),
                    ui.DoubleSpinBox({
                        "ID": self.ID["duration"],
                        "Minimum": 0.1, "Maximum": 60.0,
                        "SingleStep": 0.1, "Decimals": 2,
                        "Value": config.DEFAULT_DURATION_SEC,
                        "Weight": 0.6,
                    }),
                ]),

                ui.HGroup({"Weight": 0}, [
                    ui.Label({"Text": "フェードイン (秒)", "Weight": 0.4}),
                    ui.DoubleSpinBox({
                        "ID": self.ID["fade_in"],
                        "Minimum": 0.0, "Maximum": 10.0,
                        "SingleStep": 0.05, "Decimals": 2,
                        "Value": config.DEFAULT_FADE_IN_SEC,
                        "Weight": 0.6,
                    }),
                ]),

                ui.HGroup({"Weight": 0}, [
                    ui.Label({"Text": "フェードアウト (秒)", "Weight": 0.4}),
                    ui.DoubleSpinBox({
                        "ID": self.ID["fade_out"],
                        "Minimum": 0.0, "Maximum": 10.0,
                        "SingleStep": 0.05, "Decimals": 2,
                        "Value": config.DEFAULT_FADE_OUT_SEC,
                        "Weight": 0.6,
                    }),
                ]),

                ui.HGroup({"Weight": 0}, [
                    ui.Label({"Text": "配置先トラック (V)", "Weight": 0.4}),
                    ui.SpinBox({
                        "ID": self.ID["track"],
                        "Minimum": 1, "Maximum": 50,
                        "Value": config.DEFAULT_TARGET_TRACK,
                        "Weight": 0.6,
                    }),
                ]),

                # 表示位置 (プリセット選択で自動反映、ユーザーは微調整可能)
                ui.HGroup({"Weight": 0}, [
                    ui.Label({"Text": "表示位置 X", "Weight": 0.4}),
                    ui.DoubleSpinBox({
                        "ID": self.ID["pos_x"],
                        "Minimum": 0.0, "Maximum": 1.0,
                        "SingleStep": 0.01, "Decimals": 3,
                        "Value": 0.80,
                        "Weight": 0.6,
                    }),
                ]),
                ui.HGroup({"Weight": 0}, [
                    ui.Label({"Text": "表示位置 Y", "Weight": 0.4}),
                    ui.DoubleSpinBox({
                        "ID": self.ID["pos_y"],
                        "Minimum": 0.0, "Maximum": 1.0,
                        "SingleStep": 0.01, "Decimals": 3,
                        "Value": 0.20,
                        "Weight": 0.6,
                    }),
                ]),

                ui.HGroup({"Weight": 0}, [
                    ui.CheckBox({
                        "ID": self.ID["overwrite"],
                        "Text": "既存配置を上書き",
                        "Checked": False,
                    }),
                ]),
            ]),
        ])

    # ----- イベント配線 -----

    def attach_handlers(self, items: dict[str, Any]) -> None:
        """``main_window`` から呼ばれ、UI 部品が出来上がった後にハンドラを配線する。

        Parameters
        ----------
        items : ``win.GetItems()`` の戻り値辞書。

        プリセット ComboBox の項目構成:
            index 0           : ``(カスタム)``  (実プリセットなし)
            index 1..N        : 各プリセット
        ユーザーが詳細設定を変更すると ComboBox が自動的に index 0 に切り替わる。
        """
        combo = items[self.ID["preset_combo"]]
        combo.AddItem(self.CUSTOM_LABEL)
        for key in self._preset_keys:
            combo.AddItem(ArrowEffect.preset_label(key))
        # 既定は最初の実プリセット (index 1)
        if self._preset_keys:
            combo.CurrentIndex = 1
            self._last_preset_key = self._preset_keys[0]

        def on_preset_changed(ev: dict[str, Any]) -> None:
            idx = combo.CurrentIndex
            if idx <= 0:
                return  # "(カスタム)" は何もしない (表示専用)
            preset_idx = idx - 1
            if not (0 <= preset_idx < len(self._preset_keys)):
                return
            key = self._preset_keys[preset_idx]
            preset = ArrowEffect.presets()[key]
            self._applying_preset = True
            try:
                items[self.ID["pos_x"]].Value = float(preset["pos_x"])
                items[self.ID["pos_y"]].Value = float(preset["pos_y"])
            finally:
                self._applying_preset = False
            self._last_preset_key = key

        combo.On[self.ID["preset_combo"]].CurrentIndexChanged = on_preset_changed

        # 詳細設定の値変更で「カスタム」表示に切り替え
        def on_value_changed(ev: dict[str, Any]) -> None:
            if self._applying_preset:
                return
            combo.CurrentIndex = 0  # (カスタム)

        for field_id in (
            self.ID["scale"], self.ID["duration"], self.ID["fade_in"],
            self.ID["fade_out"], self.ID["track"], self.ID["pos_x"], self.ID["pos_y"],
        ):
            items[field_id].On[field_id].ValueChanged = on_value_changed

    # ----- パラメータ取り出し -----

    def collect_params(self, items: dict[str, Any]) -> ArrowParams:
        """現在の UI 値から ``ArrowParams`` を組み立てる。

        ComboBox が ``(カスタム)`` のときは ``self._last_preset_key`` を direction
        として採用する (= 最後に選ばれたプリセットの PNG アセットを使う)。
        """
        idx = items[self.ID["preset_combo"]].CurrentIndex
        if idx <= 0:
            direction = self._last_preset_key
        else:
            preset_idx = idx - 1
            direction = (
                self._preset_keys[preset_idx]
                if 0 <= preset_idx < len(self._preset_keys)
                else self._last_preset_key
            )
        return ArrowParams(
            direction=direction,
            scale=float(items[self.ID["scale"]].Value),
            duration_sec=float(items[self.ID["duration"]].Value),
            fade_in_sec=float(items[self.ID["fade_in"]].Value),
            fade_out_sec=float(items[self.ID["fade_out"]].Value),
            track_index=int(items[self.ID["track"]].Value),
            pos_x=float(items[self.ID["pos_x"]].Value),
            pos_y=float(items[self.ID["pos_y"]].Value),
            overwrite_existing=bool(items[self.ID["overwrite"]].Checked),
        )
