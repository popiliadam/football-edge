import styles from "../../../src/styles/site.module.css";

export default function Terms() {
  return (
    <article>
      <p className={styles.draft}>TASLAK — avukat onayı bekler</p>
      <h2>Bu site nedir</h2>
      <p>
        Bu site yalnız bilgi amaçlıdır. Herkese açık, hash zincirli bir defterde kaydettiğimiz bahis
        sitesi fiyatlarından türetilen piyasa konsensüs olasılıklarını gösterir. Bahis kabul etmez,
        ziyaretçiyi hiçbir bahis sitesine yönlendirmez ve bahis işletmecilerine bağlantı içermez.
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
      <h2>Avukata sorular</h2>
      <p>[AVUKAT SORUSU] Uygulanacak hukuk, yetkili mahkeme ve sorumluluk sınırlaması ifadesi.</p>
    </article>
  );
}
