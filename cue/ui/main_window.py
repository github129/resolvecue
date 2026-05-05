"""cue メインウィンドウ。

役割:

1. Resolve に接続してマーカー一覧を取得・表示
2. 色フィルタのチェックボックス群 (実際に使われている色だけ表示)
3. エフェクトタブ (矢印 / 囲み枠) の切り替え
4. 「プレビュー」「全マーカーに適用」のボタン
5. ステータスログ表示
"""
from __future__ import annotations

from typing import Any

from cue.core.markers import collect_used_colors, fetch_markers
from cue.core.resolve_api import ResolveAPI
from cue.core.timeline import clear_preview_track
from cue.effects.arrow import ArrowEffect
from cue.effects.box import BoxEffect
from cue.effects.context import EffectContext
from cue.triggers.marker_trigger import MarkerTrigger
from cue.ui.arrow_panel import ArrowPanel
from cue.ui.box_panel import BoxPanel


WINDOW_ID = "com.cue.MainWindow"
WINDOW_TITLE = "cue - 演出自動化"

EFFECT_ARROW = "arrow"
EFFECT_BOX = "box"


class MainWindow:
    """エントリーポイント ``cue.py`` から呼ばれるメインウィンドウ。"""

    def __init__(
        self,
        api: ResolveAPI,
        bmd: Any,
        fusion: Any,
    ) -> None:
        """
        Parameters
        ----------
        api    : Resolve API ラッパー。
        bmd    : Resolve が exec 時に注入する ``bmd`` モジュール。
                 ``UIDispatcher`` の取得に必要。``import bmd`` は Resolve 環境では
                 失敗するので、エントリーポイント (cue.py) で ``globals()`` から
                 捕まえて渡す。
        fusion : Resolve の Fusion オブジェクト (``bmd.scriptapp("Fusion")``
                 相当)。``UIManager`` の取得元。

        いずれも必須。Resolve 外で起動された場合は cue.py の main() が
        ここに到達する前にエラーで終了させる。
        """
        self.api = api
        self.bmd = bmd
        self.fusion = fusion
        self.ui = fusion.UIManager
        self.dispatcher = bmd.UIDispatcher(self.ui)

        self.arrow_panel = ArrowPanel(fusion=fusion, bmd=bmd)
        self.box_panel = BoxPanel(fusion=fusion, bmd=bmd)
        self.win: Any = None
        self.items: dict[str, Any] = {}

        self._all_markers: list = []
        self._color_checkboxes: dict[str, Any] = {}
        self._current_effect: str = EFFECT_ARROW

    # ----- 起動 -----

    def show(self) -> None:
        self._build()
        self._populate_markers()
        self._wire_events()
        self.win.Show()
        self.dispatcher.RunLoop()
        self.win.Hide()

    # ----- 画面構築 -----

    def _build(self) -> None:
        ui = self.ui
        self.win = self.dispatcher.AddWindow(
            {
                "ID": WINDOW_ID,
                "WindowTitle": WINDOW_TITLE,
                "Geometry": [200, 200, 600, 900],
            },
            ui.VGroup({"Spacing": 8, "Margin": 12}, [
                ui.Label({"Text": WINDOW_TITLE, "Alignment": {"AlignHCenter": True}}),

                # マーカー情報
                ui.HGroup({"Weight": 0}, [
                    ui.Label({"ID": "MarkerSummary", "Text": "マーカー: 0 件"}),
                    ui.Button({"ID": "RefreshBtn", "Text": "再読み込み", "Weight": 0}),
                ]),

                # 色フィルタ
                ui.Label({"Text": "対象マーカー色 (チェックで選択, 複数可)"}),
                ui.VGroup({"ID": "ColorFilterGroup", "Weight": 0, "Spacing": 2}, [
                    ui.Label({"Text": "(マーカーが見つかりません)", "ID": "ColorFilterEmpty"}),
                ]),

                # エフェクトタブ
                ui.HGroup({"Weight": 0, "Spacing": 4}, [
                    ui.Label({"Text": "エフェクト", "Weight": 0}),
                    ui.Button({"ID": "TabArrowBtn", "Text": "矢印",   "Checkable": True, "Checked": True}),
                    ui.Button({"ID": "TabBoxBtn",   "Text": "囲み枠", "Checkable": True}),
                ]),

                # 矢印パネル
                ui.VGroup({"ID": "ArrowSection", "Weight": 0}, [
                    ui.Label({"Text": "─── 矢印設定 ───", "Alignment": {"AlignHCenter": True}}),
                    self.arrow_panel.build(),
                ]),
                # 囲み枠パネル
                ui.VGroup({"ID": "BoxSection", "Weight": 0}, [
                    ui.Label({"Text": "─── 囲み枠設定 ───", "Alignment": {"AlignHCenter": True}}),
                    self.box_panel.build(),
                ]),

                # ステータスログ
                ui.Label({"Text": "ステータス"}),
                ui.TextEdit({
                    "ID": "StatusLog",
                    "ReadOnly": True,
                    "PlaceholderText": "ここに進捗が表示されます…",
                    "Weight": 1,
                }),

                # アクション
                ui.HGroup({"Weight": 0, "Spacing": 8}, [
                    ui.Button({"ID": "PreviewBtn", "Text": "プレビュー (V10 cue_preview)"}),
                    ui.Button({"ID": "ApplyBtn",   "Text": "全マーカーに適用"}),
                ]),
            ]),
        )
        self.items = self.win.GetItems()
        # 起動時は矢印タブを表示
        self._show_section(EFFECT_ARROW)

    # ----- マーカー取得・色フィルタ -----

    def _populate_markers(self) -> None:
        try:
            timeline = self.api.get_current_timeline()
            markers = fetch_markers(self.api, timeline)
        except Exception as e:  # noqa: BLE001
            self._log(f"マーカー取得失敗: {e}")
            self._all_markers = []
            return

        self._all_markers = markers
        self.items["MarkerSummary"].Text = f"マーカー: {len(markers)} 件"

        used_colors = collect_used_colors(markers)
        self._rebuild_color_filter(used_colors)
        self._log(f"マーカー {len(markers)} 件を読み込み。色: {', '.join(used_colors) or '-'}")

    def _rebuild_color_filter(self, colors: list[str]) -> None:
        self._color_checkboxes = {}
        label_text = " / ".join(c for c in colors) if colors else "(マーカーが見つかりません)"
        try:
            self.items["ColorFilterEmpty"].Text = label_text
        except Exception:
            pass

    def _selected_colors(self) -> list[str]:
        return [c for c, cb in self._color_checkboxes.items() if cb.Checked]

    # ----- イベント配線 -----

    def _wire_events(self) -> None:
        win = self.win
        items = self.items

        win.On[WINDOW_ID].Close = lambda ev: self.dispatcher.ExitLoop()

        win.On["RefreshBtn"].Clicked = lambda ev: self._populate_markers()
        win.On["PreviewBtn"].Clicked = lambda ev: self._on_preview()
        win.On["ApplyBtn"].Clicked = lambda ev: self._on_apply_all()

        win.On["TabArrowBtn"].Clicked = lambda ev: self._show_section(EFFECT_ARROW)
        win.On["TabBoxBtn"].Clicked = lambda ev: self._show_section(EFFECT_BOX)

        self.arrow_panel.attach_handlers(items)
        self.box_panel.attach_handlers(items)

    # ----- セクション切り替え -----

    def _show_section(self, effect_name: str) -> None:
        self._current_effect = effect_name
        try:
            self.items["ArrowSection"].Hidden = effect_name != EFFECT_ARROW
            self.items["BoxSection"].Hidden = effect_name != EFFECT_BOX
        except Exception:  # noqa: BLE001 - UIManager 環境差ガード
            pass
        try:
            self.items["TabArrowBtn"].Checked = effect_name == EFFECT_ARROW
            self.items["TabBoxBtn"].Checked = effect_name == EFFECT_BOX
        except Exception:  # noqa: BLE001
            pass

    # ----- アクション -----

    def _build_current_effect(self):
        """現在のタブに応じて Effect インスタンスを作る。"""
        if self._current_effect == EFFECT_BOX:
            return BoxEffect(self.box_panel.collect_params(self.items))
        return ArrowEffect(self.arrow_panel.collect_params(self.items))

    def _on_preview(self) -> None:
        try:
            timeline = self.api.get_current_timeline()
            effect = self._build_current_effect()

            errors = effect.validate()
            if errors:
                self._log("バリデーションエラー:\n" + "\n".join(f" - {e}" for e in errors))
                return

            removed = clear_preview_track(self.api, timeline)
            self._log(f"プレビュー: 既存 {removed} 件をクリア。")

            current_frame = self._get_current_frame(timeline)
            ctx = EffectContext(
                api=self.api,
                timeline=timeline,
                frame_rate=self.api.get_frame_rate(timeline),
                start_frame=current_frame,
                extra={"color": "Preview"},
            )
            result = effect.preview(ctx)
            self._log(f"プレビュー結果: {result.message}")
        except Exception as e:  # noqa: BLE001
            self._log(f"プレビュー失敗: {e}")

    def _on_apply_all(self) -> None:
        try:
            timeline = self.api.get_current_timeline()
            effect = self._build_current_effect()

            errors = effect.validate()
            if errors:
                self._log("バリデーションエラー:\n" + "\n".join(f" - {e}" for e in errors))
                return

            colors = self._selected_colors()
            trigger = MarkerTrigger(self.api, timeline, colors=colors)
            points = trigger.collect()
            if not points:
                self._log("対象マーカーがありません。色を選択してください。")
                return

            self._log(f"対象マーカー: {len(points)} 件 (色: {', '.join(colors) or '全色'})")

            fps = self.api.get_frame_rate(timeline)
            success = 0
            skipped = 0
            failed = 0
            for tp in points:
                ctx = EffectContext(
                    api=self.api,
                    timeline=timeline,
                    frame_rate=fps,
                    start_frame=tp.start_frame,
                    end_frame=tp.end_frame,
                    extra={"color": tp.color, "label": tp.label},
                )
                result = effect.apply(ctx)
                if result.skipped:
                    skipped += 1
                elif result.success:
                    success += 1
                else:
                    failed += 1
                    self._log(f" - 失敗 @frame {tp.start_frame}: {result.message}")

            self._log(f"完了: 配置 {success} / スキップ {skipped} / 失敗 {failed}")
        except Exception as e:  # noqa: BLE001
            self._log(f"適用失敗: {e}")

    # ----- ヘルパ -----

    def _get_current_frame(self, timeline: Any) -> int:
        for attr in ("GetCurrentTimecode",):
            method = getattr(timeline, attr, None)
            if callable(method):
                tc = method()
                if tc:
                    return _timecode_to_frame(tc, self.api.get_frame_rate(timeline))
        start = timeline.GetStartFrame() if hasattr(timeline, "GetStartFrame") else 0
        return int(start or 0)

    def _log(self, message: str) -> None:
        log_widget = self.items.get("StatusLog")
        if log_widget is None:
            return
        existing = log_widget.PlainText if hasattr(log_widget, "PlainText") else ""
        log_widget.PlainText = (existing + "\n" + message) if existing else message


def _timecode_to_frame(tc: str, fps: float) -> int:
    """``HH:MM:SS:FF`` を整数フレームに変換 (drop frame 非対応)。"""
    try:
        hh, mm, ss, ff = (int(p) for p in tc.replace(";", ":").split(":"))
    except ValueError:
        return 0
    return int(round(((hh * 3600 + mm * 60 + ss) * fps) + ff))
