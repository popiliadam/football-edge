// DEFERRED 9.7g: kapanışı kaçırılmış maç kuralı — denetçinin KENDİ türetimi (sitenin `src/lib/closing.ts`ini
// içe aktarmaz). `content.closingReason` ve `expect.expectedLabel` ikisi de bunu kullanır.
// Sınır boru hattıyla aynı (`rounds`: tam başlama anında mühür hâlâ olur): başladı = başlama < dışa aktarım.
// Çözülemeyen zaman sessizce "bekleniyor" sayılmaz — denetçi kapalı başarısız olur.
export function closingMissed(commenceTime: string, generatedAt: string): boolean {
  const kickoff = Date.parse(commenceTime);
  const now = Date.parse(generatedAt);
  if (Number.isNaN(kickoff) || Number.isNaN(now)) {
    throw new Error(`çözülemeyen zaman: ${commenceTime} / ${generatedAt}`);
  }
  return kickoff < now;
}
