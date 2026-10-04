"""Task 12 — dil kalibrasyonu (spec §5.4, açık soru #4).

Jev'in Türkçe ve diğer dillerdeki doğruluğu HİÇ ÖLÇÜLMEMİŞTİ. Mimarinin en global iddiası
— yabancı bahisçilerin yerel-dil haberini geç fiyatladığı — bu ölçülmemiş doğruluğun üstünde
duruyor. Yol haritası ölçmeyi Faz 1'in şartı yapıyor: kötü çıkarsa mimari çöker, o yüzden
karar ölçüm biter bitmez verilir, Faz 1'in sonunda değil.

BU DOSYA HİÇBİR DİLİ ÖLÇMEDİ. Dil başına ~100 elle etiketlenmiş haber gerekir ve etiketler bir
İNSANDAN gelir; etiketleri modele ürettirmek ölçümü ölçülenin kopyası yapar, hiçbir şey kanıtlamaz.
`data/calibration/tr.jsonl` 2026-10-02'den beri İNSAN ONAYLI 100 etiket taşır (başlıksız; başlıklar
gitignored `tr.titles.jsonl`de — bkz. o dizinin README'si). Ücretli ölçüm Plan 2 T3'te; o güne dek
`config/languages.yaml`'da HER dil `production_enabled: false`.

Yanılma YÖNÜ ayrı sayılır: yanlış pozitif (alakasız haberi alakalı sanmak) sinyali
gürültüyle şişirir, yanlış negatif (alakalı haberi kaçırmak) sinyali kaybettirir. Tek bir
doğruluk sayısı ikisini eşitler ve hangisinin olduğu KARARI değiştirir — `CalibrationReport`
bu yüzden ikisini ayrı tutar.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from football_edge.jev import JevClient

RELEVANT = "relevant"
NOT_RELEVANT = "not relevant"

_INSTRUCTIONS = (
    "Does this news headline carry information that affects the named club's NEXT match? "
    "Relevant: squad availability, injuries, suspensions, manager change, motivation, "
    "venue or weather. Not relevant: transfer rumours, reports on past matches, other "
    "clubs, or non-football club news."
)


@dataclass(frozen=True)
class LabelledItem:
    title: str
    language: str
    relevant: bool
    team: str
    url: str = ""
    id: int | None = None


@dataclass(frozen=True)
class CalibrationReport:
    language: str
    n: int
    accuracy: float
    false_positive: int
    false_negative: int
    mean_confidence: float


def _jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return tuple(json.loads(line) for line in lines if line.strip())


def _titles(sidecar: Path) -> dict[int, dict[str, Any]]:
    if not sidecar.exists():
        raise ValueError(
            f"başlıksız etiketler için {sidecar.name} yok ({sidecar}) — başlıklar "
            "depoda değil, gitignored yan dosyada tutulur (K/7/5)"
        )
    return {int(record["id"]): record for record in _jsonl(sidecar)}


def load_labels(path: Path) -> tuple[LabelledItem, ...]:
    """Etiketleri okur. Başlığı olmayan satır (depodaki insan turu: yalnız `id + etiket + kulüp +
    dil`, başlık telifi K/7/5) başlığını `id` ile `<dil>.titles.jsonl` yan dosyasından alır;
    yan dosya ya da id eksikse adıyla reddedilir — başlıksız satır sessizce atlanmaz."""
    records = _jsonl(path)
    needs_titles = any("title" not in record for record in records)
    titles = _titles(path.with_name(f"{path.stem}.titles.jsonl")) if needs_titles else {}
    items: tuple[LabelledItem, ...] = ()
    for record in records:
        if "title" not in record:
            found = titles.get(int(record["id"]))
            if found is None:
                raise ValueError(f"{path.name}: id {record['id']} başlık yan dosyasında yok")
            record = {**record, "title": found["title"], "url": found.get("url", "")}
        items = (*items, LabelledItem(**record))
    return items


def score_language(
    items: tuple[LabelledItem, ...], client: JevClient, *, language: str
) -> CalibrationReport:
    """Jev'in cevaplarını İNSAN etiketleriyle karşılaştırır.

    Yanılma YÖNÜ ayrı sayılır: yanlış pozitif (alakasız haberi alakalı sanmak) sinyali
    gürültüyle şişirir; yanlış negatif (alakalı haberi kaçırmak) sinyali kaybettirir.
    Tek bir doğruluk sayısı ikisini eşitler ve hangisinin olduğu KARARI değiştirir.
    """
    correct = 0
    false_positive = 0
    false_negative = 0
    confidences: list[float] = []
    for entry in items:
        answer = client.ask_choice(
            state={"headline": entry.title, "club": entry.team, "language": entry.language},
            instructions=_INSTRUCTIONS,
            criteria={
                RELEVANT: "The headline affects the club's next match",
                NOT_RELEVANT: "The headline does not affect the club's next match",
            },
        )
        predicted = answer.choice == RELEVANT
        confidences.append(answer.confidence)
        if predicted == entry.relevant:
            correct += 1
        elif predicted:
            false_positive += 1
        else:
            false_negative += 1
    total = len(items)
    return CalibrationReport(
        language=language,
        n=total,
        accuracy=correct / total if total else 0.0,
        false_positive=false_positive,
        false_negative=false_negative,
        mean_confidence=sum(confidences) / len(confidences) if confidences else 0.0,
    )


def production_ready(
    report: CalibrationReport, *, min_n: int = 100, min_accuracy: float = 0.85
) -> tuple[bool, str]:
    """Bir dilin üretime alınabilirliği. Eşikler ÖLÇÜLDÜKTEN sonra ayarlanır, önce değil.

    `min_n` neden var: %100 doğruluk 12 örnekte hiçbir şey kanıtlamaz. `min_accuracy`
    ve `min_n` BAŞLANGIÇ değerleridir, `EloConfig.k`/`home_advantage`nin "fit edilene kadar
    duran iskele" olması gibi — ilk gerçek ölçümden sonra bu dosyada GEREKÇESİYLE
    güncellenir. Uydurulmuş bir eşik, ölçülmüş görünüp aslında seçilmiş olduğu için
    hiç eşik koymamaktan kötüdür; o yüzden bu iki sayı burada AÇIKÇA "başlangıç" diye
    işaretli.
    """
    if report.n < min_n:
        return False, f"{report.language}: {report.n} örnek < {min_n} — ölçüm yetersiz"
    if report.accuracy < min_accuracy:
        return (
            False,
            f"{report.language}: doğruluk {report.accuracy:.2f} < {min_accuracy:.2f} "
            f"(YP={report.false_positive}, YN={report.false_negative})",
        )
    return True, f"{report.language}: doğruluk {report.accuracy:.2f}, n={report.n}"


def write_report(report: CalibrationReport, calibration_dir: Path) -> Path:
    """`<dil>.report.json` yazar, yazılan yolu döner — `calibrate`in tek disk-yazan adımı."""
    path = calibration_dir / f"{report.language}.report.json"
    path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def run_calibration(language: str, calibration_dir: Path, client: JevClient) -> tuple[Path, str]:
    """`<dil>.jsonl`i skorlar, raporu yazar; yazılan yol ve üretime-hazır METNİNİ döner.

    `collect._calibrate_command`in tek işi budur; burada tutulması `collect.py`yi ince bir
    CLI sevk katmanı olarak bırakır (dosya 800 satır sert sınırına yakındı — R50'nin aynı
    gerekçesi: satır bütçesi collect.py'de değil, ilgili modülde harcanır).
    """
    items = load_labels(calibration_dir / f"{language}.jsonl")
    report = score_language(items, client, language=language)
    path = write_report(report, calibration_dir)
    _, reason = production_ready(report)
    return path, reason


def production_languages(languages_path: Path) -> frozenset[str]:
    """Kademe 1 ve 2'nin sorabildiği diller (Plan 2 R178): `production_enabled: true` VE raporu
    `production_ready()`yi (`min_n = 100`, `min_accuracy = 0,85`) geçen. Kapı (`dil-kalibrasyonu`)
    ikisinin ayrışmasını zaten kırmızı yapar; burada yine sorulur ki ayrışmış bir dosya kalibre
    olmayan haberi Jev'e göndermesin."""
    raw = yaml.safe_load(languages_path.read_text(encoding="utf-8"))
    enabled: frozenset[str] = frozenset()
    for entry in raw.get("languages") or ():
        report_path = Path(entry["calibration_report"])
        if not entry["production_enabled"] or not report_path.is_file():
            continue
        report = CalibrationReport(**json.loads(report_path.read_text(encoding="utf-8")))
        if production_ready(report)[0]:
            enabled = enabled | {str(entry["code"])}
    return enabled


def language_config_violations(languages_path: Path) -> tuple[str, ...]:
    """`production_enabled: true` diyen HER dilin GEÇERLİ bir kalibrasyon raporu var mı?

    Ağa çıkmaz, para harcamaz — yalnız dosya sistemini ve `production_ready()`'yi sorar.
    Kapının `dil-kalibrasyonu` adımı BUNU çağırır (`check-languages`), `calibrate`'i DEĞİL
    (Ruling R4): rapor OLMADAN bir dil production_enabled olamaz, kapı bunu her push'ta
    zorlar — `calibrate` para harcar/ağa çıkar, kapı asla onu tetiklemez.

    HİÇBİR dil `production_enabled: true` değilse (bugünkü durum: hepsi false) dönen demet
    BOŞTUR — bu TEMİZ bir sonuçtur, hata değil; `check-languages` bunu "dil kalibrasyonu:
    TEMİZ" diye raporlar ve exit 0 verir.
    """
    raw = yaml.safe_load(languages_path.read_text(encoding="utf-8"))
    violations: tuple[str, ...] = ()
    for entry in raw.get("languages") or ():
        if not entry["production_enabled"]:
            continue
        report_path = Path(entry["calibration_report"])
        if not report_path.is_file():
            violations = (*violations, f"{entry['code']}: production_enabled ama rapor yok")
            continue
        report = CalibrationReport(**json.loads(report_path.read_text(encoding="utf-8")))
        ready, reason = production_ready(report)
        if not ready:
            violations = (*violations, reason)
    return violations
