import { CONTACT_EMAIL, SITE_NAME } from "../../../site.config.ts";

export default function Terms() {
  return (
    <article>
      <h2>Bu site nedir</h2>
      <p>
        Bu site yalnız bilgi amaçlıdır. Hash zincirli bir defterde kaydettiğimiz bahis sitesi
        fiyatlarından türetilen piyasa konsensüs olasılıklarını gösterir. Defterin satırlarını
        değil, baş hash'lerini yayımlıyoruz. Site bahis kabul etmez, ziyaretçiyi hiçbir bahis
        sitesine yönlendirmez ve bahis işletmecilerine bağlantı içermez.
      </p>
      <h2>Garanti yoktur</h2>
      <p>
        Olasılıklar tahmindir, garanti değildir. Geçmiş performans geleceği göstermez. Bu sitedeki
        hiçbir içerik bahis, finans ya da yatırım tavsiyesi değildir.
      </p>
      <h2>Veri kaynakları</h2>
      <p data-fe-allow="license-negation">
        Verilerimizin lisanslı olduğu, resmî veri olduğu ya da herhangi bir lig, kulüp veya veri
        sağlayıcının resmî ortağı olduğumuz yönünde hiçbir iddiada bulunmuyoruz.
      </p>
      <h2>Yaş</h2>
      <p>Bu site 18 yaşından büyükler içindir.</p>
      <h2>İşletmeci ve iletişim</h2>
      <p>
        Bu site {SITE_NAME} adıyla işletilir. İletişim: {CONTACT_EMAIL}.
      </p>
      <h2>Sorumluluk</h2>
      <p>
        Site olduğu gibi sunulur. Hukukun izin verdiği ölçüde, sitedeki içeriğe dayanılarak verilen
        kararlardan doğan zararlardan sorumlu değiliz. Bu koşullar, kanunen sınırlanamayan
        sorumluluğu sınırlamaz.
      </p>
      <h2>Uygulanacak hukuk ve yetkili mahkeme</h2>
      <p>
        Bu koşullar İngiltere ve Galler hukukuna tabidir; uyuşmazlıklarda İngiltere ve Galler
        mahkemeleri yetkilidir. Siteyi tüketici olarak kullanıyorsanız, yaşadığınız ülkenin zorunlu
        tüketici koruma kuralları ve o ülkede dava açma hakkınız saklıdır.
      </p>
    </article>
  );
}
