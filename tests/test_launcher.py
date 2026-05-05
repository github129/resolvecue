"""``cue.py`` (ランチャー) のパス解決テスト。

Resolve は ``Workspace > Scripts`` メニュー経由でスクリプトを ``exec()`` で
読み込むため ``__file__`` が未定義になることがある。
``_locate_package_parent()`` が多段フォールバックで ``cue/`` パッケージの
親ディレクトリを特定できることを確認する。

このテストは ``cue.py`` を **直接 import せず** (末尾で ``sys.exit(main())``
を呼ぶため)、ファイル内容を読み込んで関数定義部分だけを切り出して評価する。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
LAUNCHER_PATH = REPO_ROOT / "cue.py"


def _load_launcher_namespace() -> dict[str, Any]:
    """``cue.py`` のソースから ``sys.exit(main())`` を除去して exec し、関数を取り出す。

    cue.py 末尾は ``if __name__ != "cue": sys.exit(main())`` の形なので、
    その2行ブロックをまるごと除去する (関数定義だけ評価したい)。
    """
    src = LAUNCHER_PATH.read_text(encoding="utf-8")
    # 末尾の `if __name__ != "cue":\n    sys.exit(main())` ブロックを除去
    src = re.sub(
        r'^if __name__ != "cue":\s*\n\s+sys\.exit\(main\(\)\)\s*$',
        "",
        src,
        flags=re.MULTILINE,
    )
    # 旧形式のフォールバック (リバートされた場合の保険)
    src = re.sub(r"^sys\.exit\(main\(\)\)\s*$", "", src, flags=re.MULTILINE)
    namespace: dict[str, Any] = {"__name__": "cue_launcher_test"}
    exec(compile(src, str(LAUNCHER_PATH), "exec"), namespace)
    return namespace


@pytest.fixture
def launcher() -> dict[str, Any]:
    return _load_launcher_namespace()


def test_locate_via_file_attribute(launcher):
    """通常実行時 (``__file__`` 定義あり) はそのパスから親ディレクトリを返す。"""
    # exec で ``__file__`` が namespace に入っているはずなので、通常パスで解決される
    result = launcher["_locate_package_parent"]()
    assert result == REPO_ROOT


def test_locate_via_cue_home_env(monkeypatch, launcher):
    """``__file__`` が無い状況でも CUE_HOME 環境変数でフォールバックできる。"""
    # __file__ を消す
    if "__file__" in launcher:
        del launcher["__file__"]
    monkeypatch.setenv("CUE_HOME", str(REPO_ROOT))
    result = launcher["_locate_package_parent"]()
    assert result == REPO_ROOT


def test_locate_returns_none_when_all_fallbacks_fail(monkeypatch, launcher):
    """``__file__`` 無し / CUE_HOME 無し / Resolve ディレクトリ無しなら None。"""
    if "__file__" in launcher:
        del launcher["__file__"]
    monkeypatch.delenv("CUE_HOME", raising=False)
    # Resolve 標準ディレクトリ走査も空にする
    monkeypatch.setitem(launcher, "_resolve_script_dirs", lambda: [])
    # inspect フォールバックも 'cue/__init__.py' を含まないパスで失敗するようにする
    # (このテスト環境のフレームファイル名は cue.py パスを返すので、それを潰すには
    # さらに inspect.currentframe() を None 返しにする必要がある)
    import inspect as _inspect
    monkeypatch.setattr(_inspect, "currentframe", lambda: None)

    # CUE_HOME を意図的に存在しない場所へ
    monkeypatch.setenv("CUE_HOME", str(REPO_ROOT / "this_does_not_exist"))
    result = launcher["_locate_package_parent"]()
    assert result is None


def test_looks_like_cue_parent_detects_package(launcher):
    assert launcher["_looks_like_cue_parent"](REPO_ROOT) is True
    assert launcher["_looks_like_cue_parent"](REPO_ROOT / "tests") is False


def test_resolve_script_dirs_not_empty(launcher):
    """少なくとも現在の OS 用の候補が1つ以上返ること (絶対パス)。"""
    dirs = launcher["_resolve_script_dirs"]()
    # Linux 環境でも HOME 配下の候補が出るはず
    assert len(dirs) > 0
    assert all(isinstance(p, Path) for p in dirs)
    assert all(p.is_absolute() for p in dirs)


def test_ensure_package_on_path_inserts_into_sys_path(launcher, monkeypatch):
    """``_ensure_package_on_path()`` 呼び出し後、cue/ 親が sys.path 先頭にある。"""
    saved = list(sys.path)
    try:
        # 現在の sys.path から repo root を一旦消す
        sys.path[:] = [p for p in sys.path if Path(p).resolve() != REPO_ROOT]
        launcher["_ensure_package_on_path"]()
        assert str(REPO_ROOT) in sys.path
    finally:
        sys.path[:] = saved


# ----- bmd / fusion グローバル捕獲 -----


def test_capture_resolve_globals_returns_none_outside_resolve(launcher, monkeypatch):
    """通常の Python 実行では bmd / fusion は注入されないので両方 None。"""
    # 環境を確実に "Resolve なし" にする
    if "bmd" in launcher:
        del launcher["bmd"]
    if "fusion" in launcher:
        del launcher["fusion"]
    if "fu" in launcher:
        del launcher["fu"]
    import builtins
    monkeypatch.delattr(builtins, "bmd", raising=False)
    import sys as _sys
    monkeypatch.delitem(_sys.modules, "bmd", raising=False)

    bmd, fusion = launcher["_capture_resolve_globals"]()
    assert bmd is None
    assert fusion is None


def test_capture_resolve_globals_picks_up_injected_bmd(launcher):
    """Resolve が注入したのを模した状態で、bmd / fusion が取得できる。"""
    sentinel_bmd = object()
    sentinel_fusion = object()
    launcher["bmd"] = sentinel_bmd
    launcher["fusion"] = sentinel_fusion

    bmd, fusion = launcher["_capture_resolve_globals"]()
    assert bmd is sentinel_bmd
    assert fusion is sentinel_fusion


def test_capture_resolve_globals_falls_back_to_fu(launcher):
    """``fusion`` 名で無く ``fu`` 名のグローバルを使うバージョンの Resolve に対応。"""
    launcher.pop("fusion", None)
    sentinel_fu = object()
    launcher["fu"] = sentinel_fu
    launcher["bmd"] = object()

    _, fusion = launcher["_capture_resolve_globals"]()
    assert fusion is sentinel_fu


def test_capture_resolve_globals_uses_builtins_fallback(launcher, monkeypatch):
    """グローバル名前空間に bmd が無くても builtins.bmd があれば拾う。"""
    launcher.pop("bmd", None)
    launcher.pop("fusion", None)
    launcher.pop("fu", None)
    import builtins
    sentinel = object()
    monkeypatch.setattr(builtins, "bmd", sentinel, raising=False)

    bmd, _ = launcher["_capture_resolve_globals"]()
    assert bmd is sentinel


# ----- sys.modules キャッシュクリア (Resolve 長時間プロセス対策) -----


def _saved_cue_modules() -> dict:
    """テスト前後で `cue.*` の sys.modules 状態を退避するヘルパ。"""
    return {k: v for k, v in sys.modules.items() if k == "cue" or k.startswith("cue.")}


def _restore_cue_modules(saved: dict) -> None:
    # 現在登録されている cue.* を一旦消してから元の状態を復元
    for k in list(sys.modules):
        if k == "cue" or k.startswith("cue."):
            del sys.modules[k]
    sys.modules.update(saved)


def test_clear_cache_removes_launcher_module(launcher):
    """Resolve が cue.py を sys.modules['cue'] に登録した状況で、それを除去できる。"""
    import types
    saved = _saved_cue_modules()
    try:
        # 起動シナリオ再現: cue が非パッケージとして登録されている
        for k in list(sys.modules):
            if k == "cue" or k.startswith("cue."):
                del sys.modules[k]
        sys.modules["cue"] = types.ModuleType("cue")
        launcher["_clear_cue_modules_cache"]()
        assert "cue" not in sys.modules
    finally:
        _restore_cue_modules(saved)


def test_clear_cache_removes_real_package_too(launcher):
    """``cue.*`` の停滞キャッシュも全削除される (開発中の差分反映用)。"""
    import types
    saved = _saved_cue_modules()
    try:
        for k in list(sys.modules):
            if k == "cue" or k.startswith("cue."):
                del sys.modules[k]
        # 本物のパッケージらしさで登録 (__path__ あり)
        pkg = types.ModuleType("cue")
        pkg.__path__ = ["/fake/cue"]
        sys.modules["cue"] = pkg
        sys.modules["cue.core"] = types.ModuleType("cue.core")
        sys.modules["cue.ui.main_window"] = types.ModuleType("cue.ui.main_window")

        launcher["_clear_cue_modules_cache"]()

        assert "cue" not in sys.modules
        assert "cue.core" not in sys.modules
        assert "cue.ui.main_window" not in sys.modules
    finally:
        _restore_cue_modules(saved)


def test_clear_cache_handles_absent_modules(launcher):
    """``cue.*`` が一つも登録されていなくても例外を出さない。"""
    saved = _saved_cue_modules()
    try:
        for k in list(sys.modules):
            if k == "cue" or k.startswith("cue."):
                del sys.modules[k]
        launcher["_clear_cue_modules_cache"]()  # 例外なく完了
    finally:
        _restore_cue_modules(saved)


# ----- 強制パッケージロード (Resolve 環境での cue.py / cue/ 名前衝突対策) -----


def test_force_load_cue_package_pins_real_package(launcher):
    """``_force_load_cue_package`` が cue/__init__.py を sys.modules['cue'] に固定する。"""
    saved = _saved_cue_modules()
    try:
        # cue.py が偽のスクリプトとして sys.modules['cue'] に居る状況を作る
        for k in list(sys.modules):
            if k == "cue" or k.startswith("cue."):
                del sys.modules[k]
        import types
        fake_script_module = types.ModuleType("cue")
        fake_script_module.__file__ = "/fake/cue.py"
        # __path__ なし = パッケージではない (これが問題状況)
        sys.modules["cue"] = fake_script_module
        assert not hasattr(sys.modules["cue"], "__path__")

        launcher["_force_load_cue_package"](REPO_ROOT)

        # 上書きされて、本物のパッケージになっている
        assert hasattr(sys.modules["cue"], "__path__")
        assert sys.modules["cue"].__file__.endswith("cue/__init__.py")
    finally:
        _restore_cue_modules(saved)


def test_force_load_cue_package_raises_when_init_missing(launcher, tmp_path):
    """``cue/__init__.py`` が無い場所を渡すと明示エラー。"""
    import pytest as _pytest
    with _pytest.raises(RuntimeError, match="__init__.py が見つかりません"):
        launcher["_force_load_cue_package"](tmp_path)


def test_force_load_cue_package_enables_submodule_imports(launcher):
    """強制ロード後は ``from cue.core.resolve_api import ResolveAPI`` が通ること。"""
    saved = _saved_cue_modules()
    try:
        for k in list(sys.modules):
            if k == "cue" or k.startswith("cue."):
                del sys.modules[k]

        launcher["_force_load_cue_package"](REPO_ROOT)

        # サブモジュール import が成功する (= __path__ がパッケージとして機能している)
        from cue.core.resolve_api import ResolveAPI  # noqa: F401
    finally:
        _restore_cue_modules(saved)


# ----- MainWindow シグネチャ診断 -----


def test_diagnose_main_window_returns_none_for_correct_signature(launcher):
    """正しい (api, bmd, fusion) シグネチャの MainWindow なら診断 OK (None)。"""
    class GoodMainWindow:
        def __init__(self, api, bmd, fusion):
            pass
    assert launcher["_diagnose_main_window"](GoodMainWindow) is None


def test_diagnose_main_window_detects_missing_bmd(launcher):
    """``bmd`` が無い古い MainWindow を検出し、ファイルパスを含むエラー文を返す。"""
    class OldMainWindow:
        def __init__(self, api):  # 旧シグネチャ
            pass
    err = launcher["_diagnose_main_window"](OldMainWindow)
    assert err is not None
    assert "bmd" in err
    assert "対処" in err
    assert "Resolve を完全に終了" in err


def test_diagnose_main_window_detects_missing_fusion(launcher):
    class PartialMainWindow:
        def __init__(self, api, bmd):  # fusion 欠
            pass
    err = launcher["_diagnose_main_window"](PartialMainWindow)
    assert err is not None
    assert "fusion" in err


def test_launcher_skips_main_when_imported_as_cue():
    """``cue.py`` を ``import cue`` で読み込んだ場合 (=__name__ == "cue") は
    main() を実行しないこと (再帰防止)。"""
    src = LAUNCHER_PATH.read_text(encoding="utf-8")
    namespace: dict[str, Any] = {"__name__": "cue"}
    main_called = [False]

    # main 関数は呼ばれてはいけないので、置き換えで監視
    # ただし src には main の定義があるため、その定義後 sys.exit を呼ばせない
    # ように実行前に sys.exit を no-op に差し替える
    real_exit = sys.exit
    sys.exit = lambda c=0: main_called.__setitem__(0, True)
    try:
        exec(compile(src, str(LAUNCHER_PATH), "exec"), namespace)
    finally:
        sys.exit = real_exit

    assert main_called[0] is False, (
        "__name__ == 'cue' のとき main() が呼ばれてはいけない (再帰の原因)"
    )


def test_ensure_package_on_path_calls_clear_cache(launcher):
    """``_ensure_package_on_path()`` 経由でもキャッシュクリアが走る。"""
    import types
    saved = _saved_cue_modules()
    original_locate = launcher["_locate_package_parent"]
    launcher["_locate_package_parent"] = lambda: REPO_ROOT
    try:
        for k in list(sys.modules):
            if k == "cue" or k.startswith("cue."):
                del sys.modules[k]
        sys.modules["cue.ui.main_window"] = types.ModuleType("cue.ui.main_window")

        launcher["_ensure_package_on_path"]()

        assert "cue.ui.main_window" not in sys.modules
    finally:
        launcher["_locate_package_parent"] = original_locate
        _restore_cue_modules(saved)
