// Adlı HTML varlıkları (T9 yeniden inceleme N1). React derlenmiş HTML'e yalnız `&amp; &lt; &gt; &quot;`
// ve sayısal varlık basar; başka her adlı varlık elle kurcalamadır ve BULGUDUR. Tarayıcının çözdüğü
// hâliyle görülebilsin diye güvenlikle ilgili HTML5 alt kümesi (URL ayraçları, görünmez ve boşluk
// karakterleri) ayrıca çözülür: `/&sol;host` = `//host`, `Pin&ZeroWidthSpace;nacle` = `Pinnacle`.
// Adlar büyük/küçük harfe duyarlıdır (HTML5 gibi).
import { stripScripts } from "../lib/html.ts";

const INVISIBLE = "​";
const NAMED: Record<string, string> = {
  // URL ve sözdizimi karakterleri
  sol: "/",
  bsol: "\\",
  Tab: "\t",
  NewLine: "\n",
  colon: ":",
  period: ".",
  comma: ",",
  quest: "?",
  num: "#",
  excl: "!",
  commat: "@",
  lowbar: "_",
  apos: "'",
  lpar: "(",
  rpar: ")",
  semi: ";",
  equals: "=",
  percnt: "%",
  dollar: "$",
  plus: "+",
  ast: "*",
  lsqb: "[",
  rsqb: "]",
  lcub: "{",
  rcub: "}",
  verbar: "|",
  Hat: "^",
  grave: "`",
  hyphen: "‐",
  dash: "‐",
  // Görünmez ve boşluk karakterleri
  shy: "­",
  nbsp: " ",
  NonBreakingSpace: " ",
  ZeroWidthSpace: INVISIBLE,
  NegativeVeryThinSpace: INVISIBLE,
  NegativeThinSpace: INVISIBLE,
  NegativeMediumSpace: INVISIBLE,
  NegativeThickSpace: INVISIBLE,
  zwnj: "‌",
  zwj: "‍",
  lrm: "‎",
  rlm: "‏",
  NoBreak: "⁠",
  af: "⁡",
  ApplyFunction: "⁡",
  it: "⁢",
  InvisibleTimes: "⁢",
  ic: "⁣",
  InvisibleComma: "⁣",
  ensp: " ",
  emsp: " ",
  emsp13: " ",
  emsp14: " ",
  numsp: " ",
  puncsp: " ",
  thinsp: " ",
  ThinSpace: " ",
  hairsp: " ",
  VeryThinSpace: " ",
  MediumSpace: " ",
};

// `&amp; &lt; &gt; &quot;` ve sayısalları html.ts `decodeEntities` çözer; burada yalnız tablodakiler.
export function decodeNamed(text: string): string {
  return text.replace(/&([A-Za-z][A-Za-z0-9]*);/g, (whole, name: string) => NAMED[name] ?? whole);
}

// Kapalı kural (T9 yeniden inceleme 2 B1/B2, son inceleme m2): betik dışı HTML'de `&` YALNIZ `&amp;`,
// `&lt;`, `&gt;`, `&quot;` ya da `;` ile biten sayısal başvuruyla (`&#39;`, `&#x27;`) devam eder. Tarayıcı
// sayısal başvuruyu ve eski adları `;` OLMADAN da çözer (`/&#47evil.example/` = `//evil.example/`,
// `Pin&shynacle`); denetimin çözücüleri `;` ister. React her zaman `;` basar ve çıplak `&`i kaçışlar.
const ALLOWED_REFERENCE = /^&(?:amp|lt|gt|quot|#[0-9]+|#[xX][0-9A-Fa-f]+);/;

export function entityFindings(where: string, html: string): string[] {
  const text = stripScripts(html);
  const found = new Set<string>();
  for (const match of text.matchAll(/&/g)) {
    const rest = text.slice(match.index, match.index + 64);
    if (ALLOWED_REFERENCE.test(rest)) continue;
    const named = /^&([A-Za-z][A-Za-z0-9]*);/.exec(rest)?.[1];
    found.add(
      named !== undefined
        ? `adlı HTML varlığı &${named}; (React yalnız &amp; &lt; &gt; &quot; basar)`
        : `izinsiz karakter başvurusu "${/^&[#A-Za-z0-9]{0,16}/.exec(rest)?.[0] ?? "&"}" (yalnız &amp; &lt; &gt; &quot; ve ; ile biten sayısal)`,
    );
  }
  return [...found].map((finding) => `${where}: ${finding}`);
}
