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
        media_path: Path | str | None = None,
    ) -> str:
        """Fusion Composition クリップをタイムラインに配置する。

        実装フロー:
            1. ``media_path`` の PNG をメディアプールに取り込む
               (``None`` なら ``cue/assets/arrows/`` の最初の PNG を
               プレースホルダとして使う。Fusion comp が完全に上書きする
               箱エフェクト等では中身は何でも OK)
            2. ``MediaPool.AppendToTimeline`` でタイムラインに追加
            3. 一時 ``.setting`` ファイルに ``fusion_settings`` を書き出して
               ``TimelineItem.ImportFusionComp`` でロード

        Resolve API には ``LoadFusionCompFromString`` のような直接読み込み API は
        無いため、temp file 経由が公式パスとなる。

        Parameters
        ----------
        media_path : クリップのソースメディア。矢印では当該 PNG、箱では None
                     (= プレースホルダ PNG)。

        Returns
        -------
        配置した TimelineItem の識別子。
        """
        media_pool = self.get_media_pool()

        # ----- 1. メディア準備 -----
        media_item = self._import_media_or_placeholder(media_pool, media_path)

        # ----- 2. タイムラインへ追加 -----
        self.ensure_track(timeline, track_index)
        end_frame = max(1, duration_frames)
        clip_info = {
            "mediaPoolItem": media_item,
            "startFrame": 0,                    # ソース上の開始フレーム
            "endFrame": end_frame,              # ソース上の終了フレーム (= 表示時間)
            "recordFrame": int(start_frame),    # タイムライン上の配置フレーム
            "trackIndex": int(track_index),
            "mediaType": 1,                     # 1=video
        }
        appended = media_pool.AppendToTimeline([clip_info])
        if not appended:
            raise RuntimeError(
                f"AppendToTimeline に失敗しました (clip_info={clip_info!r})"
            )
        timeline_item = appended[0]
        try:
            timeline_item.SetName(clip_name)
        except Exception:  # noqa: BLE001 - SetName は環境差で失敗することがある
            pass

        # ----- 3. Fusion Composition を適用 -----
        self._apply_fusion_comp(timeline_item, fusion_settings, clip_name)

        try:
            return timeline_item.GetUniqueId()
        except Exception:  # noqa: BLE001
            return clip_name

    def _import_media_or_placeholder(
        self, media_pool: Any, media_path: Path | str | None
    ) -> Any:
        """``media_path`` をメディアプールに取り込む。``None`` ならプレースホルダ。"""
        from cue import config

        if media_path is None:
            arrow_pngs = sorted(config.ARROWS_DIR.glob("arrow_*.png"))
            if not arrow_pngs:
                raise RuntimeError(
                    "プレースホルダ PNG が見つかりません: "
                    f"{config.ARROWS_DIR}\n"
                    "矢印 PNG を1枚以上配置してください。"
                )
            media_path = arrow_pngs[0]
        items = media_pool.ImportMedia([str(media_path)])
        if not items:
            raise RuntimeError(f"ImportMedia に失敗しました: {media_path}")
        return items[0]

    def _apply_fusion_comp(
        self, timeline_item: Any, fusion_settings: str, clip_name: str
    ) -> None:
        """``fusion_settings`` (.setting テキスト) を temp ファイル経由で適用。"""
        import os
        import tempfile

        fd, tmp_path = tempfile.mkstemp(suffix=".setting", prefix=f"cue_{clip_name}_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(fusion_settings)
            if hasattr(timeline_item, "ImportFusionComp"):
                ok = timeline_item.ImportFusionComp(tmp_path)
                if ok is False:
                    raise RuntimeError(
                        f"ImportFusionComp に失敗しました (clip={clip_name})"
                    )
            else:
                raise RuntimeError(
                    "TimelineItem.ImportFusionComp が利用できません "
                    "(Resolve のバージョンを確認してください)"
                )
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def _connect_to_resolve() -> Any | None:
    """``DaVinciResolveScript`` 経由で Resolve に接続する。"""
    try:
        import DaVinciResolveScript as dvr_script  # type: ignore[import-not-found]
    except ImportError:
        return None
    return dvr_script.scriptapp("Resolve")
