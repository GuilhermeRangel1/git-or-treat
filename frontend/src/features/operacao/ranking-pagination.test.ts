import { describe, expect, it } from "vitest";
import { pageWindow } from "./ranking-pagination";

describe("pageWindow", () => {
  it("mostra uma única página quando não há mais de uma", () => {
    expect(pageWindow(1, 1)).toEqual([1]);
    expect(pageWindow(1, 0)).toEqual([1]);
  });

  it("mostra todas as páginas quando são poucas", () => {
    expect(pageWindow(1, 3)).toEqual([1, 2, 3]);
    expect(pageWindow(4, 7)).toEqual([1, 2, 3, 4, 5, 6, 7]);
  });

  it("resume o fim da lista com reticências no começo", () => {
    expect(pageWindow(1, 25)).toEqual([1, 2, 3, "ellipsis", 25]);
    expect(pageWindow(2, 25)).toEqual([1, 2, 3, "ellipsis", 25]);
  });

  it("resume os dois lados quando a página atual está no meio", () => {
    expect(pageWindow(12, 25)).toEqual([
      1,
      "ellipsis",
      11,
      12,
      13,
      "ellipsis",
      25,
    ]);
  });

  it("resume o começo da lista quando a página atual está no fim", () => {
    expect(pageWindow(25, 25)).toEqual([1, "ellipsis", 23, 24, 25]);
    expect(pageWindow(24, 25)).toEqual([1, "ellipsis", 23, 24, 25]);
  });

  it("mostra o número em vez de reticências quando falta só uma página", () => {
    expect(pageWindow(4, 8)).toEqual([1, 2, 3, 4, 5, "ellipsis", 8]);
  });
});
