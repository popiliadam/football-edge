# Dil kalibrasyon etiketleri

Dil başına ~100 haber başlığı, ELLE etiketlenmiş. Spec §5.4: ölçülmeden hiçbir dil
üretime alınmaz.

Biçim: satır başına bir JSON nesnesi (JSONL).

    {"title": "...", "url": "...", "language": "tr", "team": "Galatasaray", "relevant": true}

- `team` — haberin ilgili olduğu iddia edilen takımın KANONİK adı.
- `relevant` — bu haber GERÇEKTEN o takımın YAKLAŞAN maçını ilgilendiriyor mu?
  `true`: kadro, sakatlık, ceza, hoca, motivasyon, saha/hava.
  `false`: transfer dedikodusu, geçmiş maç özeti, başka takım, kulüp dışı haber.

Etiketleyen kişi bir insandır ve adı `data/calibration/<dil>.meta.json` içine yazılır.
Etiketleri modelin kendisine ürettirmek, ölçümü ölçülenin kopyası yapar — o rapor
hiçbir şey kanıtlamaz.

## `tr.jsonl`'ın BUGÜNKÜ içeriği: BİÇİM ÖRNEĞİ, VERİ DEĞİL

**Aşağıdaki 10 satır İNSAN ETİKETLEME TURUNDAN GEÇMEMİŞTİR.** Task 12'nin operatör kararı
gereği yazıldılar: biçimi (alanlar, en az bir açık `true`, bir açık `false`, bir SINIRDA
vaka) göstermek için, `production_ready()`nin örnek-sayısı tabanını (`min_n=100`) test
edebilmek için değil. Bu satırları etiketleyen bir model (bu görevi uygulayan Claude
oturumu) — spec §5.4'ün yasakladığı TAM olarak "etiketi modele ürettirmek" durumu, o yüzden
bu satırlar GERÇEK kalibrasyon verisi OLARAK ASLA kullanılmamalı ve `calibrate --language
tr` şu an çalıştırılırsa (n=10 < min_n=100) `production_ready()` zaten reddeder — ama
niyet güvenceyi bu otomatik reddə bırakmak değil, açıkça söylemektir.

Gerçek etiketleme turu başladığında bu dosyanın TAMAMI — bu 10 satır dâhil — bir insan
tarafından SIFIRDAN gözden geçirilip ~100 satıra çıkarılır; bu 10 satırın "zaten
etiketlenmiş" sayılıp atlanması YASAKTIR. O turdan sonra etiketleyenin adı
`data/calibration/tr.meta.json`e yazılır — bugün böyle bir dosya YOK, çünkü henüz
gerçek bir etiketleme turu olmadı.

Sınırda vaka (#7): oyuncu sakatlıktan dönüyor ama bugünkü antrenmana yalnızca YARI
temposunda katıldı. Maça yetişip yetişmeyeceği belirsiz — "etkiler" ile "etkilemez"
arasında gerçek bir yargı çağrısı, kolay bir soru değil. Bu satır `relevant: true`
işaretlendi (kısmi katılım hâlâ kadro belirsizliği sinyalidir) ama bu YARGI tartışmaya
açıktır; gerçek etiketleme turunda bir insan bunu FARKLI kararlaştırabilir.

Başlıkları toplamak için (henüz uygulanmadı, bkz. task-12-report.md "concerns"):

    uv run python -m football_edge.collect harvest-labels --language tr --out data/calibration/tr.raw.jsonl

Sonra `relevant` alanlarını elle doldur ve `.jsonl` olarak kaydet.
