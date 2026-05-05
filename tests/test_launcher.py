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
    """``cue.py`` のソースから ``sys.exit(main())`` を除去して exec し、関数を取り出す。"""
    src = LAUNCHER_PATH.read_text(encoding="utf-8")
    # 末尾の sys.exit(main()) を空行に置換 (関数定義だけ評価したい)
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


# ----- sys.modules['cue'] 名前衝突対策 -----


def test_drop_non_package_cue_removes_launcher_module(launcher):
    """Resolve が cue.py を sys.modules['cue'] に登録した状況で、それを除去できる。"""
    import types
    fake_launcher_module = types.ModuleType("cue")
    fake_launcher_module.__file__ = "/somewhere/cue.py"
    # __path__ を持たない = パッケージではない
    assert not hasattr(fake_launcher_module, "__path__")

    saved = sys.modules.get("cue")
    sys.modules["cue"] = fake_launcher_module
    try:
        launcher["_drop_non_package_cue_from_sys_modules"]()
        assert "cue" not in sys.modules
    finally:
        if saved is not None:
            sys.modules["cue"] = saved
        else:
            sys.modules.pop("cue", None)


def test_drop_non_package_cue_keeps_real_package(launcher):
    """sys.modules['cue'] が本物のパッケージ (``__path__`` あり) なら触らない。"""
    import types
    fake_package = types.ModuleType("cue")
    fake_package.__path__ = ["/fake/cue"]  # パッケージマーカー

    saved = sys.modules.get("cue")
    sys.modules["cue"] = fake_package
    try:
        launcher["_drop_non_package_cue_from_sys_modules"]()
        assert sys.modules.get("cue") is fake_package
    finally:
        if saved is not None:
            sys.modules["cue"] = saved
        else:
            sys.modules.pop("cue", None)


def test_drop_non_package_cue_handles_absent_module(launcher):
    """sys.modules['cue'] が無くても例外を出さない。"""
    saved = sys.modules.pop("cue", None)
    try:
        # 例外なく完了することの確認
        launcher["_drop_non_package_cue_from_sys_modules"]()
        assert "cue" not in sys.modules
    finally:
        if saved is not None:
            sys.modules["cue"] = saved


def test_ensure_package_on_path_clears_launcher_module(launcher):
    """``_ensure_package_on_path()`` の中で sys.modules['cue'] のクリーンアップも走る。"""
    import types
    # _locate_package_parent を一時的に固定値返しに差し替え
    original_locate = launcher["_locate_package_parent"]
    launcher["_locate_package_parent"] = lambda: REPO_ROOT
    fake_launcher = types.ModuleType("cue")
    saved = sys.modules.get("cue")
    sys.modules["cue"] = fake_launcher
    try:
        launcher["_ensure_package_on_path"]()
        # 登録されていた non-package が外れている
        assert sys.modules.get("cue") is not fake_launcher
    finally:
        launcher["_locate_package_parent"] = original_locate
        if saved is not None:
            sys.modules["cue"] = saved
        else:
            sys.modules.pop("cue", None)
