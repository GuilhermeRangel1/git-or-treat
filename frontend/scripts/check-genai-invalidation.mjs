import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";
import { chromium } from "playwright";

// Dados e sessão artificiais. Exercita o portal real; não certifica o lote Gold.
const origin = process.env.INVALIDATION_BASE_URL ?? "http://127.0.0.1:5184";
assert.ok(["127.0.0.1", "localhost"].includes(new URL(origin).hostname));
const source = await readFile(
  new URL("../src/shared/analytics/syntheticData.ts", import.meta.url),
  "utf8",
);
const js = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText;
const { calculateSyntheticPanorama } = await import(
  `data:text/javascript;base64,${Buffer.from(js).toString("base64")}`
);
const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
  });
  const page = await context.newPage();
  let fingerprint = "a".repeat(64),
    insightError = false,
    delayChat = false,
    releaseChat;
  const questionRequests = [];
  const filters = {
    periodo: "2024-04",
    comparacao: "anterior",
    municipio: "todos",
    classe: "todas",
  };
  const json = (route, value, status = 200) =>
    route.fulfill({ status, json: value });
  await page.route(/\/api\/v1\//, async (route) => {
    const req = route.request(),
      url = new URL(req.url());
    if (url.pathname === "/api/v1/auth/session")
      return json(route, {
        enabled: true,
        user: {
          id: "invalidation-test",
          username: "Teste local",
          permissions: ["orders:read"],
        },
        expires_at: new Date(Date.now() + 3600000).toISOString(),
      });
    if (url.pathname === "/api/v1/panorama") {
      const f = {
        ...filters,
        ...Object.fromEntries(
          [...url.searchParams].filter(([k]) => k in filters),
        ),
      };
      const d = calculateSyntheticPanorama(f);
      d.loteVersao = "artificial-local";
      d.periodoIncompleto = true;
      d.opcoesFiltros = {
        competencias: ["2024-04"],
        municipios: ["Recife", "Olinda"],
        classes: ["Residencial", "Comercial"],
      };
      for (const metric of Object.values(d.metricas))
        Object.assign(metric, {
          status: "partial",
          statusComparacao:
            metric.valorAnterior == null ? "unavailable" : "partial",
          limitacoes: [],
          limitacoesComparacao: [],
        });
      d.metricas.ucsFaturadasNoMes = { ...d.metricas.ucsAtivas };
      d.serieMensal.forEach((row) => (row.status = "partial"));
      return json(route, {
        data: d,
        metadata: {
          contract_version: "2.0.0",
          status: "partial",
          period: { start: f.periodo, end: f.periodo, granularity: "month" },
          temporal_scope: "monthly",
          schema_version: "gold-csv-v2",
          fingerprint,
          filters: {
            municipio: f.municipio === "todos" ? null : f.municipio,
            classe: f.classe === "todas" ? null : f.classe,
            bairro: null,
            alimentador: null,
          },
          source: {
            kind: "gold",
            version: d.loteVersao,
            is_demo: false,
            updated_at: d.dataAtualizacao,
          },
          limitations: ["Fixture artificial de invalidação"],
        },
      });
    }
    if (url.pathname === "/api/v1/ai/insights") {
      const body = req.postDataJSON();
      assert.equal(body.fingerprint, fingerprint);
      if (insightError)
        return json(
          route,
          {
            contract_version: "v1",
            status: "error",
            correlation_id: "a".repeat(32),
            message: "Publicação alterada",
            error: { code: "invalid_context", retryable: false },
          },
          409,
        );
      const d = calculateSyntheticPanorama(body.filters),
        m = d.metricas.receitaFaturada;
      return json(route, {
        metric: { id: m.id, definicao: m.definicao, formula: m.formula },
        source: {
          kind: "gold",
          fingerprint,
          loteVersao: "artificial-local",
          dataAtualizacao: d.dataAtualizacao,
          isDemo: false,
          limitacoes: [],
        },
        analysis: {
          direcao: "indisponivel",
          variacaoPercentual: null,
          principalContribuicao: null,
          compensacao: null,
        },
        insight: {
          contract_version: "v1",
          correlation_id: "a".repeat(32),
          audit_reference: null,
          error: null,
          status: "answered",
          context: {
            metric: m.nome,
            unit: m.unidade,
            period: {
              start: "2024-04-01",
              end: "2024-04-30",
              granularity: "month",
            },
            filters: body.filters,
          },
          observation: { values: [{ label: "Atual", value: m.valorAtual }] },
          hypothesis: "Hipótese artificial para conferir invalidação.",
          message: null,
          evidence: [
            {
              source: "gold.local",
              description: "Fixture artificial, sem dados reais",
              is_demo: false,
            },
          ],
          limitations: ["Teste controlado de interface"],
        },
      });
    }
    if (url.pathname === "/api/v1/ai/questions") {
      const body = req.postDataJSON();
      questionRequests.push(body);
      if (delayChat) await new Promise((resolve) => (releaseChat = resolve));
      return json(route, {
        contract_version: "v1",
        status: "answered",
        answer: "Resposta artificial vigente.",
        evidence: [
          {
            source: "gold.local",
            description: "Fixture de publicação",
            is_demo: false,
          },
        ],
        limitations: ["Teste artificial"],
        analysis_context: {
          metric: "billing.revenue",
          unit: "R$",
          filters: {},
          batch_reference: "gold-csv-v2:artificial:" + fingerprint[0],
        },
      });
    }
    return json(route, {}, 503);
  });
  await page.goto(
    origin +
      "/panorama?periodo=2024-04&comparacao=anterior&municipio=todos&classe=todas",
  );
  await page
    .getByText("Hipótese artificial para conferir invalidação.", {
      exact: true,
    })
    .first()
    .waitFor();
  insightError = true;
  await page
    .getByRole("button", { name: "Atualizar interpretação" })
    .count()
    .then(async (n) => {
      if (n)
        await page
          .getByRole("button", { name: "Atualizar interpretação" })
          .click();
      else {
        await page
          .getByRole("link", { name: "Assistente", exact: true })
          .click();
        await page.getByRole("link", { name: "Panorama", exact: true }).click();
      }
    });
  await page
    .getByText(/O lote mudou desde/)
    .first()
    .waitFor();
  assert.equal(
    await page
      .getByText("Hipótese artificial para conferir invalidação.", {
        exact: true,
      })
      .count(),
    0,
  );
  await page.getByRole("link", { name: "Assistente", exact: true }).click();
  const input = page.getByRole("textbox", { name: "Escreva sua pergunta" });
  await input.fill("Qual a receita?");
  await input.press("Enter");
  await page
    .getByText("Resposta artificial vigente.", { exact: true })
    .waitFor();
  assert.deepEqual(questionRequests[0].expected_publication, {
    lote: "artificial-local",
    fingerprint,
  });
  delayChat = true;
  await input.fill("E o consumo?");
  await input.press("Enter");
  await page.getByText("Analisando a pergunta").waitFor();
  await page.getByRole("link", { name: "Panorama", exact: true }).click();
  await page
    .getByRole("heading", { name: "Sua rede, em perspectiva." })
    .waitFor();
  releaseChat();
  await page.getByRole("link", { name: "Assistente", exact: true }).click();
  await page.getByRole("textbox", { name: "Escreva sua pergunta" }).waitFor();
  assert.equal(
    await page
      .getByText("Resposta artificial vigente.", { exact: true })
      .count(),
    0,
  );
  console.log(
    "PASS: portal real; fingerprint no pedido; 409 oculta insight antigo; chat vinculado à publicação; resposta atrasada após mudança de rota descartada. API/sessão artificiais, sem banco ou provedor.",
  );
  await context.close();
} finally {
  await browser.close();
}
