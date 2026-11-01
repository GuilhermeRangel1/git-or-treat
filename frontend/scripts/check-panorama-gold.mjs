import assert from "node:assert/strict";
import { chromium } from "playwright";
let input;
if (process.env.GENAI_BROWSER_CASE) {
  input = {
    ...JSON.parse(process.env.GENAI_BROWSER_CASE),
    origin: process.env.GENAI_BROWSER_BASE_URL || "http://127.0.0.1:5182",
    username: process.env.GENAI_BROWSER_USERNAME,
    password: process.env.GENAI_BROWSER_PASSWORD,
    artifacts: process.env.GENAI_BROWSER_ARTIFACT_DIR,
  };
} else {
  if (process.stdin.isTTY)
    throw new Error(
      "Configure GENAI_BROWSER_CASE e as credenciais locais de teste.",
    );
  let raw = "";
  for await (const chunk of process.stdin) raw += chunk;
  if (!raw.trim())
    throw new Error(
      "Forneça a configuração privada de teste por ambiente ou stdin.",
    );
  input = JSON.parse(raw);
}
assert.ok(
  input.username && input.password && input.filters,
  "Configuração de teste incompleta.",
);
assert.ok(
  new URL(input.origin).hostname === "127.0.0.1" ||
    new URL(input.origin).hostname === "localhost",
  "Use apenas o portal local autorizado.",
);

const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
  });
  const login = await context.request.post(
    input.origin + "/api/v1/auth/login",
    {
      data: { username: input.username, password: input.password },
      headers: { Origin: input.origin },
    },
  );
  assert.equal(login.status(), 200, "login local");
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.name));
  const responseReady = page.waitForResponse(
    (r) =>
      r.url().includes("/api/v1/ai/insights") &&
      r.request().method() === "POST",
    { timeout: 60000 },
  );
  await page.goto(
    input.origin + "/panorama?" + new URLSearchParams(input.filters),
    { waitUntil: "domcontentloaded" },
  );
  const response = await responseReady;
  const body = await response.json();
  assert.equal(
    response.status(),
    200,
    "insight HTTP " + response.status() + " " + body.error?.code,
  );
  assert.equal(body.insight.status, "answered", body.insight.status);
  assert.equal(body.source.isDemo, false);
  assert.ok(body.insight.audit_reference);
  assert.equal(body.insight.observation.values[0].value, input.expected);
  await page
    .getByText("Hipótese para investigar", { exact: true })
    .waitFor({ timeout: 10000 });
  assert.equal(await page.getByText(/Os números são fictícios/).count(), 0);
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const theme of ["light", "dark"]) {
      if ((await page.locator("html").getAttribute("data-theme")) !== theme)
        await page
          .getByRole("button", { name: /Alternar para tema/ })
          .first()
          .click();
      const trigger = page.getByRole("button", {
        name: "Ver análise detalhada",
      });
      await trigger.click();
      const dialog = page.getByRole("dialog");
      await dialog.waitFor();
      if (
        await dialog
          .getByRole("button", { name: "Ver fundamento", exact: true })
          .count()
      )
        await dialog
          .getByRole("button", { name: "Ver fundamento", exact: true })
          .click();
      await dialog.getByLabel("Fundamento do insight").waitFor();
      assert.ok((await dialog.innerText()).includes(body.source.loteVersao));
      assert.ok(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth + 1,
        ),
        "sem overflow",
      );
      if (input.artifacts)
        await page.screenshot({
          path: input.artifacts + "/genai12-" + width + "-" + theme + ".png",
          fullPage: false,
        });
      await page.keyboard.press("Escape");
      await dialog.waitFor({ state: "hidden" });
      assert.equal(
        await trigger.evaluate((e) => e === document.activeElement),
        true,
        "foco restaurado",
      );
    }
  }
  const next = { ...input.filters, classe: "todas", comparacao: "anterior" };
  const nextReady = page.waitForResponse(
    (r) =>
      r.url().includes("/api/v1/ai/insights") &&
      r.request().method() === "POST",
    { timeout: 60000 },
  );
  await page.goto(input.origin + "/panorama?" + new URLSearchParams(next));
  const nextResponse = await nextReady;
  const nextBody = await nextResponse.json();
  assert.equal(nextResponse.status(), 200);
  assert.equal(nextBody.insight.status, "answered");
  assert.equal(nextBody.insight.observation.values[0].value, input.expectedAll);
  if (nextBody.insight.observation.values.length >= 3) {
    assert.equal(
      nextBody.insight.observation.values[1].value,
      input.previousAll,
    );
    assert.equal(
      nextBody.insight.observation.values[2].value,
      Math.round((input.expectedAll - input.previousAll) * 100) / 100,
    );
  }
  await page.route("**/api/v1/ai/insights", (route) =>
    route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({
        contract_version: "v1",
        status: "error",
        correlation_id: "e".repeat(32),
        message: "O lote mudou. Atualize o Panorama.",
        error: { code: "invalid_context", retryable: false },
      }),
    }),
  );
  const staleReady = page.waitForResponse(
    (r) => r.url().includes("/api/v1/ai/insights") && r.status() === 409,
  );
  await page.evaluate(() =>
    window.dispatchEvent(new Event("visibilitychange")),
  );
  await staleReady;
  await page
    .getByText(/O lote mudou desde que os indicadores foram carregados/)
    .waitFor();
  assert.equal(
    await page.getByText("Hipótese para investigar", { exact: true }).count(),
    0,
  );
  assert.ok(
    await page
      .getByRole("region", { name: "Indicadores principais do Panorama" })
      .isVisible(),
  );
  assert.deepEqual(errors, []);
  console.log(
    "PASS: jornada autenticada Gold v2 + provedor configurado, KPI reconciliado, painel/fundamento, desktop/mobile, claro/escuro, Escape e foco.",
  );
  await context.close();
} finally {
  await browser.close();
}
