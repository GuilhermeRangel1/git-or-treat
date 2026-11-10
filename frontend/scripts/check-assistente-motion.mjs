import assert from "node:assert/strict";
import { chromium } from "playwright";

// Prova de apresentação: respostas artificiais; não substitui o aceite Gold.
const browser = await chromium.launch({
  headless: true,
  ...(process.env.PLAYWRIGHT_CHANNEL
    ? { channel: process.env.PLAYWRIGHT_CHANNEL }
    : {}),
});
try {
  for (const reducedMotion of ["no-preference", "reduce"]) {
    const context = await browser.newContext({ reducedMotion });
    try {
      const page = await context.newPage();
      page.on("pageerror", (error) => console.error(error.message));
      page.on("console", (message) => {
        if (message.type() === "error") console.error(message.text());
      });
      let releaseResponse;
      const pending = new Promise((resolve) => {
        releaseResponse = resolve;
      });
      let requests = 0;
      await page.route(/\/api\/v1\//, async (route) => {
        const path = new URL(route.request().url()).pathname;
        if (path === "/api/v1/auth/session") {
          return route.fulfill({
            json: {
              enabled: true,
              user: {
                id: "motion-test",
                username: "Teste visual",
                profile: "commercial",
                permissions: ["panorama:read", "revenue:read", "ai:ask"],
              },
              expires_at: new Date(Date.now() + 3600000).toISOString(),
            },
          });
        }
        if (
          path === "/api/v1/ai/conversations" &&
          route.request().method() === "GET"
        ) {
          return route.fulfill({ json: { items: [], has_more: false } });
        }
        if (
          path === "/api/v1/ai/conversations" &&
          route.request().method() === "POST"
        ) {
          const now = new Date().toISOString();
          return route.fulfill({
            json: {
              id: "11111111-1111-4111-8111-111111111111",
              title: "Nova conversa",
              revision: 1,
              created_at: now,
              updated_at: now,
              expires_at: new Date(Date.now() + 3_600_000).toISOString(),
              message_count: 0,
            },
          });
        }
        if (path.endsWith("/questions")) {
          requests++;
          await pending;
          return route.fulfill({
            json: {
              contract_version: "v1",
              status: "answered",
              answer: "O consumo fictício foi de 100 kWh em janeiro de 2025.",
              evidence: [
                {
                  source: "synthetic.fixture",
                  description: "Cenário artificial de acessibilidade.",
                  is_demo: true,
                },
              ],
              limitations: [
                "Valores fictícios usados somente nesta prova visual.",
              ],
              analysis_context: {
                metric_label: "Consumo",
                unit: "kWh",
                period: "2025-01",
                filters: {},
              },
            },
          });
        }
        return route.fulfill({
          status: 503,
          json: { message: "Fora do escopo desta prova visual." },
        });
      });
      await page.goto(
        `${process.env.MOTION_BASE_URL ?? "http://127.0.0.1:5180"}/assistente`,
      );
      const field = page.getByRole("textbox", { name: "Escreva sua pergunta" });
      await field.fill("Qual foi o consumo em janeiro de 2025?");
      const requestStarted = page.waitForRequest(
        (request) => new URL(request.url()).pathname.endsWith("/questions"),
        { timeout: 5000 },
      );
      await field.press("Enter");
      const didStart = await requestStarted.then(() => true).catch(() => false);
      if (!didStart) {
        console.error(
          `Sem chamada ao endpoint; tela: ${await page.locator("body").innerText()}`,
        );
        throw new Error("O Assistente não iniciou a consulta.");
      }
      await page
        .getByRole("status")
        .filter({ hasText: "Consultando os dados" })
        .waitFor({ timeout: 5000 });
      assert.equal(await field.isDisabled(), true);
      assert.equal(
        await page
          .getByRole("button", { name: "Enviar pergunta" })
          .isDisabled(),
        true,
      );
      const dotAnimations = await page
        .locator(".assistant-processing-dot")
        .evaluateAll((icons) =>
          icons.map((icon) => getComputedStyle(icon).animationName),
        );
      const buttonAnimations = await page
        .locator("button svg.animate-spin")
        .evaluateAll((icons) =>
          icons.map((icon) => getComputedStyle(icon).animationName),
        );
      assert.equal(dotAnimations.length, 3, "Conferir pontos de processamento");
      assert.equal(buttonAnimations.length, 1, "Conferir indicador do botão");
      assert.equal(
        await page.evaluate(
          () => matchMedia("(prefers-reduced-motion: reduce)").matches,
        ),
        reducedMotion === "reduce",
      );
      assert.ok(
        [...dotAnimations, ...buttonAnimations].every((name) =>
          reducedMotion === "reduce" ? name === "none" : name !== "none",
        ),
        `Movimento ${reducedMotion}: ${[...dotAnimations, ...buttonAnimations].join(", ")}`,
      );
      releaseResponse();
      await page
        .getByText("O consumo fictício foi de 100 kWh em janeiro de 2025.", {
          exact: true,
        })
        .waitFor();
      await page.waitForFunction(
        () => document.activeElement?.id === "assistant-question",
      );
      assert.equal(requests, 1);
      assert.equal(await field.inputValue(), "");
      assert.equal(
        await page.getByRole("log").getAttribute("aria-live"),
        "polite",
      );
      await page.getByLabel("Fundamento da resposta").waitFor();
      await page
        .getByText("Valores fictícios usados somente nesta prova visual.", {
          exact: true,
        })
        .waitFor();
      console.log(
        `PASS ${reducedMotion}: movimento, envio por Enter, bloqueio durante consulta, foco de retorno, fundamento e limitações visíveis.`,
      );
    } finally {
      await context.close();
    }
  }
} finally {
  await browser.close();
}
