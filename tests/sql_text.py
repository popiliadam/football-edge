"""Migration METNİNİ deyimlere ayıran küçük okuyucu (yalnız test).

Yorumlar (`--`, `/* */`) atılır; `;` yalnız tek tırnak ve dolar tırnağı (`$$`, `$etiket$`) DIŞINDA
ve açık bir `begin atomic … end` gövdesinin dışında deyim sonudur — `do $$ … $$` bloğu ve fonksiyon
gövdesi TEK deyim olarak kalır, içindeki metin deyimle birlikte taranır. Çıktı küçük harf ve tek
boşlukludur: yorumdaki bir örnek kuralı karşılamış ya da çiğnemiş sayılmasın.
"""

from __future__ import annotations

import re

_DOLLAR = re.compile(r"\$[A-Za-z_]*\$")
_ATOMIC = re.compile(r"\bbegin atomic\b")
_ATOMIC_END = re.compile(r"\bend$")


def statements(sql: str) -> list[str]:
    found: list[str] = []
    current: list[str] = []
    index, quote = 0, ""
    while index < len(sql):
        char = sql[index]
        if quote:
            if sql.startswith(quote, index):
                current.append(quote)
                index += len(quote)
                quote = ""
                continue
            current.append(char)
            index += 1
            continue
        if sql.startswith("--", index):
            end = sql.find("\n", index)
            index = len(sql) if end == -1 else end
            continue
        if sql.startswith("/*", index):
            end = sql.find("*/", index)
            index = len(sql) if end == -1 else end + 2
            continue
        tag = _DOLLAR.match(sql, index)
        if tag is not None or char == "'":
            quote = tag.group(0) if tag is not None else "'"
            current.append(quote)
            index += len(quote)
            continue
        if char == ";":
            text = " ".join("".join(current).split()).lower()
            if not (_ATOMIC.search(text) and not _ATOMIC_END.search(text)):
                found.append(text)
                current = []
                index += 1
                continue
        current.append(char)
        index += 1
    tail = " ".join("".join(current).split()).lower()
    return [text for text in (*found, tail) if text]
