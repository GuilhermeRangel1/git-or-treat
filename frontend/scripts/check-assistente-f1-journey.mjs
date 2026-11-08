import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const baseUrl = process.env.ASSISTENTE_BASE_URL ?? "http://127.0.0.1:5180";
const useLiveBackend = process.env.TSQL8_LIVE_BACKEND === "true";
const artifactSuffix = useLiveBackend ? "live-postgres-synthetic" : "synthetic";
const artifactDir = path.resolve(
  process.env.TSQL8_ARTIFACT_DIR ?? "../work/tsql8-visual-review",
);
const batchRef =
  "gold-csv-v2:GOLD_20261106T000000Z_aaaaaaaa:12345678-1234-4123-8123-123456789abc";
const limitation =
  "Faturamento representa valor faturado e não confirma recebimento ou pagamento.";
const cases = [
  {
    id: "F1-01",
    question: "Qual foi o faturamento de Recife em junho de 2026?",
    status: "answered",
    answer: "O faturamento total no período junho de 2026 foi R$ 200,00.",
    period: "2026-06",
    filters: ["Município: Recife"],
    columns: [
      {
        key: "revenue",
        label: "Faturamento",
        role: "measure",
        semantic_id: "revenue_total",
        unit: "R$",
      },
    ],
    rows: [["200.00"]],
    amounts: ["R$ 200,00"],
  },
  {
    id: "F1-02",
    question: "E o faturamento total de 2026?",
    status: "needs_clarification",
    clarification:
      "O faturamento total de 2026 exige janeiro a dezembro, mas a publicação cobre somente janeiro a junho. Quer consultar o acumulado disponível?",
    missing_fields: ["period"],
  },
  {
    id: "F1-03",
    question: "Então mostre o acumulado de janeiro a junho de 2026.",
    status: "answered",
    answer:
      "O faturamento total no período janeiro a junho de 2026 foi R$ 950,00.",
    period: "2026-01 a 2026-06",
    filters: ["Município: Recife"],
    columns: [
      {
        key: "revenue",
        label: "Faturamento",
        role: "measure",
        semantic_id: "revenue_total",
        unit: "R$",
      },
    ],
    rows: [["950.00"]],
    amounts: ["R$ 950,00"],
  },
  {
    id: "F1-04",
    question: "Compare esse acumulado com janeiro a junho de 2025.",
    status: "answered",
    answer:
      "O faturamento foi R$ 950,00 em 2026 e R$ 720,00 em 2025. A diferença foi R$ 230,00, uma variação de 31,94%.",
    period: "2026-01 a 2026-06 e 2025-01 a 2025-06",
    filters: ["Município: Recife"],
    columns: [
      {
        key: "current_total",
        label: "Faturamento 2026",
        role: "measure",
        semantic_id: "period_0_total",
        unit: "R$",
      },
      {
        key: "previous_total",
        label: "Faturamento 2025",
        role: "measure",
        semantic_id: "period_1_total",
        unit: "R$",
      },
      {
        key: "difference",
        label: "Diferença",
        role: "measure",
        semantic_id: "period_0_minus_period_1",
        unit: "R$",
      },
      {
        key: "growth",
        label: "Variação percentual",
        role: "measure",
        semantic_id: "period_0_growth_percent",
        unit: "%",
      },
    ],
    rows: [["950.00", "720.00", "230.00", "31.94"]],
    amounts: ["R$ 950,00", "R$ 720,00", "R$ 230,00", "31,94%"],
  },
  {
    id: "F1-05",
    question:
      "Mostre o faturamento por mês de janeiro a junho de 2026 em Recife.",
    status: "answered",
    answer:
      "O faturamento mensal de Recife, de janeiro a junho de 2026, está detalhado na tabela.",
    period: "2026-01 a 2026-06",
    filters: ["Município: Recife"],
    columns: [
      {
        key: "competency",
        label: "Competência",
        role: "dimension",
        semantic_id: "competency",
        unit: null,
      },
      {
        key: "revenue",
        label: "Faturamento",
        role: "measure",
        semantic_id: "revenue_total",
        unit: "R$",
      },
    ],
    rows: [
      ["2026-01", "150.00"],
      ["2026-02", "150.00"],
      ["2026-03", "150.00"],
      ["2026-04", "150.00"],
      ["2026-05", "150.00"],
      ["2026-06", "200.00"],
    ],
    amounts: ["R$ 150,00", "R$ 200,00"],
    chartTitle: "Faturamento mensal",
  },
  {
    id: "F1-06",
    question:
      "Quais cinco municípios mais faturaram entre janeiro e junho de 2026, considerando todos os municípios?",
    status: "answered",
    answer:
      "Recife teve o maior faturamento do período, com R$ 950,00. O ranking completo está na tabela.",
    period: "2026-01 a 2026-06",
    filters: [],
    universe: ["Municípios: todos os valores disponíveis no recorte"],
    columns: [
      {
        key: "municipality",
        label: "Município",
        role: "dimension",
        semantic_id: "municipality",
        unit: null,
      },
      {
        key: "revenue",
        label: "Faturamento",
        role: "measure",
        semantic_id: "revenue_total",
        unit: "R$",
      },
    ],
    rows: [
      ["Recife", "950.00"],
      ["Cidade Controle", "480.00"],
      ["Olinda", "480.00"],
      ["Jaboatão dos Guararapes", "420.00"],
    ],
    amounts: ["R$ 950,00", "R$ 480,00", "R$ 420,00"],
    chartTitle: "Ranking de faturamento",
  },
  {
    id: "F1-07",
    question: "Quanto corresponde a cada classe em Recife em junho de 2026?",
    status: "answered",
    answer:
      "O faturamento por classe de consumo em Recife, em junho de 2026, está detalhado na tabela.",
    period: "2026-06",
    filters: ["Município: Recife"],
    columns: [
      {
        key: "consumption_class",
        label: "Classe de consumo",
        role: "dimension",
        semantic_id: "consumption_class",
        unit: null,
      },
      {
        key: "revenue",
        label: "Faturamento",
        role: "measure",
        semantic_id: "revenue_total",
        unit: "R$",
      },
    ],
    rows: [
      ["COMERCIAL", "50.00"],
      ["RESIDENCIAL", "150.00"],
    ],
    amounts: ["R$ 50,00", "R$ 150,00"],
    chartTitle: "Faturamento por classe de consumo",
    screenshot: true,
  },
  {
    id: "F1-08",
    question:
      "Qual foi a soma em reais das faturas emitidas em Recife em junho de 2026?",
    status: "answered",
    answer: "O faturamento total no período junho de 2026 foi R$ 200,00.",
    period: "2026-06",
    filters: ["Município: Recife"],
    columns: [
      {
        key: "revenue",
        label: "Faturamento",
        role: "measure",
        semantic_id: "revenue_total",
        unit: "R$",
      },
    ],
    rows: [["200.00"]],
    amounts: ["R$ 200,00"],
  },
];

