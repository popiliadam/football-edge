import styles from "../../../src/styles/site.module.css";

export default function Cookies() {
  return (
    <article>
      <p className={styles.draft}>TASLAK — avukat onayı bekler</p>
      <h2>Çerezler</h2>
      <p>Bu site çerez kullanmaz; analitik ya da reklam izleyicisi yoktur.</p>
      <h2>Zorunlu yerel depolama</h2>
      <p>
        18 yaşından büyük olduğunuzu onayladığınızda tarayıcınız bildirimin tekrar gösterilmemesi
        için <code>fe-age-18</code> girdisini saklar. Tarayıcınızda bu sitenin verilerini silerek
        girdiyi istediğiniz an kaldırabilirsiniz.
      </p>
    </article>
  );
}
