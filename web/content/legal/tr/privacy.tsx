import styles from "../../../src/styles/site.module.css";

export default function Privacy() {
  return (
    <article>
      <p className={styles.draft}>TASLAK — avukat onayı bekler</p>
      <h2>Hangi verileri topluyoruz</h2>
      <p>Kişisel veri toplamıyoruz. Sitede hesap, form, bülten, yorum ve analitik yoktur.</p>
      <h2>Barındırma</h2>
      <p>
        Site, bir barındırma sağlayıcısı tarafından statik dosyalar olarak sunulur; sağlayıcı
        hizmetini işletmek için teknik erişim kayıtları (ör. IP adresi) tutabilir.
      </p>
      <p>
        [AVUKAT SORUSU] Barındırma sağlayıcısı bizim adımıza veri işleyen mi, yoksa kendi kayıtları
        için ayrı bir veri sorumlusu mu? Sitenin yurt dışından sunulması KVKK anlamında yurt dışına
        aktarım sayılır mı; sayılırsa hangi hukuki dayanak ve aydınlatma gerekir?
      </p>
      <h2>Sağlık verisi</h2>
      <p>Oyuncu sağlık ya da sakatlık bilgisi ve oyuncu düzeyinde hiçbir bilgi yayımlamıyoruz.</p>
      <h2>Yerel depolama</h2>
      <p>
        Tarayıcınız yalnız 18 yaşından büyük olduğunuzu onayladığınızı kaydeden tek bir girdi
        saklar. Bu girdi cihazınızdan çıkmaz.
      </p>
    </article>
  );
}
