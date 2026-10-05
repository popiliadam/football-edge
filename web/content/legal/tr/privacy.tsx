import { CONTACT_EMAIL, SITE_NAME } from "../../../site.config.ts";

export default function Privacy() {
  return (
    <article>
      <h2>Veri sorumlusu</h2>
      <p>
        Bu sitenin veri sorumlusu {SITE_NAME}'dur. İletişim: {CONTACT_EMAIL}.
      </p>
      <h2>Hangi verileri topluyoruz</h2>
      <p>
        Bu site ziyaretçilerinden kendisi kişisel veri toplamaz. Sitede hesap, form, bülten, yorum
        ve analitik yoktur.
      </p>
      <h2>Barındırma ve erişim kayıtları</h2>
      <p>
        Site, ABD merkezli bir barındırma sağlayıcısı (Netlify) tarafından statik dosyalar olarak
        sunulur. Sağlayıcı hizmetini işletmek ve güvenliğini sağlamak için teknik erişim kayıtları
        (ör. IP adresi, tarayıcı bilgisi, istek zamanı) tutar. Bu kayıtlar kişisel veri sayılabilir.
        Onları sitenin işletilmesi ve güvenliği dışında hiçbir amaçla kullanmayız. Sağlayıcı bu
        kayıtları yurt dışında, ABD dâhil, işleyebilir ve kendi politikasında yazan süre boyunca
        saklar. Hukuki sebep: sitenin işletilmesine ilişkin meşru menfaat (KVKK md. 5/2-f).
      </p>
      <h2>Haber işleme</h2>
      <p>
        Maç öncesi analiz için kamuya açık futbol haberlerinin başlıklarını ve bağlantılarını
        saklıyoruz. Başlıklar oyuncu sakatlıklarından söz edebilir. Analiz için üçüncü taraf bir
        yapay zekâ hizmetine (TypeSafe) gönderilir; bu hizmet onları yurt dışında işleyebilir. Bu
        sitede oyuncu sağlık ya da sakatlık bilgisi ve oyuncu düzeyinde hiçbir bilgi yayımlamıyoruz;
        analiz yalnız takım düzeyinde sayılara dönüştürülür.
      </p>
      <h2>Hakem adları</h2>
      <p>
        Süper Lig maçlarında Türkiye Futbol Federasyonu'nun (TFF) atadığı baş hakemin adını, TFF
        açıkladıktan sonra ve kaynağıyla gösteriyoruz. Bu adı TFF'nin kamuya açık atama
        sayfalarından alıyoruz.
      </p>
      <h2>Yerel depolama</h2>
      <p>
        Tarayıcınız yalnız 18 yaşından büyük olduğunuzu onayladığınızı kaydeden tek bir girdi
        saklar. Bu girdi cihazınızdan çıkmaz.
      </p>
      <h2>Haklarınız</h2>
      <p>
        KVKK md. 11 uyarınca kişisel verinizin işlenip işlenmediğini öğrenme, bilgi isteme,
        düzeltilmesini ya da silinmesini isteme ve işlenmesine itiraz etme haklarına sahipsiniz.
        Başvurularınızı {CONTACT_EMAIL} adresine iletebilirsiniz. Kişisel Verileri Koruma Kurulu'na
        şikâyet hakkınız saklıdır.
      </p>
    </article>
  );
}
