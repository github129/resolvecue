"""``cue.utils.png_meta`` の単体テスト。

実際の PNG ファイル (``cue/assets/arrows/arrow_tr.png`` 等) を使い、
ヘッダパースが正しく動くことを確認する。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from cue import config
from cue.utils import png_meta


@pytest.fixture
def any_arrow_png() -> Path:
    """同梱済みの矢印 PNG を 1 つ返す。

    PNG が未配置の環境では ``skip`` する。
    """
    candidates = sorted(config.ARROWS_DIR.glob("arrow_*.png"))
    if not candidates:
        pytest.skip("no arrow PNG asset in cue/assets/arrows/")
    return candidates[0]


def test_read_dimensions_returns_positive_integers(any_arrow_png):
    w, h = png_meta.read_png_dimensions(any_arrow_png)
    assert isinstance(w, int) and isinstance(h, int)
    assert w > 0 and h > 0


def test_read_dimensions_raises_on_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        png_meta.read_png_dimensions(tmp_path / "no_such_file.png")


def test_read_dimensions_rejects_non_png(tmp_path):
    fake = tmp_path / "fake.png"
    fake.write_bytes(b"not a real png file")
    with pytest.raises(png_meta.NotAPngError):
        png_meta.read_png_dimensions(fake)


def test_read_dimensions_synthetic_minimal_png(tmp_path):
    """1x1 の最小 PNG を合成してパースが正しいことを確認。"""
    # 8 byte signature + IHDR chunk
    sig = b"\x89PNG\r\n\x1a\n"
    # IHDR: length(13) + "IHDR" + width(4) + height(4) + bit_depth(1) + color_type(1)
    #       + compression(1) + filter(1) + interlace(1) + crc(4)
    ihdr_data = (
        b"\x00\x00\x00\x0d"   # length = 13
        b"IHDR"
        b"\x00\x00\x00\x10"   # width = 16
        b"\x00\x00\x00\x20"   # height = 32
        b"\x08"               # bit depth
        b"\x06"               # color type (RGBA)
        b"\x00" b"\x00" b"\x00"  # compression / filter / interlace
        b"\x00\x00\x00\x00"   # crc (適当でも read_png_dimensions は検証しない)
    )
    p = tmp_path / "tiny.png"
    p.write_bytes(sig + ihdr_data)
    w, h = png_meta.read_png_dimensions(p)
    assert (w, h) == (16, 32)
