import { describe, expect, it } from "vitest";
import { FormatError, formatNumber } from "./format.ts";

describe("formatNumber — yalnız ayraç ve birim, yuvarlama yok (spec §5.4)", () => {
  it.each([
    [45.7, "pct1", "en", "45.7%"],
    [45.7, "pct1", "tr", "%45,7"],
    [40, "pct1", "en", "40.0%"],
    [-1.3, "pp1", "en", "-1.3 pp"],
    [-1.3, "pp1", "tr", "-1,3 puan"],
    [-0, "pp1", "en", "0.0 pp"],
    [2.2, "price2", "en", "2.20"],
    [3.57, "price2", "tr", "3,57"],
    [-4.76, "pct2", "tr", "%-4,76"],
    [1834, "int", "en", "1834"],
  ] as const)("%s %s %s → %s", (value, kind, lang, expected) => {
    expect(formatNumber(value, kind, lang)).toBe(expected);
  });

  it.each([
    [45.75, "pct1"],
    [2.205, "price2"],
    [1.5, "int"],
    [1e-7, "pct1"],
    [Number.NaN, "pct1"],
    [Number.POSITIVE_INFINITY, "int"],
  ] as const)("%s (%s) sözleşme dışı → FormatError, sessiz yuvarlama yok", (value, kind) => {
    expect(() => formatNumber(value, kind, "en")).toThrow(FormatError);
  });
});
