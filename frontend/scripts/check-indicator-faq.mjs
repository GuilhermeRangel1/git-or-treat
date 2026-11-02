import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

// Interface real com sessão artificial e APIs indisponíveis: não é aceite Gold.
const browser = await chromium.launch({ headless: true });
const artifacts = new URL("../../work/faq-validation/", import.meta.url);
mkdirSync(artifacts, { recursive: true });
try {
  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 390, height: 844 },
  ]) {
    const context = await browser.newContext({ viewport });
    const page = await context.newPage();
    const errors = [];
    let modelCalls = 0;
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route("**/api/v1/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path === "/api/v1/auth/session")
        return route.fulfill({
          json: {
            enabled: true,
            user: {
              id: "faq-test",
              username: "Teste de ajuda",
              permissions: ["orders:read"],
            },
            expires_at: new Date(Date.now() + 3600000).toISOString(),
          },
        });
      if (path.includes("/ai/")) modelCalls++;
      return route.fulfill({
        status: 503,
        json: { message: "Fonte indisponível nesta prova de interface." },
      });
    });
    for (const route of [
      "assistente",
      "panorama",
      "receita",
      "operacao",
      "uc-360",
    ]) {
      await page.goto(
        `${process.env.FAQ_BASE_URL ?? "http://localhost:5173"}/${route}`,
      );
      if (route === "assistente")
        await page
          .getByRole("textbox", { name: "Escreva sua pergunta" })
          .fill("Quero investigar minha receita");
      for (const theme of ["light", "dark"]) {
        await page.evaluate(
          (value) => (document.documentElement.dataset.theme = value),
          theme,
        );
        const trigger = page.getByRole("button", {
          name: "Entenda os indicadores",
        });
        await trigger.click();
        const dialog = page.getByRole("dialog", {
          name: "Entenda os indicadores",
        });
        await dialog.waitFor();
        if (route === "assistente") {
          const examples = dialog.getByText(
            "Perguntas prontas para usar no Assistente",
            { exact: true },
          );
          await examples.click();
          await dialog
            .getByText("Receita e preços · 8 perguntas", { exact: true })
            .click();
          const example = dialog.getByRole("textbox", {
            name: "Pergunta de exemplo 1",
          });
          await example.focus();
          assert.equal(
            await example.evaluate(
              (element) =>
                element.selectionEnd - element.selectionStart ===
                element.value.length,
            ),
            true,
          );
          await dialog
            .getByRole("button", { name: "Copiar pergunta 1" })
            .waitFor({ state: "visible" });
          await page.screenshot({
            path: fileURLToPath(
              new URL(`${viewport.width}-${theme}-examples.png`, artifacts),
            ),
          });
          await examples.click();
        }
        const search = dialog.getByRole("searchbox");
        await search.fill(route === "operacao" ? "DEC" : "receita");
        await dialog.locator("details.group > summary").first().focus();
        await page.keyboard.press("Enter");
        await dialog
          .getByText(/Fonte interna/)
          .first()
          .waitFor({ state: "visible" });
        assert.equal(await dialog.getByRole("link").count(), 0);
        if (route === "assistente")
          await page.screenshot({
            path: fileURLToPath(
              new URL(`${viewport.width}-${theme}.png`, artifacts),
            ),
          });
        assert.equal(
          await dialog.evaluate(
            (element) => element.scrollWidth <= element.clientWidth + 1,
          ),
          true,
        );
        await search.fill("Qual foi a receita em junho de 2026?");
        await dialog
          .getByRole("status")
          .filter({ hasText: "precisa de uma consulta" })
          .waitFor();
        await page.keyboard.press("Escape");
        await dialog.waitFor({ state: "hidden" });
        await page.waitForFunction(
          (element) => element === document.activeElement,
          await trigger.elementHandle(),
        );
        assert.equal(
          await trigger.evaluate(
            (element) => element === document.activeElement,
          ),
          true,
        );
      }
      if (route === "assistente") {
        assert.equal(
          await page
            .getByRole("textbox", { name: "Escreva sua pergunta" })
            .inputValue(),
          "Quero investigar minha receita",
        );
        assert.equal(modelCalls, 0, "Abrir e buscar ajuda não chama a IA.");
        const field = page.getByRole("textbox", {
          name: "Escreva sua pergunta",
        });
        const question = "Qual foi a receita em junho de 2026?";
        await field.fill(question);
        const [request] = await Promise.all([
          page.waitForRequest(
            (item) => new URL(item.url()).pathname === "/api/v1/ai/questions",
          ),
          field.press("Enter"),
        ]);
        assert.equal(request.postDataJSON().question, question);
      }
    }
    assert.deepEqual(errors, []);
    assert.equal(
      modelCalls,
      1,
      "Somente o envio explícito da pergunta chama a API de IA.",
    );
    await context.close();
    console.log(
      `FAQ: cinco telas, claro/escuro, ${viewport.width}px, teclado e falha das APIs passaram.`,
    );
  }
} finally {
  await browser.close();
}
