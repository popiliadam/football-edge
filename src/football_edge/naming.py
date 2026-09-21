from __future__ import annotations

import re
import unicodedata

# Hukuki/kurumsal ekler: eşleşme anahtarına katkısı yok, gürültüsü çok.
#
# KISA EKLERİN HEPSİNDE OPSİYONEL NOKTA VAR (`s\.?k\.?` vb.), YALNIZ "a.ş."de DEĞİL:
# ilk sürüm yalnız `a\.?ş\.?`ye nokta payı tanıyor, `sk|as|fk|fc|cf`i noktasız bırakıyordu.
# Sonuç: "F.K." süzülmüyor ("gaziantep f.k." → suffix eşleşmiyor, sonraki noktalama
# temizliği "f" ve "k"yi AYRI token'a düşürüyor — "gaziantep f k"), oysa "FK" süzülüyor
# ("gaziantep fk" → "gaziantep"). Aynı kısaltmanın noktalı/noktasız hâli farklı anahtar
# üretiyordu — tam da bu modülün var olma sebebi olan sınıf arıza. Ölçüldü (ampirik):
# `normalise_team("Gaziantep F.K.") == normalise_team("gaziantep fk")` düzeltmeden ÖNCE
# False, düzeltmeden SONRA True (bkz. tests/test_collector.py::
# test_normalise_team_strips_legal_suffixes_and_punctuation).
_SUFFIXES = re.compile(
    r"\b(a\.?ş\.?|spor kul(ü|u)b(ü|u)|futbol|s\.?k\.?|a\.?s\.?|f\.?k\.?|f\.?c\.?|c\.?f\.?)\b"
)
_NON_WORD = re.compile(r"[^a-z0-9ğüşıöç ]+")


def normalise_team(name: str) -> str:
    """Kaynaklar arası eşleşme anahtarı: küçük harf, aksan korunur, ek ve noktalama atılır.

    TÜRKÇE'YE ÖZEL VE LOAD-BEARING: Python'da `"I".lower()` `"i"` verir, oysa Türkçe'de
    `I`nın küçüğü `ı`, `İ`nin küçüğü `i`dir. `casefold()` da bunu bilmez. Açık eşleme
    yapılmazsa aynı takım iki kaynakta FARKLI anahtar üretir ve join sessizce boş kalır —
    bu projenin 1 numaralı ölüm sebebi (spec §5.3).

    SONDA `ı` → `i` KATLANIR (review #1, ölçüldü): yukarıdaki İ/I değişimi kaynaklar
    ARASI TUTARLI görünse de kaynaklar KENDİ İÇİNDE tutarsızdır — TFF (windows-1254)
    doğru Türkçe `İstanbulspor` (noktalı büyük İ) yayınlarken FootyStats ASCII
    `Istanbulspor` (noktasız büyük I) yayınlıyor. Yalnız İ→i/I→ı ile bu ikisi FARKLI
    anahtar üretirdi (`istanbulspor` / `ıstanbulspor`) — tam bu fonksiyonun önlemesi
    gereken sınıf arıza, bir adım öteye taşınmış. `ı`/`i` ayrımının kulüp adları
    arasında hiçbir ayırt edici gücü yok; bu yüzden pipeline'ın SONUNDA (ek/noktalama
    temizliğinden SONRA) `ı` `i`ye katlanır ve iki yazım da AYNI anahtarda buluşur.
    Ara adımdaki İ→i değişimi ayrıca gerekli: Python'ın varsayılan `"İ".lower()`'ı tek
    bir `i` DEĞİL, `i` + BİRLEŞTİRİCİ NOKTA (U+0307, 2 kod noktası) üretir ve bu NFC'de
    de tek koda inmez — İ önce açıkça `i`ye çevrilmezse aynı sorun başka bir yoldan geri
    gelir (ölçüldü: `"İ".lower() == "i"` → `False`).

    Task 6 (TFF) ve Task 11 (varlık eşleme) bu TEK fonksiyonu paylaşır. İki kopya tutulursa
    biri diğerinden sessizce ayrışır ve eşleşme anahtarı iki farklı şey olur.
    """
    folded = name.replace("İ", "i").replace("I", "ı").strip().lower()
    folded = unicodedata.normalize("NFC", folded)
    folded = _SUFFIXES.sub(" ", folded)
    folded = _NON_WORD.sub(" ", folded)
    folded = folded.replace("ı", "i")
    return " ".join(folded.split())
