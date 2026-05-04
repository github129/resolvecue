"""cue エントリーポイント。

DaVinci Resolve の ``Workspace > Scripts > cue`` から呼ばれる。

このファイルを以下に配置する:

    %APPDATA%\\Blackmagic Design\\DaVinci Resolve\\Support\\Fusion\\Scripts\\Comp\\cue.py

同じ場所に ``cue/`` パッケージディレクトリも置くこと。
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path


def _ensure_package_on_path() -> None:
    """Resolve から起動された際に ``cue/`` パッケージを import 可能にする。

    Resolve の ``Comp`` スクリプトディレクトリは sys.path に入っていないことがあるため、
    自身の所在から相対的に追加する。
    """
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))


def main() -> int:
    _ensure_package_on_path()
    try:
        from cue.core.resolve_api import ResolveAPI, ResolveConnectionError
        from cue.ui.main_window import MainWindow
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 1

    try:
        api = ResolveAPI()
    except ResolveConnectionError as e:
        print(f"[cue] {e}")
        return 1

    try:
        MainWindow(api).show()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