function sqlResponse(testCase, index) {
  const correlationId = (index + 1).toString(16).padStart(32, "0");
  const auditReference = (index + 101).toString(16).padStart(32, "0");
  if (testCase.status === "needs_clarification") {
    return {
      correlation_id: correlationId,
      audit_reference: auditReference,
      status: testCase.status,
      continuation_token: `continuation-token-${index}`,
      clarification: {
        question: testCase.clarification,
        missing_fields: testCase.missing_fields,
      },
    };
  }

  const digest = (index + 1).toString(16).padStart(64, "0");
  const evidenceColumns = testCase.columns.map(({ key, role, unit }) => ({
    name: key,
    role,
    unit,
  }));
  const evidenceRows = testCase.rows;
  const comparisonWithGrowth = testCase.id === "F1-04";
  return {
    correlation_id: correlationId,
    audit_reference: auditReference,
    status: "answered",
    continuation_token: `continuation-token-${index}`,
    evidence: {
      evidence_contract_version: comparisonWithGrowth
        ? "text-to-sql-f1-evidence-v3"
        : "text-to-sql-f1-evidence-v1",
      source_table: "gold_v2.diagnostico_receita",
      metric_id: "billing.revenue",
      coverage_quality: "certified",
      batch_ref: batchRef,
      evidence_digest: digest,
      columns: evidenceColumns,
      rows: evidenceRows,
    },
    presentation: {
      contract_version: comparisonWithGrowth
        ? "text-to-sql-f1-presentation-v2"
        : "text-to-sql-f1-presentation-v1",
      state: "ready",
      operation:
        testCase.id === "F1-05"
          ? "monthly_series"
          : testCase.id === "F1-06"
            ? "ranking"
            : testCase.id === "F1-07"
              ? "grouped_total"
              : testCase.id === "F1-04"
                ? "comparison"
                : "total",
      answer: testCase.answer,
      period: testCase.period,
      filters: testCase.filters,
      universe: testCase.universe ?? [],
      limitations: [limitation],
      columns: testCase.columns,
      rows: evidenceRows.map((cells, rowIndex) => ({
        observation_id: `row_${rowIndex + 1}`,
        cells,
      })),
      evidence_digest: digest,
    },
  };
}

