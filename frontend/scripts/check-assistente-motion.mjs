import assert from "node:assert/strict";
import { chromium } from "playwright";

// Prova de apresentação: respostas artificiais; não substitui o aceite Gold.
const browser = await chromium.launch({ headless: true });
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
                permissions: ["orders:read"],
              },
              expires_at: new Date(Date.now() + 3600000).toISOString(),
            },
          });
        }
        if (path === "/api/v1/ai/questions") {
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
      await field.press("Enter");
      await page
        .getByRole("status")
        .filter({ hasText: "Analisando a pergunta" })
        .waitFor();
      assert.equal(await field.isDisabled(), true);
      assert.equal(
        await page
          .getByRole("button", { name: "Enviar pergunta" })
          .isDisabled(),
        true,
      );
      const animations = await page
        .locator("svg.animate-spin")
        .evaluateAll((icons) =>
          icons.map((icon) => getComputedStyle(icon).animationName),
        );
      assert.equal(
        animations.length,
        2,
        "Conferir indicador da conversa e do botão",
      );
      assert.equal(
        await page.evaluate(
          () => matchMedia("(prefers-reduced-motion: reduce)").matches,
        ),
        reducedMotion === "reduce",
      );
      assert.ok(
        animations.every((name) =>
          reducedMotion === "reduce" ? name === "none" : name !== "none",
        ),
        `Movimento ${reducedMotion}: ${animations.join(", ")}`,
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
      const details = page.getByLabel("Fundamento da resposta");
      await details.locator("summary").focus();
      await page.keyboard.press("Enter");
      assert.equal(await details.getAttribute("open"), "");
      await page
        .getByText("Valores fictícios usados somente nesta prova visual.", {
          exact: true,
        })
        .waitFor();
      console.log(
        `PASS ${reducedMotion}: dois indicadores, envio por Enter, bloqueio durante consulta, foco de retorno, fundamentos por teclado e limitações.`,
      );
    } finally {
      await context.close();
    }
  }
} finally {
  await browser.close();
}
