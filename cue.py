"""cue エントリーポイント。

DaVinci Resolve の ``Workspace > Scripts > Utility > cue`` から呼ばれる。

このファイルと ``cue/`` パッケージディレクトリを以下に配置する:

    Windows: %APPDATA%\\Blackmagic Design\\DaVinci Resolve\\Support\\Fusion\\Scripts\\Utility\\
    macOS:   ~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/
    Linux:   ~/.local/share/DaVinciResolve/Fusion/Scripts/Utility/

Resolve は ``Workspace > Scripts`` から起動するときスクリプトを ``exec()`` 系で
読み込むため、通常自動定義される ``__file__`` が未定義になることがある。
``_locate_package_parent()`` がそれを多段フォールバックで解決する。

ユーザー側で配置場所を変えたい場合は環境変数 ``CUE_HOME`` に
``cue/`` パッケージの **親ディレクトリ** のフルパスを設定する。
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path
from typing import Any


CUE_HOME_ENV = "CUE_HOME"
"""環境変数名: ユーザーが ``cue/`` パッケージの親ディレクトリを明示するための上書き。"""


def _ensure_package_on_path() -> None:
    """``cue/`` パッケージを import 可能にするため、その親ディレクトリを ``sys.path`` に挿入する。

    Resolve は ``exec()`` ベースでスクリプトを実行するため ``__file__`` が
    未定義のことがある。複数のフォールバックで自身の所在を特定する。

    また、Resolve は起動時に ``cue.py`` を ``sys.modules['cue']`` として
    登録することがある (Workspace > Scripts のスクリプト loader 実装による)。
    これがあると ``from cue.core import ...`` が「``cue`` is not a package」で
    失敗するため、パッケージ ``cue/`` をロードする前に競合する登録を解除する。
    """
    here = _locate_package_parent()
    if here is None:
        raise RuntimeError(
            "cue パッケージの所在を特定できませんでした。\n"
            "対応策:\n"
            "  1. cue.py と cue/ ディレクトリを Resolve の Scripts/Utility/ に配置する\n"
            "     Windows: %APPDATA%\\Blackmagic Design\\DaVinci Resolve\\Support\\Fusion\\Scripts\\Utility\\\n"
            "  2. または環境変数 CUE_HOME に cue/ パッケージの親ディレクトリの絶対パスを設定する\n"
            f"     例: set {CUE_HOME_ENV}=C:\\path\\to\\resolvecue"
        )
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    _drop_non_package_cue_from_sys_modules()


def _drop_non_package_cue_from_sys_modules() -> None:
    """``sys.modules['cue']`` がパッケージでない (=ランチャー自身) なら除去する。

    Resolve の Script loader は ``cue.py`` を ``sys.modules['cue']`` として
    登録することがあり、後続の ``from cue.core import ...`` がそれを見つけて
    「``cue`` is not a package」で失敗する原因になる。

    パッケージは ``__path__`` 属性を持つ (モジュールは持たない) ので、これで
    両者を判別する。除去後の最初の ``import cue`` は ``cue/__init__.py``
    (= 本来のパッケージ) を解決する。

    ランチャー自身の現在の実行は ``sys.modules`` 上の参照削除では止まらない
    (関数オブジェクト等はローカル参照で生きている) ので影響なし。
    """
    existing = sys.modules.get("cue")
    if existing is not None and not hasattr(existing, "__path__"):
        del sys.modules["cue"]


def _locate_package_parent() -> Path | None:
    """``cue/`` パッケージを含む親ディレクトリを多段フォールバックで特定する。

    Returns
    -------
    見つかった親ディレクトリ (絶対パス)。どの方法でも特定できなければ ``None``。

    探索順:
        1. ``__file__``                           (通常実行時)
        2. ``inspect.currentframe()``             (一部の exec 環境)
        3. ``os.environ[CUE_HOME]``               (ユーザー上書き)
        4. Resolve 標準スクリプトディレクトリ走査  (Utility / Comp / Edit / Tool)
    """
    # 1. __file__: 通常 Python 実行時はこれで OK
    try:
        return Path(__file__).resolve().parent
    except NameError:
        pass

    # 2. inspect: 現在のフレームの code object からファイル名を取る
    #    Resolve が ``exec(compile(src, path, 'exec'))`` ならパスが残る
    try:
        import inspect

        frame = inspect.currentframe()
        if frame is not None:
            filename = frame.f_code.co_filename
            if filename and filename not in ("<string>", "<stdin>"):
                path = Path(filename)
                # exec の filename は絶対でも相対でもありうる
                if not path.is_absolute():
                    path = Path.cwd() / path
                path = path.resolve()
                if path.exists() and path.is_file():
                    return path.parent
    except Exception:  # noqa: BLE001 - フォールバックなので幅広く拾う
        pass

    # 3. 環境変数 CUE_HOME: ユーザーが明示的に指定したパス
    cue_home = os.environ.get(CUE_HOME_ENV)
    if cue_home:
        path = Path(cue_home).expanduser().resolve()
        if _looks_like_cue_parent(path):
            return path

    # 4. Resolve 標準ディレクトリの走査
    for candidate in _resolve_script_dirs():
        if _looks_like_cue_parent(candidate):
            return candidate

    return None


def _looks_like_cue_parent(path: Path) -> bool:
    """``path`` が ``cue/`` パッケージを含む親ディレクトリかを判定する。"""
    return (path / "cue" / "__init__.py").exists()


def _resolve_script_dirs() -> list[Path]:
    """Resolve のユーザー/システム両方のスクリプトディレクトリを返す。

    Workspace > Scripts メニューから起動される標準的な配置場所を網羅する。
    Utility を最優先にしているのは、cue は Comp ベースのエフェクトでも
    タイムライン操作が主体なため Utility 配下に置く運用を推奨しているため。
    """
    candidates: list[Path] = []
    subdirs = ("Utility", "Comp", "Edit", "Tool")

    if sys.platform == "win32":
        # ユーザースコープ
        appdata = os.environ.get("APPDATA")
        if appdata:
            base = (
                Path(appdata)
                / "Blackmagic Design" / "DaVinci Resolve"
                / "Support" / "Fusion" / "Scripts"
            )
            candidates.extend(base / sub for sub in subdirs)
        # システムスコープ
        progdata = os.environ.get("PROGRAMDATA")
        if progdata:
            base = (
                Path(progdata)
                / "Blackmagic Design" / "DaVinci Resolve"
                / "Fusion" / "Scripts"
            )
            candidates.extend(base / sub for sub in subdirs)
    elif sys.platform == "darwin":
        home = Path.home()
        base = (
            home / "Library" / "Application Support"
            / "Blackmagic Design" / "DaVinci Resolve"
            / "Fusion" / "Scripts"
        )
        candidates.extend(base / sub for sub in subdirs)
        # システムスコープ
        sys_base = (
            Path("/Library/Application Support/Blackmagic Design/DaVinci Resolve")
            / "Fusion" / "Scripts"
        )
        candidates.extend(sys_base / sub for sub in subdirs)
    else:
        # Linux
        home = Path.home()
        base = home / ".local" / "share" / "DaVinciResolve" / "Fusion" / "Scripts"
        candidates.extend(base / sub for sub in subdirs)

    return candidates


def _capture_resolve_globals() -> tuple[Any | None, Any | None]:
    """Resolve が exec 時にスクリプトのグローバル名前空間に注入する
    ``bmd`` / ``fusion`` を取得する。

    Resolve が Workspace > Scripts でスクリプトを exec する際、
    ``bmd`` ``fu`` ``fusion`` ``app`` ``resolve`` ``composition`` などの
    変数を実行名前空間に注入する。これは ``import bmd`` のような通常の
    モジュール import では取得できないため、関数の ``__globals__`` 経由で
    捕まえる必要がある。

    Resolve 外 (REPL や pytest 等) では戻り値の両方が ``None`` になる。

    Returns
    -------
    (bmd, fusion) のタプル。取得できなかった方は ``None``。
    """
    g = globals()
    bmd_module = g.get("bmd")
    fusion_obj = g.get("fusion") or g.get("fu")

    # フォールバック1: builtins に注入されているケース
    if bmd_module is None:
        import builtins
        bmd_module = getattr(builtins, "bmd", None)

    # フォールバック2: sys.modules にロードされているケース
    if bmd_module is None:
        bmd_module = sys.modules.get("bmd")

    return bmd_module, fusion_obj


def main() -> int:
    try:
        _ensure_package_on_path()
    except RuntimeError as e:
        print(f"[cue] {e}")
        return 1

    # Resolve 注入グローバルから bmd / fusion を捕獲。
    # この関数の __globals__ は Resolve の exec 名前空間と一致する。
    bmd_module, fusion_obj = _capture_resolve_globals()

    try:
        from cue.core.resolve_api import ResolveAPI, ResolveConnectionError
        from cue.ui.main_window import MainWindow
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 1

    if bmd_module is None:
        print(
            "[cue] bmd モジュールが見つかりません。\n"
            "      cue は DaVinci Resolve の Workspace > Scripts > Utility > cue\n"
            "      から起動する必要があります (通常の python 実行では bmd が\n"
            "      Resolve から注入されないため動きません)。"
        )
        return 1

    try:
        api = ResolveAPI()
    except ResolveConnectionError as e:
        print(f"[cue] {e}")
        return 1

    # Resolve が ``fusion`` をグローバル注入していなくても、Resolve API 経由で
    # 確実に取得できるのでフォールバックする。MainWindow は fusion を必須引数
    # として要求するため、ここで None になっていないことを保証しておく。
    if fusion_obj is None:
        try:
            fusion_obj = api.fusion
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            return 1

    try:
        MainWindow(api, bmd=bmd_module, fusion=fusion_obj).show()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 1
    return 0


# Resolve 経由で exec() される際は ``__name__`` の値が環境次第なので、
# 末尾で無条件に main() を呼ぶ。cue.py はランチャー専用で他からは import されない。
sys.exit(main())
