import assert from "node:assert/strict";
import { readFile, mkdir } from "node:fs/promises";
import vm from "node:vm";
import { chromium } from "playwright";

// Fixture pública e artificial. Esta verificação não comprova integração Gold.
const source = await readFile(
  new URL("../src/features/receita/ReceitaPage.test.tsx", import.meta.url),
  "utf8",
);
const fixture = vm.runInNewContext(
  "(" +
    source
      .slice(
        source.indexOf("const response = ") + 17,
        source.indexOf("\n};", source.indexOf("const response = ")) + 2,
      )
      .replace(/;$/, "") +
    ")",
);
const seriesMonths = Array.from({ length: 12 }, (_, index) => {
  const date = new Date(Date.UTC(2025, 6 + index, 1));
  const competencia = date.toISOString().slice(0, 7);
  return {
    competencia,
    billed_amount: 100000 + Math.sin(index / 1.5) * 15000,
    paid_amount: null,
    measured_energy_kwh: 90000 - index * 500,
    billed_energy_kwh: null,
  };
});
fixture.data.series = seriesMonths;
const windows = ["2022-07", "2023-06", "2025-07", "2026-06"];
const decomposition = {
  status: "available",
  windows,
  method: "PARES_MES_UC_PRECO_OBSERVADO_VOLUME_INTERACAO_V3",
  components: {
    preco: 5000,
    volume: -8000,
    interacao: -500,
    entradas: 0,
    saidas: 0,
    sem_leitura: 0,
    outros: 0,
  },
  initial_amount_brl: 80000,
  final_amount_brl: 76500,
  total_change_brl: -3500,
  residual_brl: 0,
  change_percent: -4.375,
  component_percentage_points: { preco: 6.25, volume: -10 },
  group_count: 1,
  incomplete_groups: 0,
  limitations: ["Demonstração artificial para conferir layout."],
};
const artifacts = new URL("../../work/receita-layout/", import.meta.url);
await mkdir(artifacts, { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    let body = {};
    if (url.pathname.endsWith("/auth/session"))
      body = { enabled: false, user: null, expires_at: null };
    else if (url.pathname.endsWith("/analytics/options"))
      body = {
        data: {
          competencias: seriesMonths.map((item) => item.competencia),
          municipio: ["Olinda"],
          bairro: ["Centro"],
          bairros: [{ municipio: "Olinda", bairro: "Centro" }],
          classe: ["Residencial"],
          alimentador: [],
        },
        source: fixture.metadata.source,
        limitations: [],
      };
    else if (url.pathname.endsWith("/revenue")) {
      body = structuredClone(fixture);
      for (const field of ["municipio", "bairro", "classe", "alimentador"])
        body.metadata.filters[field] = url.searchParams.get(field);
      const dimension = url.searchParams.get("group_by") || "municipio";
      body.data.breakdown.dimension = dimension;
      body.data.window_decomposition = decomposition;
      body.data.diagnosis = url.searchParams.get("include_diagnosis")
        ? {
            status: "available",
            volume_offset_percent: 160,
            population: {
              initial_billed_uc_count: 20,
              final_billed_uc_count: 22,
              change_percent: 10,
            },
            concentration: {
              dimension: "municipio",
              labels: ["Olinda"],
              share_negative_volume_percent: 100,
            },
            gd: {
              status: "available",
              cohorts: [
                {
                  group: "connected_between",
                  uc_count: 10,
                  measured_energy_change_percent: -70,
                },
                {
                  group: "no_record",
                  uc_count: 20,
                  measured_energy_change_percent: 10,
                },
              ],
              share_negative_volume_percent: 90,
              limitations: [],
            },
            limitations: [],
          }
        : null;
      body.data.window_breakdown = [
        {
          key: "segmento",
          label:
            dimension === "municipio"
              ? "Olinda"
              : dimension === "bairro"
                ? "Centro"
                : "Residencial",
          filters: {
            ...body.metadata.filters,
            [dimension]:
              dimension === "municipio"
                ? "Olinda"
                : dimension === "bairro"
                  ? "Centro"
                  : "Residencial",
          },
          decomposition,
        },
      ];
    }
    await route.fulfill({ json: body });
  });
  for (const width of [1440, 390])
    for (const theme of ["light", "dark"]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("http://127.0.0.1:5187/receita");
      await page.evaluate(
        (value) => document.documentElement.setAttribute("data-theme", value),
        theme,
      );
      try {
        await page
          .getByRole("heading", { name: /A receita diminuiu/ })
          .waitFor({ timeout: 10000 });
      } catch (error) {
        console.log(await page.locator("body").innerText());
        console.log(errors);
        throw error;
      }
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        true,
        "Resumo sem overflow",
      );
      await page.screenshot({
        path: new URL(
          `${width}-${theme}-resumo.png`,
          artifacts,
        ).pathname.replace(/^\/(\w:)/, "$1"),
        fullPage: true,
      });
      await page
        .getByRole("button", { name: "Como calculamos e valores" })
        .click();
      await page
        .getByRole("dialog", { name: "Método e valores da comparação" })
        .waitFor();
      await page.keyboard.press("Escape");
      await page.getByRole("button", { name: /Investigar recortes/ }).click();
      await page.getByRole("button", { name: "Explorar Olinda" }).click();
      await page.getByRole("button", { name: "Explorar Centro" }).click();
      await page
        .getByRole("button", { name: /Selecionar classe Residencial/ })
        .waitFor();
      assert.ok(new URL(page.url()).searchParams.has("recorte_bairro"));
      await page
        .getByRole("button", { name: "Ver diagnóstico deste recorte" })
        .click();
      await page.getByRole("heading", { name: /receita/i }).waitFor();
      assert.equal(new URL(page.url()).searchParams.get("aba"), "resumo");
      assert.ok(new URL(page.url()).searchParams.has("recorte_bairro"));
      await page.getByRole("button", { name: /Investigar recortes/ }).click();
      await page.getByText("Ver tabela · todos os valores").click();
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        true,
        "Tabela completa não amplia a página horizontalmente",
      );
      await page.screenshot({
        path: new URL(
          `${width}-${theme}-investigar.png`,
          artifacts,
        ).pathname.replace(/^\/(\w:)/, "$1"),
        fullPage: true,
      });
      await page
        .getByRole("button", { name: "Ver histórico deste recorte" })
        .click();
      await page.getByLabel("Mês inicial do histórico").waitFor();
      assert.equal(
        await page.getByRole("dialog").locator("select").count(),
        2,
        "Histórico usa dois seletores integrados de mês/ano",
      );
      await page.screenshot({
        path: new URL(
          `${width}-${theme}-historico.png`,
          artifacts,
        ).pathname.replace(/^\/(\w:)/, "$1"),
        fullPage: true,
      });
      await page.getByRole("button", { name: /Ver tabela da série/ }).click();
      await page.getByRole("dialog").waitFor();
      await page.reload();
      await page
        .getByRole("dialog", { name: "Histórico do recorte" })
        .waitFor();
      await page.keyboard.press("Escape");
      await page.keyboard.press("Escape");
    }
  assert.deepEqual(errors, []);
  console.log(
    "Receita: 4 jornadas artificiais passaram (1440/390 px, claro/escuro), modal, drill-down, reload e overflow.",
  );
} finally {
  await browser.close();
}
