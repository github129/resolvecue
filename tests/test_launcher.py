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
