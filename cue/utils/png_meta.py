"""PNG ファイルから幅・高さを stdlib のみで読み出すヘルパ。

Resolve 同梱 Python は PIL / Pillow を持たないことが多いため、
PNG ヘッダ (固定形式) を直接パースする。

参考: https://www.w3.org/TR/PNG/#11IHDR
"""
from __future__ import annotations

from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class NotAPngError(ValueError):
    """ファイルが PNG ではない (シグネチャ不一致) ときに送出。"""


def read_png_dimensions(path: Path | str) -> tuple[int, int]:
    """``path`` の PNG の (width, height) をピクセル単位で返す。

    Raises
    ------
    FileNotFoundError : ファイルが存在しない。
    NotAPngError      : シグネチャが PNG でない。
    """
    p = Path(path)
    with p.open("rb") as f:
        header = f.read(24)
    if len(header) < 24 or header[:8] != PNG_SIGNATURE:
        raise NotAPngError(f"not a PNG file: {p}")
    # IHDR chunk: 8 bytes signature, then 4 bytes length, 4 bytes "IHDR",
    # then 4 bytes width, 4 bytes height (big-endian)
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    return width, height
