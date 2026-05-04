"""囲み枠 (box) エフェクト用の設定パネル。

矢印パネルと共通する仕組み:
- 用途プリセットを選んだ瞬間に詳細設定を一括上書き (``BoxEffect.apply_preset()``)
- ユーザーが詳細を変更すると ``(カスタム)`` 表示に切り替え
- プリセット側の ``disabled_fields`` に挙がったフィールドは Enabled=False で disable

固有要素:
- 3×3 のテキスト揃えグリッドボタン
- 複数行テキストエリア
- カラーピッカーが UIManager にないため HEX 入力で代替
- フォントは ``utils.fonts.list_system_fonts()`` を「よく使う」+「全フォント」に分類して表示
"""
from __future__ import annotations

from typing import Any

from cue import config
from cue.effects.box import BackgroundConfig, BorderConfig, BoxEffect, BoxParams, TextConfig
from cue.utils import fonts as font_utils


class BoxPanel:
    """囲み枠設定パネル。"""

    CUSTOM_LABEL = "(カスタム)"

    ID = {
        # プリセット
        "preset_combo": "BoxPresetCombo",
        # 配置
        "pos_x": "BoxPosX",
        "pos_y": "BoxPosY",
        "width": "BoxWidth",
        "height": "BoxHeight",
        # 枠線
        "border_enabled": "BoxBorderEnabled",
        "border_color": "BoxBorderColor",
        "border_width": "BoxBorderWidth",
        "border_radius": "BoxBorderRadius",
        "border_animation": "BoxBorderAnimation",
        "border_draw_sec": "BoxBorderDrawSec",
        # 背景
        "bg_fill_type": "BoxBgFillType",
        "bg_color": "BoxBgColor",
        "bg_opacity": "BoxBgOpacity",
        # テキスト
        "text_content": "BoxTextContent",
        "text_color": "BoxTextColor",
        "text_font": "BoxTextFont",
        "text_size": "BoxTextSize",
        "text_weight": "BoxTextWeight",
        "text_padding": "BoxTextPadding",
        "text_appearance": "BoxTextAppearance",
        "text_fade_in": "BoxTextFadeIn",
        # タイミング
        "duration": "BoxDuration",
        "fade_out": "BoxFadeOut",
        # 配置先
        "track": "BoxTrack",
        "overwrite": "BoxOverwrite",
    }

    # 3×3 揃えグリッドのボタン ID と (h, v) のマッピング
    ALIGN_BUTTON_IDS: dict[str, tuple[str, str]] = {
        "BoxAlignTL": ("left",   "top"),
        "BoxAlignTC": ("center", "top"),
        "BoxAlignTR": ("right",  "top"),
        "BoxAlignML": ("left",   "center"),
        "BoxAlignMC": ("center", "center"),
        "BoxAlignMR": ("right",  "center"),
        "BoxAlignBL": ("left",   "bottom"),
        "BoxAlignBC": ("center", "bottom"),
        "BoxAlignBR": ("right",  "bottom"),
    }

    BORDER_ANIM_OPTIONS: tuple[tuple[str, str], ...] = (
        ("cw",   "時計回り"),
        ("ccw", "反時計回り"),
        ("none", "4辺同時"),
    )

    BG_FILL_OPTIONS: tuple[tuple[str, str], ...] = (
        ("transparent", "透過"),
        ("solid",       "単色塗りつぶし"),
    )

    TEXT_WEIGHT_OPTIONS: tuple[str, ...] = ("Regular", "Bold")
    TEXT_APPEARANCE_OPTIONS: tuple[tuple[str, str], ...] = (
        ("after_border", "枠の描画後"),
        ("with_border",  "枠と同時"),
    )

    def __init__(self, ui: Any) -> None:
        self.ui = ui
        self._preset_keys: list[str] = list(BoxEffect.presets().keys())
        self._applying_preset: bool = False
        self._last_preset_key: str = self._preset_keys[0] if self._preset_keys else "plain"
        self._current_align: tuple[str, str] = ("center", "center")
        self._all_fonts: list[str] = []
        self._font_combo_keys: list[str] = []  # ComboBox の index に対応するフォント名

    # ----- レイアウト構築 -----

    def build(self) -> Any:
        ui = self.ui
        return ui.VGroup({"Spacing": 6}, [
            # 用途プリセット (タブ上部)
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "用途プリセット", "Weight": 0.3}),
                ui.ComboBox({"ID": self.ID["preset_combo"], "Weight": 0.7}),
            ]),

            ui.Label({"Text": "─── 詳細設定 ───", "Alignment": {"AlignHCenter": True}}),

            # ----- 配置 -----
            ui.Label({"Text": "▼ 配置 (画面比率 0.0-1.0)"}),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "中心 X", "Weight": 0.25}),
                ui.DoubleSpinBox({
                    "ID": self.ID["pos_x"],
                    "Minimum": 0.0, "Maximum": 1.0,
                    "SingleStep": 0.01, "Decimals": 3,
                    "Value": config.DEFAULT_BOX_POS[0], "Weight": 0.25,
                }),
                ui.Label({"Text": "中心 Y", "Weight": 0.25}),
                ui.DoubleSpinBox({
                    "ID": self.ID["pos_y"],
                    "Minimum": 0.0, "Maximum": 1.0,
                    "SingleStep": 0.01, "Decimals": 3,
                    "Value": config.DEFAULT_BOX_POS[1], "Weight": 0.25,
                }),
            ]),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "幅", "Weight": 0.25}),
                ui.DoubleSpinBox({
                    "ID": self.ID["width"],
                    "Minimum": 0.01, "Maximum": 1.0,
                    "SingleStep": 0.01, "Decimals": 3,
                    "Value": config.DEFAULT_BOX_SIZE[0], "Weight": 0.25,
                }),
                ui.Label({"Text": "高さ", "Weight": 0.25}),
                ui.DoubleSpinBox({
                    "ID": self.ID["height"],
                    "Minimum": 0.01, "Maximum": 1.0,
                    "SingleStep": 0.01, "Decimals": 3,
                    "Value": config.DEFAULT_BOX_SIZE[1], "Weight": 0.25,
                }),
            ]),

            # ----- 枠線 -----
            ui.Label({"Text": "▼ 枠線"}),
            ui.HGroup({"Weight": 0}, [
                ui.CheckBox({
                    "ID": self.ID["border_enabled"], "Text": "枠線を表示",
                    "Checked": True,
                }),
            ]),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "色 (HEX)", "Weight": 0.4}),
                ui.LineEdit({
                    "ID": self.ID["border_color"],
                    "Text": config.DEFAULT_BORDER_COLOR, "Weight": 0.6,
                }),
            ]),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "太さ (px)", "Weight": 0.4}),
                ui.SpinBox({
                    "ID": self.ID["border_width"],
                    "Minimum": 0, "Maximum": 50,
                    "Value": config.DEFAULT_BORDER_WIDTH_PX, "Weight": 0.6,
                }),
            ]),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "角丸 R (px)", "Weight": 0.4}),
                ui.SpinBox({
                    "ID": self.ID["border_radius"],
                    "Minimum": 0, "Maximum": 200,
                    "Value": config.DEFAULT_BORDER_RADIUS_PX, "Weight": 0.6,
                }),
            ]),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "描画アニメ", "Weight": 0.4}),
                ui.ComboBox({"ID": self.ID["border_animation"], "Weight": 0.4}),
                ui.DoubleSpinBox({
                    "ID": self.ID["border_draw_sec"],
                    "Minimum": 0.0, "Maximum": 10.0,
                    "SingleStep": 0.1, "Decimals": 2,
                    "Value": config.DEFAULT_BORDER_DRAW_SEC, "Weight": 0.2,
                }),
            ]),

            # ----- 背景 -----
            ui.Label({"Text": "▼ 背景"}),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "塗りタイプ", "Weight": 0.4}),
                ui.ComboBox({"ID": self.ID["bg_fill_type"], "Weight": 0.6}),
            ]),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "色 (HEX)", "Weight": 0.4}),
                ui.LineEdit({
                    "ID": self.ID["bg_color"],
                    "Text": config.DEFAULT_BG_COLOR, "Weight": 0.6,
                }),
            ]),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "不透明度 (%)", "Weight": 0.4}),
                ui.DoubleSpinBox({
                    "ID": self.ID["bg_opacity"],
                    "Minimum": 0.0, "Maximum": 100.0,
                    "SingleStep": 1.0, "Decimals": 1,
                    "Value": config.DEFAULT_BG_OPACITY_PCT, "Weight": 0.6,
                }),
            ]),

            # ----- テキスト -----
            ui.Label({"Text": "▼ テキスト"}),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "内容", "Weight": 0.2}),
                ui.TextEdit({
                    "ID": self.ID["text_content"],
                    "Text": "",
                    "PlaceholderText": "ここに表示するテキストを入力 (空なら非表示)",
                    "Weight": 0.8,
                    "AcceptRichText": False,
                }),
            ]),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "色 (HEX)", "Weight": 0.4}),
                ui.LineEdit({
                    "ID": self.ID["text_color"],
                    "Text": config.DEFAULT_TEXT_COLOR, "Weight": 0.6,
                }),
            ]),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "フォント", "Weight": 0.3}),
                ui.ComboBox({"ID": self.ID["text_font"], "Weight": 0.7}),
            ]),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "サイズ (px)", "Weight": 0.3}),
                ui.SpinBox({
                    "ID": self.ID["text_size"],
                    "Minimum": 4, "Maximum": 400,
                    "Value": config.DEFAULT_TEXT_SIZE_PX, "Weight": 0.3,
                }),
                ui.Label({"Text": "ウェイト", "Weight": 0.2}),
                ui.ComboBox({"ID": self.ID["text_weight"], "Weight": 0.2}),
            ]),
            ui.Label({"Text": "揃え (3×3 グリッド)"}),
            self._build_align_grid(),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "パディング (px)", "Weight": 0.4}),
                ui.SpinBox({
                    "ID": self.ID["text_padding"],
                    "Minimum": 0, "Maximum": 200,
                    "Value": config.DEFAULT_TEXT_PADDING_PX, "Weight": 0.6,
                }),
            ]),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "出現タイミング", "Weight": 0.4}),
                ui.ComboBox({"ID": self.ID["text_appearance"], "Weight": 0.6}),
            ]),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "テキストフェードイン (秒)", "Weight": 0.6}),
                ui.DoubleSpinBox({
                    "ID": self.ID["text_fade_in"],
                    "Minimum": 0.0, "Maximum": 10.0,
                    "SingleStep": 0.05, "Decimals": 2,
                    "Value": config.DEFAULT_TEXT_FADE_IN_SEC, "Weight": 0.4,
                }),
            ]),

            # ----- タイミング -----
            ui.Label({"Text": "▼ タイミング"}),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "保持 (秒)", "Weight": 0.4}),
                ui.DoubleSpinBox({
                    "ID": self.ID["duration"],
                    "Minimum": 0.1, "Maximum": 60.0,
                    "SingleStep": 0.1, "Decimals": 2,
                    "Value": config.DEFAULT_DURATION_SEC, "Weight": 0.6,
                }),
            ]),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "退場フェード (秒)", "Weight": 0.4}),
                ui.DoubleSpinBox({
                    "ID": self.ID["fade_out"],
                    "Minimum": 0.0, "Maximum": 10.0,
                    "SingleStep": 0.05, "Decimals": 2,
                    "Value": config.DEFAULT_FADE_OUT_SEC, "Weight": 0.6,
                }),
            ]),

            # ----- 配置先 -----
            ui.Label({"Text": "▼ 配置先"}),
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "トラック (V)", "Weight": 0.4}),
                ui.SpinBox({
                    "ID": self.ID["track"],
                    "Minimum": 1, "Maximum": 50,
                    "Value": config.DEFAULT_TARGET_TRACK, "Weight": 0.6,
                }),
            ]),
            ui.HGroup({"Weight": 0}, [
                ui.CheckBox({
                    "ID": self.ID["overwrite"],
                    "Text": "既存配置を上書き",
                    "Checked": False,
                }),
            ]),
        ])

    def _build_align_grid(self) -> Any:
        """3×3 のテキスト揃えグリッドを組む。"""
        ui = self.ui
        rows: list[Any] = []
        labels = [["↖", "↑", "↗"], ["←", "●", "→"], ["↙", "↓", "↘"]]
        ids = [
            ["BoxAlignTL", "BoxAlignTC", "BoxAlignTR"],
            ["BoxAlignML", "BoxAlignMC", "BoxAlignMR"],
            ["BoxAlignBL", "BoxAlignBC", "BoxAlignBR"],
        ]
        for r in range(3):
            cols: list[Any] = []
            for c in range(3):
                cols.append(
                    ui.Button({
                        "ID": ids[r][c], "Text": labels[r][c],
                        "Checkable": True, "Weight": 1,
                    })
                )
            rows.append(ui.HGroup({"Weight": 0, "Spacing": 2}, cols))
        return ui.VGroup({"Weight": 0, "Spacing": 2}, rows)

    # ----- イベント配線 -----

    def attach_handlers(self, items: dict[str, Any]) -> None:
        # 用途プリセット ComboBox
        combo = items[self.ID["preset_combo"]]
        combo.AddItem(self.CUSTOM_LABEL)
        for key in self._preset_keys:
            combo.AddItem(BoxEffect.preset_label(key))
        if self._preset_keys:
            combo.CurrentIndex = 1  # 最初の実プリセット
            self._last_preset_key = self._preset_keys[0]

        combo.On[self.ID["preset_combo"]].CurrentIndexChanged = (
            lambda ev: self._on_preset_changed(items)
        )

        # 描画アニメ ComboBox
        anim = items[self.ID["border_animation"]]
        for value, label in self.BORDER_ANIM_OPTIONS:
            anim.AddItem(label)
        anim.CurrentIndex = 0

        # 背景塗りタイプ ComboBox
        bg_type = items[self.ID["bg_fill_type"]]
        for value, label in self.BG_FILL_OPTIONS:
            bg_type.AddItem(label)
        bg_type.CurrentIndex = 0

        # フォント ComboBox
        self._populate_fonts(items[self.ID["text_font"]])

        # ウェイト ComboBox
        weight_combo = items[self.ID["text_weight"]]
        for w in self.TEXT_WEIGHT_OPTIONS:
            weight_combo.AddItem(w)
        weight_combo.CurrentIndex = self.TEXT_WEIGHT_OPTIONS.index("Bold")

        # 出現タイミング ComboBox
        appearance_combo = items[self.ID["text_appearance"]]
        for value, label in self.TEXT_APPEARANCE_OPTIONS:
            appearance_combo.AddItem(label)
        appearance_combo.CurrentIndex = 0

        # 3×3 揃えボタン
        for btn_id in self.ALIGN_BUTTON_IDS:
            items[btn_id].On[btn_id].Clicked = (
                lambda ev, _id=btn_id: self._on_align_clicked(items, _id)
            )
        self._update_align_buttons(items)

        # 「カスタム」表示への切り替え
        for field_id in self._custom_trigger_field_ids():
            items[field_id].On[field_id].ValueChanged = (
                lambda ev: self._mark_custom(items)
            )
        # CheckBox / LineEdit / TextEdit / ComboBox にも同様に
        items[self.ID["border_enabled"]].On[self.ID["border_enabled"]].Toggled = (
            lambda ev: self._mark_custom(items)
        )
        items[self.ID["overwrite"]].On[self.ID["overwrite"]].Toggled = (
            lambda ev: self._mark_custom(items)
        )
        for line_edit_id in (
            self.ID["border_color"], self.ID["bg_color"], self.ID["text_color"],
        ):
            items[line_edit_id].On[line_edit_id].TextChanged = (
                lambda ev: self._mark_custom(items)
            )
        items[self.ID["text_content"]].On[self.ID["text_content"]].TextChanged = (
            lambda ev: self._mark_custom(items)
        )
        for combo_id in (
            self.ID["border_animation"], self.ID["bg_fill_type"],
            self.ID["text_weight"], self.ID["text_font"],
            self.ID["text_appearance"],
        ):
            items[combo_id].On[combo_id].CurrentIndexChanged = (
                lambda ev: self._mark_custom(items)
            )

    def _custom_trigger_field_ids(self) -> tuple[str, ...]:
        return (
            self.ID["pos_x"], self.ID["pos_y"], self.ID["width"], self.ID["height"],
            self.ID["border_width"], self.ID["border_radius"], self.ID["border_draw_sec"],
            self.ID["bg_opacity"],
            self.ID["text_size"], self.ID["text_padding"], self.ID["text_fade_in"],
            self.ID["duration"], self.ID["fade_out"], self.ID["track"],
        )

    # ----- プリセット適用 -----

    def _on_preset_changed(self, items: dict[str, Any]) -> None:
        combo = items[self.ID["preset_combo"]]
        idx = combo.CurrentIndex
        if idx <= 0:
            return  # (カスタム)
        preset_idx = idx - 1
        if not (0 <= preset_idx < len(self._preset_keys)):
            return
        key = self._preset_keys[preset_idx]
        self._last_preset_key = key

        # 一旦デフォルトの BoxParams を作り、preset を当ててから UI に書き戻す
        params = BoxParams(preset=key)
        BoxEffect.apply_preset(params, key)

        self._applying_preset = True
        try:
            self._params_to_ui(items, params)
            self._apply_disabled_fields(items, BoxEffect.disabled_fields_for(key))
        finally:
            self._applying_preset = False

    def _params_to_ui(self, items: dict[str, Any], params: BoxParams) -> None:
        """``BoxParams`` の値を UI ウィジェットへ流し込む (プリセット適用時のみ呼ぶ)。"""
        items[self.ID["pos_x"]].Value = float(params.pos_x)
        items[self.ID["pos_y"]].Value = float(params.pos_y)
        items[self.ID["width"]].Value = float(params.width)
        items[self.ID["height"]].Value = float(params.height)
        items[self.ID["duration"]].Value = float(params.duration_sec)
        items[self.ID["fade_out"]].Value = float(params.fade_out_sec)
        items[self.ID["track"]].Value = int(params.track_index)
        items[self.ID["overwrite"]].Checked = bool(params.overwrite_existing)

        b = params.border
        items[self.ID["border_enabled"]].Checked = bool(b.enabled)
        items[self.ID["border_color"]].Text = b.color
        items[self.ID["border_width"]].Value = int(b.width_px)
        items[self.ID["border_radius"]].Value = int(b.radius_px)
        items[self.ID["border_animation"]].CurrentIndex = _index_of(
            self.BORDER_ANIM_OPTIONS, b.animation
        )
        items[self.ID["border_draw_sec"]].Value = float(b.draw_duration_sec)

        bg = params.background
        items[self.ID["bg_fill_type"]].CurrentIndex = _index_of(
            self.BG_FILL_OPTIONS, bg.fill_type
        )
        items[self.ID["bg_color"]].Text = bg.color
        items[self.ID["bg_opacity"]].Value = float(bg.opacity_pct)

        t = params.text
        items[self.ID["text_content"]].PlainText = t.content
        items[self.ID["text_color"]].Text = t.color
        if t.font_family and t.font_family in self._font_combo_keys:
            items[self.ID["text_font"]].CurrentIndex = self._font_combo_keys.index(
                t.font_family
            )
        items[self.ID["text_size"]].Value = int(t.size_px)
        items[self.ID["text_weight"]].CurrentIndex = (
            self.TEXT_WEIGHT_OPTIONS.index(t.weight) if t.weight in self.TEXT_WEIGHT_OPTIONS else 0
        )
        items[self.ID["text_padding"]].Value = int(t.padding_px)
        items[self.ID["text_appearance"]].CurrentIndex = _index_of(
            self.TEXT_APPEARANCE_OPTIONS, t.appearance
        )
        items[self.ID["text_fade_in"]].Value = float(t.fade_in_sec)
        self._current_align = (t.align_h, t.align_v)
        self._update_align_buttons(items)

    def _apply_disabled_fields(
        self, items: dict[str, Any], disabled_fields: list[str]
    ) -> None:
        """``disabled_fields`` (ドット記法) の対応ウィジェットを Enabled=False に。"""
        # ドット記法 → ウィジェット ID のマッピング
        mapping = {
            "border.color":              self.ID["border_color"],
            "border.width_px":           self.ID["border_width"],
            "border.radius_px":          self.ID["border_radius"],
            "border.animation":          self.ID["border_animation"],
            "border.draw_duration_sec":  self.ID["border_draw_sec"],
            "background.color":          self.ID["bg_color"],
            "background.opacity_pct":    self.ID["bg_opacity"],
            "background.fill_type":      self.ID["bg_fill_type"],
            "text.content":              self.ID["text_content"],
            "text.color":                self.ID["text_color"],
            "text.font_family":          self.ID["text_font"],
            "text.size_px":              self.ID["text_size"],
            "text.weight":               self.ID["text_weight"],
            "text.padding_px":           self.ID["text_padding"],
            "text.appearance":           self.ID["text_appearance"],
            "text.fade_in_sec":          self.ID["text_fade_in"],
        }
        # 一旦すべて有効化
        for widget_id in mapping.values():
            try:
                items[widget_id].Enabled = True
            except Exception:  # noqa: BLE001
                pass
        # disabled_fields を無効化
        for dotted in disabled_fields:
            widget_id = mapping.get(dotted)
            if widget_id is None:
                continue
            try:
                items[widget_id].Enabled = False
            except Exception:  # noqa: BLE001
                pass

    # ----- 揃えグリッド -----

    def _on_align_clicked(self, items: dict[str, Any], btn_id: str) -> None:
        h, v = self.ALIGN_BUTTON_IDS[btn_id]
        self._current_align = (h, v)
        self._update_align_buttons(items)
        self._mark_custom(items)

    def _update_align_buttons(self, items: dict[str, Any]) -> None:
        for btn_id, (h, v) in self.ALIGN_BUTTON_IDS.items():
            items[btn_id].Checked = (h, v) == self._current_align

    # ----- 「カスタム」表示 -----

    def _mark_custom(self, items: dict[str, Any]) -> None:
        if self._applying_preset:
            return
        items[self.ID["preset_combo"]].CurrentIndex = 0  # (カスタム)

    # ----- フォント -----

    def _populate_fonts(self, combo: Any) -> None:
        all_fonts = font_utils.list_system_fonts()
        self._all_fonts = all_fonts
        rec, others = font_utils.categorize_fonts(all_fonts)
        # 表示順: 「[よく使う]」見出し → rec → 「[全フォント]」見出し → others
        # 見出しは選択不可だが UIManager に分類区切り機能はないため、ダミー項目で代替
        self._font_combo_keys = []
        if rec:
            combo.AddItem("[よく使う]")
            self._font_combo_keys.append("")  # ダミー
            for f in rec:
                combo.AddItem(f)
                self._font_combo_keys.append(f)
        combo.AddItem("[全フォント]")
        self._font_combo_keys.append("")
        for f in others:
            combo.AddItem(f)
            self._font_combo_keys.append(f)

        default = font_utils.resolve_default_font(all_fonts)
        if default in self._font_combo_keys:
            combo.CurrentIndex = self._font_combo_keys.index(default)

    # ----- パラメータ取り出し -----

    def collect_params(self, items: dict[str, Any]) -> BoxParams:
        idx = items[self.ID["preset_combo"]].CurrentIndex
        if idx <= 0:
            preset_key = self._last_preset_key
        else:
            preset_idx = idx - 1
            preset_key = (
                self._preset_keys[preset_idx]
                if 0 <= preset_idx < len(self._preset_keys)
                else self._last_preset_key
            )

        font_idx = items[self.ID["text_font"]].CurrentIndex
        font_family = (
            self._font_combo_keys[font_idx]
            if 0 <= font_idx < len(self._font_combo_keys)
            else ""
        )

        params = BoxParams(
            preset=preset_key,
            pos_x=float(items[self.ID["pos_x"]].Value),
            pos_y=float(items[self.ID["pos_y"]].Value),
            width=float(items[self.ID["width"]].Value),
            height=float(items[self.ID["height"]].Value),
            duration_sec=float(items[self.ID["duration"]].Value),
            fade_out_sec=float(items[self.ID["fade_out"]].Value),
            track_index=int(items[self.ID["track"]].Value),
            overwrite_existing=bool(items[self.ID["overwrite"]].Checked),
            border=BorderConfig(
                enabled=bool(items[self.ID["border_enabled"]].Checked),
                color=str(items[self.ID["border_color"]].Text),
                width_px=int(items[self.ID["border_width"]].Value),
                radius_px=int(items[self.ID["border_radius"]].Value),
                animation=self.BORDER_ANIM_OPTIONS[
                    items[self.ID["border_animation"]].CurrentIndex
                ][0],
                draw_duration_sec=float(items[self.ID["border_draw_sec"]].Value),
            ),
            background=BackgroundConfig(
                fill_type=self.BG_FILL_OPTIONS[
                    items[self.ID["bg_fill_type"]].CurrentIndex
                ][0],
                color=str(items[self.ID["bg_color"]].Text),
                opacity_pct=float(items[self.ID["bg_opacity"]].Value),
            ),
            text=TextConfig(
                content=str(items[self.ID["text_content"]].PlainText),
                color=str(items[self.ID["text_color"]].Text),
                font_family=font_family,
                size_px=int(items[self.ID["text_size"]].Value),
                weight=self.TEXT_WEIGHT_OPTIONS[
                    items[self.ID["text_weight"]].CurrentIndex
                ],
                align_h=self._current_align[0],
                align_v=self._current_align[1],
                padding_px=int(items[self.ID["text_padding"]].Value),
                appearance=self.TEXT_APPEARANCE_OPTIONS[
                    items[self.ID["text_appearance"]].CurrentIndex
                ][0],
                fade_in_sec=float(items[self.ID["text_fade_in"]].Value),
            ),
        )
        return params


def _index_of(options: tuple[tuple[str, str], ...], value: str) -> int:
    for i, (v, _label) in enumerate(options):
        if v == value:
            return i
    return 0


