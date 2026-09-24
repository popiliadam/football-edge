// Adlı HTML varlıkları (T9 yeniden inceleme N1). React derlenmiş HTML'e yalnız `&amp; &lt; &gt; &quot;`
// ve sayısal varlık basar; başka her adlı varlık elle kurcalamadır ve BULGUDUR. Tarayıcının çözdüğü
// hâliyle görülebilsin diye güvenlikle ilgili HTML5 alt kümesi (URL ayraçları, görünmez ve boşluk
// karakterleri) ayrıca çözülür: `/&sol;host` = `//host`, `Pin&ZeroWidthSpace;nacle` = `Pinnacle`.
// Adlar büyük/küçük harfe duyarlıdır (HTML5 gibi).
import { stripScripts } from "../lib/html.ts";

const REACT_NAMED = ["amp", "lt", "gt", "quot"];

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

export function entityFindings(where: string, html: string): string[] {
  const names = [...stripScripts(html).matchAll(/&([A-Za-z][A-Za-z0-9]*);/g)]
    .map((match) => match[1] ?? "")
    .filter((name) => !REACT_NAMED.includes(name));
  return [...new Set(names)].map(
    (name) => `${where}: adlı HTML varlığı &${name}; (React yalnız &amp; &lt; &gt; &quot; basar)`,
  );
}
