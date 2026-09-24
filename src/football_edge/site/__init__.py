"""Halka açık sitenin okuma katmanı (Faz 6 İz B, B-1): dışa aktarım ve anlık görüntü sözleşmesi.

DB'ye yalnız bu paket dokunur, yalnız `site_reader` rolüyle ve yalnız `site`, `site_input`,
`site_audit` görünümlerinden (B2, B3). Paketin geçişli import kapanışı holdout'a, tarihsel tabana,
backtest'e ve `live.context`e ulaşamaz (H1f, `tests/test_site_import_rule.py`).
"""