const browser = await chromium.launch({
  headless: true,
  ...(process.env.PLAYWRIGHT_CHANNEL
    ? { channel: process.env.PLAYWRIGHT_CHANNEL }
    : {}),
});

try {
  await mkdir(artifactDir, { recursive: true });
  for (const viewport of [
    { name: "desktop", width: 1440, height: 960 },
    { name: "mobile", width: 390, height: 844 },
  ]) {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      reducedMotion: "reduce",
    });
    try {
      const page = await context.newPage();
      const pageErrors = [];
      const requests = [];
      const analysisStatuses = [];
      page.on("pageerror", (error) => pageErrors.push(error.message));
      page.on("console", (message) => {
        if (message.type() === "error") pageErrors.push(message.text());
      });
      page.on("response", (response) => {
        const pathname = new URL(response.url()).pathname;
        if (
          pathname === "/api/v1/ai/sql-analyses" ||
          /^\/api\/v1\/ai\/conversations\/[^/]+\/questions$/.test(pathname)
        ) {
          analysisStatuses.push(response.status());
        }
      });
      await page.route("**/api/v1/**", async (route) => {
        const url = new URL(route.request().url());
        if (url.pathname === "/api/v1/auth/session") {
          if (useLiveBackend) return route.continue();
          return route.fulfill({
            json: {
              enabled: true,
              user: {
                id: "tsql8-browser-review",
                username: "Revisão TSQL 8",
                profile: "commercial",
                permissions: ["panorama:read", "revenue:read", "ai:ask"],
              },
              expires_at: new Date(Date.now() + 3_600_000).toISOString(),
            },
          });
        }
        if (url.pathname === "/api/v1/ai/conversations") {
          if (route.request().method() === "GET") {
            return route.fulfill({ json: { items: [], has_more: false } });
          }
          if (!useLiveBackend && route.request().method() === "POST") {
            const now = new Date().toISOString();
            return route.fulfill({
              json: {
                id: "12345678-1234-4123-8123-123456789abc",
                title: "Revisão de interface",
                revision: 1,
                message_count: 0,
                created_at: now,
                updated_at: now,
                expires_at: new Date(Date.now() + 3_600_000).toISOString(),
              },
            });
          }
        }
        if (
          url.pathname === "/api/v1/ai/sql-analyses" ||
          /^\/api\/v1\/ai\/conversations\/[^/]+\/questions$/.test(url.pathname)
        ) {
          const body = route.request().postDataJSON();
          requests.push({
            method: route.request().method(),
            path: url.pathname,
            body,
          });
          const testCase = cases.find(
            (item) => item.question === body.question,
          );
          assert.ok(testCase, `Pergunta inesperada: ${body.question}`);
          if (useLiveBackend) return route.continue();
          return route.fulfill({
            json: sqlResponse(testCase, requests.length - 1),
          });
        }
        return route.fulfill({
          status: 503,
          json: { message: "Fora do escopo desta jornada isolada." },
        });
      });

      if (useLiveBackend) {
        const login = await context.request.post(
          `${baseUrl}/api/v1/auth/login`,
          {
            headers: { Origin: baseUrl },
            data: {
              username: "tsql8-browser-e2e",
              password: "synthetic-browser-e2e-only",
            },
          },
        );
        assert.equal(
          login.status(),
          200,
          "login de teste deve criar sessão real",
        );
      }

      await page.goto(`${baseUrl}/assistente`, { waitUntil: "networkidle" });
      assert.equal(
        await page.getByRole("checkbox", { name: "Testar análise F1" }).count(),
        0,
        "o seletor experimental F1 não deve aparecer no Assistente",
      );
      const question = page.getByRole("textbox", {
        name: "Escreva sua pergunta",
      });
      for (const testCase of cases) {
        const responsePromise = page.waitForResponse(
          (response) =>
            (/^\/api\/v1\/ai\/conversations\/[^/]+\/questions$/.test(
              new URL(response.url()).pathname,
            ) ||
              new URL(response.url()).pathname === "/api/v1/ai/sql-analyses") &&
            response.request().method() === "POST",
          { timeout: 30000 },
        );
        await question.fill(testCase.question);
        await question.press("Enter");
        const apiResponse = await responsePromise;
        assert.equal(apiResponse.status(), 200, `${testCase.id}: HTTP status`);
        const apiResult = await apiResponse.json();
        const renderedResponse = page
          .getByText(
            testCase.status === "needs_clarification"
              ? apiResult.clarification.question
              : apiResult.presentation.answer,
            { exact: true },
          )
          .last();
        try {
          await renderedResponse.waitFor();
        } catch (error) {
          console.error(`${testCase.id} page errors:`, pageErrors);
          console.error(
            `${testCase.id} visible text:`,
            await page.locator("body").innerText(),
          );
          throw error;
        }
        const assistantCard = renderedResponse.locator(
          "xpath=ancestor::article[1]",
        );
        if (testCase.status === "needs_clarification") {
          assert.equal(apiResult.status, "needs_clarification", testCase.id);
          await assistantCard
            .getByText(apiResult.clarification.question, { exact: true })
            .waitFor();
        } else {
          assert.equal(apiResult.status, "answered", testCase.id);
          await assistantCard
            .getByText(apiResult.presentation.answer, { exact: true })
            .waitFor();
          const resultTable = assistantCard
            .getByRole("region", { name: "Tabela do resultado Text-to-SQL" })
            .getByRole("table");
          for (const amount of testCase.amounts) {
            await resultTable
              .getByText(amount, { exact: true })
              .first()
              .waitFor();
          }
          if (testCase.chartTitle) {
            await assistantCard
              .getByRole("region", { name: testCase.chartTitle, exact: true })
              .waitFor();
          }
        }

        if (testCase.screenshot) {
          await assistantCard
            .getByText(/não confirma recebimento ou pagamento/)
            .waitFor();
          await assistantCard
            .getByText(
              /Fonte: Diagnóstico de receita · Gold v2, publicação de 06\/11\/2026/,
            )
            .waitFor();
          await assistantCard
            .getByText(/Registro de auditoria confirmado/)
            .waitFor();
          const tableScroller = assistantCard.getByLabel(
            "Resultados em tabela; use as setas para rolar",
          );
          await tableScroller.focus();
          await page.keyboard.press("ArrowDown");
          assert.equal(
            await tableScroller.evaluate(
              (element) => element === document.activeElement,
            ),
            true,
          );
          await page.screenshot({
            path: path.join(
              artifactDir,
              `assistente-f1-${viewport.name}-details-${artifactSuffix}.png`,
            ),
            fullPage: true,
          });
          await assistantCard
            .getByText(apiResult.presentation.answer, { exact: true })
            .scrollIntoViewIfNeeded();
          await page.screenshot({
            path: path.join(
              artifactDir,
              `assistente-f1-${viewport.name}-answer-${artifactSuffix}.png`,
            ),
            fullPage: true,
          });
        }
      }

      assert.equal(requests.length, cases.length);
      assert.ok(requests.every((request) => request.method === "POST"));
      assert.deepEqual(
        requests.map((request) => request.body.question),
        cases.map((testCase) => testCase.question),
      );
      assert.ok(
        requests.every((request) => request.path === "/api/v1/ai/sql-analyses"),
        "todas as mensagens devem usar a rota pública F1",
      );
      assert.ok(
        requests[1].body.conversation_id === requests[0].body.conversation_id &&
          requests[1].body.continuation_token === "continuation-token-0",
        "F1-02 deve continuar o contexto sem passar pelo endpoint legado",
      );
      assert.ok(
        requests[2].body.conversation_id === requests[1].body.conversation_id &&
          requests[2].body.continuation_token === "continuation-token-1",
        "F1-03 deve continuar o contexto depois do esclarecimento pela rota F1",
      );

      const viewportWidth = await page.evaluate(() => window.innerWidth);
      const documentWidth = await page.evaluate(
        () => document.documentElement.scrollWidth,
      );
      assert.ok(
        documentWidth <= viewportWidth,
        `${viewport.name}: documento excede o viewport (${documentWidth} > ${viewportWidth})`,
      );
      assert.deepEqual(pageErrors, []);
      if (useLiveBackend) {
        assert.deepEqual(
          analysisStatuses,
          cases.map(() => 200),
          "cada etapa da jornada deve chegar à rota real e voltar com HTTP 200",
        );
      }
      console.log(
        useLiveBackend
          ? `PASS ${viewport.name}: F1-01 a F1-08 por rota HTTP real e PostgreSQL sintético, incluindo contexto, tabela, auditoria, visualização e teclado.`
          : `PASS ${viewport.name}: F1-01 a F1-08, incluindo contexto, tabela, limitação, auditoria, visualização e teclado; API simulada com fixture sintética.`,
      );
    } finally {
      await context.close();
    }
  }
} finally {
  await browser.close();
}
