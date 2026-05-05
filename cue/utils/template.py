"""Fusion ``.setting`` テンプレ用の文字列置換ヘルパ。

``{{KEY}}`` 形式のプレースホルダを mapping で置換する。
strict モード (デフォルト) では未解決のプレースホルダが残っていたら
``UnresolvedPlaceholderError`` を送出するため、テンプレと供給値のずれを
早期に検出できる (Fusion で読み込んだ後に「謎の文字列が入った」と気付くより
ずっと早い)。
"""
from __future__ import annotations

import re
from typing import Any


_PLACEHOLDER_RE = re.compile(r"\{\{([A-Z_][A-Z0-9_]*)\}\}")


class UnresolvedPlaceholderError(KeyError):
    """テンプレに mapping で解決できないプレースホルダが残っているときに送出。"""


def render_template(
    template: str,
    mapping: dict[str, Any],
    *,
    strict: bool = True,
) -> str:
    """``{{KEY}}`` を ``mapping[KEY]`` で置換する。

    値は ``format_value()`` を通して文字列化される。

    Parameters
    ----------
    template : 元のテンプレ。
    mapping : ``KEY -> 値`` の辞書。
    strict : True (デフォルト) なら未解決プレースホルダで例外を送出。
             False なら未解決のものはそのまま残す (デバッグ用)。
    """
    missing: list[str] = []

    def _sub(m: re.Match) -> str:
        key = m.group(1)
        if key in mapping:
            return format_value(mapping[key])
        if strict:
            missing.append(key)
        return m.group(0)

    rendered = _PLACEHOLDER_RE.sub(_sub, template)
    if missing:
        unique = sorted(set(missing))
        raise UnresolvedPlaceholderError(
            "unresolved placeholders: " + ", ".join("{{" + k + "}}" for k in unique)
        )
    return rendered


def find_placeholders(template: str) -> list[str]:
    """テンプレに含まれるプレースホルダ名のリスト (重複排除)。"""
    seen: set[str] = set()
    result: list[str] = []
    for m in _PLACEHOLDER_RE.finditer(template):
        key = m.group(1)
        if key not in seen:
            seen.add(key)
            result.append(key)
    return result


def format_value(value: Any) -> str:
    """Python 値を Fusion ``.setting`` に埋められる文字列に整形する。

    - ``bool``      → "1" / "0"  (Fusion は数値ブール)
    - ``int``       → 整数表示
    - ``float``     → 6桁固定小数 (指数表記回避)
    - ``str``       → そのまま (引用符は呼び出し側で付ける前提)
    - その他       → ``str()``
    """
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def escape_lua_string(s: str) -> str:
    """Fusion の文字列リテラル ``"..."`` 内に埋められるよう特殊文字をエスケープ。

    バックスラッシュを最初に処理しないと連鎖エスケープでバグる。
    """
    return (
        s.replace("\\", "\\\\")
         .replace('"', '\\"')
         .replace("\r", "")
         .replace("\n", "\\n")
         .replace("\t", "\\t")
    )
