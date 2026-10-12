// 1X2 konsensüsünün üç parçalı şeridi: sitenin tek "imza" öğesi. Renkler bütün sitede aynı anlamı
// taşır (ev · beraberlik · deplasman). Sayılar tabloda durur; şerit dekoratiftir (aria-hidden) ve
// metin taşımaz — check-out'un sayı kuralı yalnız metni okur. Genişlikler SVG özniteliği: CSP
// `style-src 'self'` satır içi stili yasaklar.
import styles from "../styles/site.module.css";

type Triple = { home: number; draw: number; away: number };

const PARTS = ["home", "draw", "away"] as const;
// Öznitelikte kayan nokta gürültüsü olmasın (`55.39999999999999`): üç ondalık yeter.
const round = (value: number): number => Math.round(value * 1000) / 1000;

export function ProbabilityBar({ p }: { p: Triple }) {
  const total = p.home + p.draw + p.away;
  if (!(total > 0)) return null;
  let x = 0;
  const rects = PARTS.map((part) => {
    const width = (p[part] / total) * 100;
    const rect = { part, x: round(x), width: round(width) };
    x += width;
    return rect;
  });
  return (
    <svg
      className={styles.bar}
      viewBox="0 0 100 1"
      width="100%"
      height="10"
      preserveAspectRatio="none"
      aria-hidden="true"
      focusable="false"
    >
      {rects.map((rect) => (
        <rect
          key={rect.part}
          x={rect.x}
          y="0"
          width={rect.width}
          height="1"
          className={styles[rect.part]}
        />
      ))}
    </svg>
  );
}
