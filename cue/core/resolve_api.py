"""DaVinci Resolve Scripting API のラッパー。

設計方針:

- Resolve への接続と各種オブジェクト取得を1箇所に集約する
- 上位コードは ``ResolveAPI`` だけに依存し、テスト時は ``MockResolveAPI`` 等に差し替え可能
- メソッド粒度は「効果単位 (1コマンドで完結する操作)」に切り、Resolve API の癖を内側に閉じ込める
- Resolve API が時々返す ``False`` / ``None`` / 空辞書のばらつきは、ここで例外 or 一貫した戻り値に変換する

参考: ``%PROGRAMDATA%\\Blackmagic Design\\DaVinci Resolve\\Support\\Developer\\Scripting\\README.txt``
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from cue import config


class ResolveConnectionError(RuntimeError):
    """Resolve への接続に失敗したときに送出される。"""


class ResolveAPI:
    """Resolve への薄いラッパー。

    インスタンス化時に Resolve への接続を確立する。失敗時は
    ``ResolveConnectionError`` を送出する。
    """

    def __init__(self, resolve: Any | None = None) -> None:
        """
        Parameters
        ----------
        resolve : 既存の Resolve オブジェクトを注入する場合に渡す。
                  None なら ``DaVinciResolveScript`` 経由で接続を試みる。
        """
        self._resolve = resolve if resolve is not None else _connect_to_resolve()
        if self._resolve is None:
            raise ResolveConnectionError(
                "DaVinci Resolve に接続できませんでした。Resolve が起動しているか確認してください。"
            )

    # ----- 基本オブジェクト取得 -----

    @property
    def resolve(self) -> Any:
        return self._resolve

    @property
    def fusion(self) -> Any:
        return self._resolve.Fusion()

    @property
    def project_manager(self) -> Any:
        return self._resolve.GetProjectManager()

    def get_current_project(self) -> Any:
        project = self.project_manager.GetCurrentProject()
        if project is None:
            raise ResolveConnectionError("カレントプロジェクトが取得できませんでした。")
        return project

    def get_current_timeline(self) -> Any:
        timeline = self.get_current_project().GetCurrentTimeline()
        if timeline is None:
            raise ResolveConnectionError(
                "カレントタイムラインが取得できませんでした。タイムラインを開いてください。"
            )
        return timeline

    def get_media_pool(self) -> Any:
        return self.get_current_project().GetMediaPool()

    # ----- タイムライン情報 -----

    def get_frame_rate(self, timeline: Any) -> float:
        """タイムラインのフレームレート。"""
        # Resolve は文字列で返すことがあるので float に正規化する
        raw = timeline.GetSetting("timelineFrameRate")
        return float(raw) if raw else 24.0

    def get_video_track_count(self, timeline: Any) -> int:
        return int(timeline.GetTrackCount("video"))

    def get_track_name(self, timeline: Any, track_index: int) -> str:
        return timeline.GetTrackName("video", track_index) or ""

    def set_track_name(self, timeline: Any, track_index: int, name: str) -> bool:
        return bool(timeline.SetTrackName("video", track_index, name))

    def add_video_track(self, timeline: Any) -> int:
        """ビデオトラックを末尾に追加し、新しいインデックスを返す。"""
        before = self.get_video_track_count(timeline)
        ok = timeline.AddTrack("video")
        if not ok:
            raise RuntimeError("ビデオトラックの追加に失敗しました。")
        return before + 1

    def ensure_track(self, timeline: Any, track_index: int) -> int:
        """指定インデックスまでビデオトラックを増やす。最終インデックスを返す。"""
        while self.get_video_track_count(timeline) < track_index:
            self.add_video_track(timeline)
        return track_index

    def ensure_preview_track(self, timeline: Any) -> int:
        """プレビュー専用トラックを確保し、そのインデックスを返す。

        既に ``cue_preview`` 名のトラックがあればそれを再利用する。
        無ければ ``PREVIEW_TRACK_INDEX`` まで増やしてリネームする。
        """
        count = self.get_video_track_count(timeline)
        for i in range(1, count + 1):
            if self.get_track_name(timeline, i) == config.PREVIEW_TRACK_NAME:
                return i
        target = max(config.PREVIEW_TRACK_INDEX, count + 1)
        self.ensure_track(timeline, target)
        self.set_track_name(timeline, target, config.PREVIEW_TRACK_NAME)
        return target

    # ----- マーカー -----

    def get_markers(self, timeline: Any) -> dict[int, dict[str, Any]]:
        """``{frame: {color, name, note, duration, customData}}`` の辞書を返す。"""
        return timeline.GetMarkers() or {}

    # ----- メディアプール / 配置 -----

    def import_media(self, file_path: Path | str) -> Any:
        """PNG などをメディアプールに取り込み、MediaPoolItem を返す。"""
        media_pool = self.get_media_pool()
        items = media_pool.ImportMedia([str(file_path)])
        if not items:
            raise RuntimeError(f"メディア取り込みに失敗: {file_path}")
        return items[0]

    def find_clip_by_name(
        self, timeline: Any, clip_name: str, track_index: int
    ) -> Any | None:
        """指定トラック上の同名クリップを返す。なければ None。"""
        items = timeline.GetItemListInTrack("video", track_index) or []
        for item in items:
            if item.GetName() == clip_name:
                return item
        return None

    def remove_clip(self, timeline: Any, clip: Any) -> bool:
        """クリップを削除する。"""
        return bool(timeline.DeleteClips([clip], False))

    def remove_all_clips_in_track(self, timeline: Any, track_index: int) -> int:
        """指定トラックの全クリップを削除し、削除数を返す。"""
        items = timeline.GetItemListInTrack("video", track_index) or []
        if not items:
            return 0
        timeline.DeleteClips(list(items), False)
        return len(items)

    def place_fusion_clip(
        self,
        timeline: Any,
        track_index: int,
        start_frame: int,
        duration_frames: int,
        clip_name: str,
        fusion_settings: str,
    ) -> str:
        """Fusion Composition クリップをタイムラインに配置する。

        実装メモ:
        - Resolve には「空の Fusion Composition クリップ」を生成する直接 API がないため、
          実機では以下の手順を踏む:
            1. メディアプールに ``Fusion Composition`` を新規作成 (``AddItemListToMediaPool`` 等)
            2. ``MediaPool.AppendToTimeline`` でタイムラインへ追加
            3. ``TimelineItem.LoadFusionCompFromFile`` または対応 API で
               ``fusion_settings`` を流し込む
        - 上記は Resolve バージョンによって API 名が変わるため、
          ``effects/arrow.py`` ではこのラッパー越しに呼び出す形にしている。

        Returns
        -------
        配置した TimelineItem の識別子 (Resolve API が返すものをそのまま返す)。
        """
        # NOTE: 実機接続時に最終仕上げが必要。MVP では呼び出し点を統一しておく。
        media_pool = self.get_media_pool()
        comp_item = media_pool.AddTimelineFusionConnection() if hasattr(
            media_pool, "AddTimelineFusionConnection"
        ) else None

        clip_info = {
            "mediaPoolItem": comp_item,
            "startFrame": start_frame,
            "endFrame": start_frame + max(1, duration_frames),
            "trackIndex": track_index,
            "mediaType": 1,  # video
        }
        appended = media_pool.AppendToTimeline([clip_info])
        if not appended:
            raise RuntimeError("Fusion Composition クリップの配置に失敗しました。")
        timeline_item = appended[0]
        timeline_item.SetName(clip_name)

        if hasattr(timeline_item, "LoadFusionCompFromString"):
            timeline_item.LoadFusionCompFromString(fusion_settings)
        elif hasattr(timeline_item, "ImportFusionComp"):
            # フォールバック: 一時ファイルに書き出してインポート
            tmp = config.TEMPLATES_DIR / f"_tmp_{clip_name}.setting"
            tmp.write_text(fusion_settings, encoding="utf-8")
            try:
                timeline_item.ImportFusionComp(str(tmp))
            finally:
                if tmp.exists():
                    tmp.unlink()

        return timeline_item.GetUniqueId() if hasattr(timeline_item, "GetUniqueId") else clip_name


def _connect_to_resolve() -> Any | None:
    """``DaVinciResolveScript`` 経由で Resolve に接続する。"""
    try:
        import DaVinciResolveScript as dvr_script  # type: ignore[import-not-found]
    except ImportError:
        return None
    return dvr_script.scriptapp("Resolve")
