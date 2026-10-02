# Dil kalibrasyon etiketleri

Dil başına ~100 haber başlığı, ELLE etiketlenmiş. Spec §5.4: ölçülmeden hiçbir dil
üretime alınmaz.

Biçim: satır başına bir JSON nesnesi (JSONL). Depodaki insan turu BAŞLIKSIZDIR (başlık telifi avukatta,
K/7/5): `{"id": 670, "language": "tr", "team": "Trabzonspor", "relevant": false}`. Başlık ve URL `id` ile
gitignored yan dosyadan gelir: `data/calibration/<dil>.titles.jsonl` → `{"id": 670, "title": "...", "url": "..."}`.
`calibration.load_labels` başlıksız satırı yan dosyasız ya da yan dosyada olmayan `id` ile ADIYLA reddeder.
Başlıklı biçim (`{"title": "...", "url": "...", "language": ..., "team": ..., "relevant": ...}`) testler için
geçerli kalır.

- `team` — haberin ilgili olduğu iddia edilen takımın KANONİK adı.
- `relevant` — bu haber GERÇEKTEN o takımın YAKLAŞAN maçını ilgilendiriyor mu?
  `true`: kadro, sakatlık, ceza, hoca, motivasyon, saha/hava.
  `false`: transfer dedikodusu, geçmiş maç özeti, başka takım, kulüp dışı haber.

Etiketleyen kişi bir insandır; `data/calibration/<dil>.meta.json` içine insan olduğunu gösteren kimliği
(`labeler_kind: human`; ad ZORUNLU DEĞİL — depo public, ör. `insan-1`) yazılır.
Etiketleri modelin kendisine ürettirmek, ölçümü ölçülenin kopyası yapar — o rapor
hiçbir şey kanıtlamaz.

## `tr.jsonl`'ın BUGÜNKÜ içeriği: İNSAN ONAYLI TUR (2026-10-02)

100 madde, **27 `true` / 73 `false`**; ayrıntı `tr.meta.json`. Kaynak: `news_items` (ajansspor, yayın 2026-09-04 →
09-23), tohum `20260923`. Yöntem: model ön-etiketi + AYRI bir ajanın kör 2. geçişi (uyum 94/100, Cohen kappa 0.86) +
insan onayı (kullanıcı oturumu Adım 8): 6 uyuşmazlık (315, 329, 920, 1297, 1314, 1335) `false`, kalan 94 öneri
onaylandı. Zaman yorumu (A): "yaklaşan maç" haberin YAYIMLANDIĞI ana göre (Jev'e tarih gitmez; bugüne göre etiket
Jev'in göremediği bilgiyi ölçerdi ve her gün değişirdi). `team` üretimdeki yazımdır (`matches`, The Odds API —
`features/tier1._state` ile aynı). Eski 10 satırlık BİÇİM ÖRNEĞİ bu turla tamamen değiştirildi; ön-etiket ve
gözden geçirme dosyaları gitignored `.superpowers/sdd/_kalici/kalibrasyon-onay/`dadır.

Ölçüm (ücretli Jev, Plan 2 T3) yerelde koşar: `tr.titles.jsonl` yan dosyası olmadan `load_labels` reddeder.
