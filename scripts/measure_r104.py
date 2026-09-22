"""R104 ölçümü (geçici dal): yalnız toplu sayı basar, hücre değeri basmaz."""
from __future__ import annotations
import csv, io, time
from collections import Counter
from pathlib import Path
import httpx
from football_edge.collector import _guarded_get
from football_edge.history.football_data import _decode
from football_edge.sources import load_sources, robots_for

REPO = Path(".")
(source,) = [s for s in load_sources(REPO / "config/sources.yaml") if s.id == "football-data"]
parser = robots_for(source, REPO / "config/robots")
paths = ["/mmz4281/0607/T1.csv", "/mmz4281/0708/F2.csv", "/mmz4281/0708/N1.csv",
         "/mmz4281/0708/P1.csv", "/mmz4281/0708/SP2.csv"]
with httpx.Client() as client:
    for i, path in enumerate(paths):
        if i: time.sleep(3)
        r = _guarded_get(client, source, path, parser, timeout=30)
        text, enc = _decode(r.content)
        rows = [row for row in csv.reader(io.StringIO(text), strict=True)]
        header, body = rows[0], [x for x in rows[1:] if any(c.strip() for c in x)]
        w = len(header)
        header_trailing_empty = len(header) - len([h for h in header if h.strip()])
        bad = [x for x in body if len(x) != w]
        widths = Counter(len(x) for x in bad)
        extra_all_empty_at_end = sum(1 for x in bad if len(x) > w and all(not c.strip() for c in x[w:]))
        short = sum(1 for x in bad if len(x) < w)
        # kısa satırlarda: eksik kısım başlığın sonundaki sütunlar mı ve o sütunlar iyi satırlarda boş mu?
        good = [x for x in body if len(x) == w]
        tail_cols_empty_in_good = {}
        for k in sorted(set(len(x) for x in bad if len(x) < w)):
            cols = range(k, w)
            tail_cols_empty_in_good[k] = sum(1 for g in good if all(not g[c].strip() for c in cols))
        # bozuk satırlar hangi sırada: ardışık bir blok mu?
        idx = [n for n, x in enumerate(body) if len(x) != w]
        block = (idx[0], idx[-1]) if idx else None
        # bozuk satırların son dolu hücresinin indeksi
        last_filled = Counter(max((j for j, c in enumerate(x) if c.strip()), default=-1) for x in bad)
        print(f"{path} enc={enc} header_w={w} header_bos_sonda={header_trailing_empty} satir={len(body)} "
              f"bozuk={len(bad)} genislikler={dict(widths)} fazla_sonda_bos={extra_all_empty_at_end} kisa={short} "
              f"blok={block} ardisik={bool(idx) and idx[-1]-idx[0]+1==len(idx)} son_dolu_idx={dict(last_filled)} "
              f"iyi_satirda_kuyruk_bos={tail_cols_empty_in_good}")
