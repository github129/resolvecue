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

    また、Resolve は長時間プロセスでモジュールキャッシュ (``sys.modules``) を
    抱え続けるため、開発中にファイルを更新しても再実行時に古いクラス定義が
    再利用されてしまう。``_clear_cue_modules_cache()`` で都度キャッシュを
    パージし、毎回ディスクからフレッシュにロードさせる。
    Resolve loader が ``cue.py`` を ``sys.modules['cue']`` に登録する
    ケースにもこのクリアで対応できる (パッケージ・非パッケージ問わず除去)。
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
    _clear_cue_modules_cache()


def _clear_cue_modules_cache() -> None:
    """``sys.modules`` 内の ``cue`` および ``cue.*`` をすべて除去する。

    Resolve は同一 Python プロセスを使い回すため、開発中にファイルを更新しても
    過去ロード時のクラス/関数定義が再利用される。これによりファイル上で
    シグネチャを変更しても古い ``MainWindow`` が呼び出され
    ``TypeError: ... unexpected keyword argument 'bmd'`` のような症状が出る。

    本関数はパッケージか単発スクリプトかを問わず ``cue`` 名前空間のキャッシュを
    全削除する。次の ``import cue.xxx`` は必ずディスクから再ロードされる。

    現在実行中のランチャー (``cue.py``) 自体は ``sys.modules`` 上の参照を
    削除されてもローカルの関数オブジェクトは生きているので影響しない。
    """
    stale = [
        name for name in list(sys.modules)
        if name == "cue" or name.startswith("cue.")
    ]
    for name in stale:
        del sys.modules[name]


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


_REQUIRED_MAIN_WINDOW_PARAMS = ("api", "bmd", "fusion")
"""``MainWindow.__init__`` に存在するべきパラメータ。古い版を検出する基準。"""


def _diagnose_main_window(main_window_cls: Any) -> str | None:
    """``MainWindow`` がランチャーと整合する定義かを確認。

    シグネチャに ``api`` / ``bmd`` / ``fusion`` 全てが含まれていなければ、
    どのファイルが読まれているかを含む詳細エラー文を返す。整合していれば
    ``None`` を返す。

    主な原因 (どれか) の特定材料になる:
      - sys.path 上に旧 cue/ が残っていて優先解決されている
      - .pyc キャッシュが古い (__pycache__ の削除で解消)
      - 配置ファイルの更新漏れ
    """
    import inspect

    try:
        sig = inspect.signature(main_window_cls.__init__)
    except Exception as e:  # noqa: BLE001
        return f"[cue] MainWindow.__init__ のシグネチャ取得に失敗: {e}"

    actual = set(sig.parameters)
    missing = [p for p in _REQUIRED_MAIN_WINDOW_PARAMS if p not in actual]
    if not missing:
        return None  # 想定通り

    try:
        mw_file = inspect.getfile(main_window_cls)
    except Exception:  # noqa: BLE001
        mw_file = "<unknown>"

    return (
        "[cue] MainWindow が古い定義です (パラメータ不足: "
        + ", ".join(missing) + ")\n"
        f"      シグネチャ : {sig}\n"
        f"      MainWindow : {mw_file}\n"
        "対処手順:\n"
        "  1. 上記 'MainWindow' のファイルを最新版に差し替える\n"
        "     (差し替え済みのつもりなら、別の場所から読まれていないか確認)\n"
        "  2. その親フォルダ内の __pycache__ ディレクトリを削除する\n"
        "     (古い .pyc が優先される場合あり)\n"
        "  3. Resolve を完全に終了 → 再起動 (Python プロセス丸ごと破棄)\n"
        "  4. sys.path 上に旧 cue/ が無いか確認:\n"
        "     Workspace > Console で `import sys; print(sys.path)` を実行"
    )


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

    # ----- 診断: 想定通りの MainWindow が import されているか確認 -----
    # 「ファイルは新版なのに MainWindow が bmd 引数を受け付けない」事象は、
    # sys.path 上に別の cue/ パッケージがある、または Python プロセスの
    # キャッシュに古い定義が残留しているケース。
    # sig が古ければ「どのファイルが読まれているか」を明示してユーザーに伝える。
    diag_err = _diagnose_main_window(MainWindow)
    if diag_err is not None:
        print(diag_err)
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


# Resolve は ``__name__`` を環境ごとに違う値で渡してくるので、基本は無条件に
# main() を呼ぶ。ただし「``import cue`` が ``cue/`` パッケージではなく
# この ``cue.py`` を解決してしまった」場合は ``__name__ == "cue"`` になる。
# その状態で main() を呼ぶと ``from cue.X import ...`` が再び cue.py を import し、
# main() が再帰呼び出しされて RecursionError になる。
# よって ``__name__ == "cue"`` なら main() は走らせず、モジュールとしてだけ振る舞う。
if __name__ != "cue":
    sys.exit(main())
