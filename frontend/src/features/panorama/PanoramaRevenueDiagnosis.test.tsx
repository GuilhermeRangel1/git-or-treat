import {
  configure,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import TestProviders from "@/shared/test/TestProviders";
import {
  acceptGoldIdentity,
  resetGoldPublication,
} from "@/shared/analytics/goldPublication";
import PanoramaRevenueDiagnosis from "./PanoramaRevenueDiagnosis";
import {
  PUBLICATION,
  revenueDiagnosis,
  revenueResponse,
  revenueWindow,
  visibleText,
} from "./revenue-diagnosis.test-support";

// A primeira renderização disputa a carga dos módulos com os demais workers.
configure({ asyncUtilTimeout: 4000 });

const FOOTNOTE = "Preço observado não é tarifa · Não indica causa";
const PERIOD_NOTE = "12 meses em cada período · não depende do filtro de mês";
const fetchMock = vi.fn();
const noComponents = {
  volume: null,
  preco: null,
  interacao: null,
  entradas: null,
  saidas: null,
  sem_leitura: null,
  outros: null,
};

function respondWith(content: Parameters<typeof revenueResponse>[1]) {
  fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), "http://localhost:5173");
    return new Response(JSON.stringify(revenueResponse(url, content)));
  });
}

function blockElement(
  scope: { municipio?: string; classe?: string; latestPeriod?: string } = {},
) {
  return (
    <TestProviders>
      <PanoramaRevenueDiagnosis
        municipio="todos"
        classe="todas"
        latestPeriod="2026-06"
        {...scope}
      />
    </TestProviders>
  );
}

function renderBlock(scope?: Parameters<typeof blockElement>[0]) {
  return render(blockElement(scope));
}

const block = () =>
  screen.getByRole("region", { name: "Diagnóstico comercial" });
const headline = () =>
  screen.getByText(/^(Preço observado|Volume) (adicionou|retirou|ficou em)/);
const columnBar = (name: RegExp) =>
  screen
    .getByRole("img", { name })
    .querySelector("[data-column-bar]") as HTMLElement;

beforeEach(() => {
  resetGoldPublication();
  acceptGoldIdentity(PUBLICATION);
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

it("mostra estado de carregamento enquanto a consulta não termina", () => {
  fetchMock.mockReturnValue(new Promise(() => {}));
  renderBlock();

  expect(within(block()).getByRole("status")).toHaveTextContent(
    "Consultando o diagnóstico deste recorte",
  );
  expect(screen.queryByText(FOOTNOTE)).toBeNull();
  expect(screen.queryByText(PERIOD_NOTE)).toBeNull();
  expect(screen.queryByText("ANTES")).toBeNull();
});

it("mostra ANTES e DEPOIS com as datas da API, em title e aria-label por extenso", async () => {
  respondWith({
    window: revenueWindow({
      windows: ["2021-01", "2021-12", "2024-02", "2025-01"],
    }),
  });
  renderBlock();

  const before = await screen.findByRole("group", {
    name: "ANTES: janeiro de 2021 a dezembro de 2021",
  });
  const after = screen.getByRole("group", {
    name: "DEPOIS: fevereiro de 2024 a janeiro de 2025",
  });
  expect(within(before).getByText("jan/2021 – dez/2021")).toBeVisible();
  expect(within(after).getByText("fev/2024 – jan/2025")).toBeVisible();
  expect(before).toHaveAttribute("title", "janeiro de 2021 a dezembro de 2021");
  expect(after).toHaveAttribute("title", "fevereiro de 2024 a janeiro de 2025");
  expect(screen.getByText(PERIOD_NOTE)).toBeVisible();
});

it("não mostra mais selos nem o link para a Receita", async () => {
  respondWith({});
  renderBlock({ municipio: "Olinda" });

  await screen.findByText(FOOTNOTE);
  expect(screen.queryByText(/Período fixo/)).toBeNull();
  expect(screen.queryByRole("link")).toBeNull();
});

it("mostra o Recorte só quando há filtro de município ou classe", async () => {
  respondWith({});
  const { unmount } = renderBlock();
  await screen.findByText(FOOTNOTE);
  expect(screen.queryByText(/Recorte/)).toBeNull();
  unmount();

  const first = renderBlock({ municipio: "JABOATÃO DOS GUARARAPES" });
  expect(
    await screen.findByText(
      "Recorte: Jaboatão dos Guararapes · Todas as classes",
    ),
  ).toBeVisible();
  first.unmount();

  const second = renderBlock({ classe: "RESIDENCIAL" });
  expect(
    await screen.findByText("Recorte: Todos os municípios · Residencial"),
  ).toBeVisible();
  second.unmount();

  renderBlock({ municipio: "OLINDA", classe: "RESIDENCIAL" });
  expect(
    await screen.findByText("Recorte: Olinda · Residencial"),
  ).toBeVisible();
});

it("usa a manchete como título, sem sinal, com faturamento, anotação e rodapé", async () => {
  respondWith({
    window: revenueWindow({
      components: {
        ...revenueWindow().components,
        preco: 16485216.2,
        volume: -6123456.78,
      },
      total_change_brl: 12345678.9,
      initial_amount_brl: 203456789.12,
      final_amount_brl: 215802468.02,
    }),
  });
  renderBlock();

  await screen.findByText(FOOTNOTE);
  expect(screen.queryByText("Preço × volume")).toBeNull();
  expect(headline().tagName).toBe("H3");
  expect(visibleText(headline())).toMatch(
    /^Preço observado adicionou R\$\s16,5 mi · Volume retirou R\$\s6,1 mi$/,
  );
  expect(visibleText(screen.getByText(/^Faturamento:/))).toMatch(
    /^Faturamento: R\$ 203,5 mi → R\$ 215,8 mi$/,
  );
  expect(screen.queryByText(/Saldo:/)).toBeNull();
  expect(screen.getByRole("img", { name: /^Saldo/ })).toBeVisible();
  expect(
    screen.getByText("O volume devolveu 37,2% do ganho de preço"),
  ).toHaveClass("text-content");
  expect(screen.queryByText(/Base parcial/)).toBeNull();
});

it("desenha colunas na mesma escala, a partir do mesmo zero, sem acumular", async () => {
  respondWith({
    window: revenueWindow({
      components: {
        ...revenueWindow().components,
        preco: 1000,
        volume: -500,
      },
      total_change_brl: 700,
    }),
  });
  renderBlock();

  await screen.findByRole("img", { name: /^Saldo/ });
  const price = columnBar(/^Preço observado/);
  const volume = columnBar(/^Volume/);
  const balance = columnBar(/^Saldo/);
  // A escala total é 1000 para cima + 500 para baixo; a linha de zero fica em 2/3.
  expect(Number.parseFloat(price.style.height)).toBeCloseTo(66.67, 1);
  expect(Number.parseFloat(volume.style.height)).toBeCloseTo(33.33, 1);
  expect(Number.parseFloat(balance.style.height)).toBeCloseTo(46.67, 1);
  expect(Number.parseFloat(price.style.bottom)).toBeCloseTo(33.33, 1);
  expect(Number.parseFloat(balance.style.bottom)).toBeCloseTo(33.33, 1);
  expect(Number.parseFloat(volume.style.top)).toBeCloseTo(66.67, 1);
  expect(price.style.top).toBe("");
  expect(volume.style.bottom).toBe("");
});

it("mostra valor compacto com sinal e o exato em title e aria-label, com cor pelo sinal", async () => {
  respondWith({
    window: revenueWindow({
      components: {
        ...revenueWindow().components,
        preco: 16485216.2,
        volume: -6123456.78,
      },
      total_change_brl: -2000000,
    }),
  });
  renderBlock();

  const price = await screen.findByRole("img", {
    name: /^Preço observado: \+R\$\s16\.485\.216,20$/,
  });
  const volume = screen.getByRole("img", {
    name: /^Volume: −R\$\s6\.123\.456,78$/,
  });
  const balance = screen.getByRole("img", {
    name: /^Saldo: −R\$\s2\.000\.000/,
  });
  expect(price.getAttribute("title")).toMatch(
    /^Preço observado: \+R\$\s16\.485\.216,20$/,
  );
  expect(volume.getAttribute("title")).toMatch(
    /^Volume: −R\$\s6\.123\.456,78$/,
  );
  expect(balance.getAttribute("title")).toMatch(
    /^Saldo: −R\$\s2\.000\.000,00$/,
  );
  for (const column of [price, volume, balance]) {
    expect(column.getAttribute("title")).toBe(
      column.getAttribute("aria-label"),
    );
    expect(column).not.toHaveAttribute("tabindex");
  }
  expect(visibleText(price)).toMatch(/^\+R\$ 16,5 miPreço observado$/);
  expect(visibleText(volume)).toMatch(/^−R\$ 6,1 miVolume$/);
  expect(columnBar(/^Preço observado/)).toHaveClass("bg-success/50");
  expect(columnBar(/^Volume/)).toHaveClass("bg-danger/50");
  expect(columnBar(/^Saldo/)).toHaveClass("bg-danger/70");
});

it.each([
  [
    "positivo",
    5000000,
    "bg-success/70",
    "text-[var(--status-success-text)]",
    /^\+R\$ 5 miSaldo$/,
  ],
  [
    "negativo",
    -5000000,
    "bg-danger/70",
    "text-[var(--action-danger-text)]",
    /^−R\$ 5 miSaldo$/,
  ],
  ["zero", 0, "bg-muted/70", "text-content", /^R\$ 0,00Saldo$/],
])(
  "a coluna Saldo segue o sinal do valor: %s",
  async (_name, balance, barTone, valueTone, text) => {
    respondWith({ window: revenueWindow({ total_change_brl: balance }) });
    renderBlock();

    const column = await screen.findByRole("img", { name: /^Saldo/ });
    expect(visibleText(column)).toMatch(text);
    const bar = columnBar(/^Saldo/);
    expect(bar).toHaveClass(barTone);
    expect(bar.querySelector("span")).toHaveClass(valueTone);
    expect(column.querySelector("p")).toHaveClass("font-medium", "text-muted");
  },
);

it("não mostra coluna de Demais componentes, que a API não devolve pronta", async () => {
  respondWith({});
  renderBlock();

  await screen.findByRole("img", { name: /^Saldo/ });
  expect(screen.queryByText("Demais componentes")).toBeNull();
  expect(
    within(block())
      .getAllByRole("img")
      .map((column) => column.querySelector("p")?.textContent),
  ).toEqual(["Preço observado", "Volume", "Saldo"]);
});

it("segue o sinal dos valores na manchete e nas colunas", async () => {
  respondWith({
    window: revenueWindow({
      components: { ...revenueWindow().components, preco: -500, volume: 300 },
    }),
    diagnosis: revenueDiagnosis({ volume_offset_percent: null }),
  });
  renderBlock();

  await screen.findByRole("img", { name: /^Volume/ });
  expect(visibleText(headline())).toMatch(
    /^Preço observado retirou R\$ 500,00 · Volume adicionou R\$ 300,00$/,
  );
  expect(columnBar(/^Volume/)).toHaveClass("bg-success/50");
  expect(columnBar(/^Preço observado/)).toHaveClass("bg-danger/50");
});

it.each([
  ["sem nenhum valor", {}],
  ["só com o inicial", { initial_amount_brl: 100, final_amount_brl: null }],
  ["só com o final", { initial_amount_brl: null, final_amount_brl: 100 }],
])("não mostra o faturamento %s", async (_name, amounts) => {
  respondWith({ window: revenueWindow(amounts) });
  renderBlock();

  await screen.findByRole("img", { name: /^Volume/ });
  expect(screen.queryByText(/^Faturamento/)).toBeNull();
});

it("sem saldo na API, esconde a coluna de Saldo", async () => {
  respondWith({ window: revenueWindow({ total_change_brl: null }) });
  renderBlock();

  await screen.findByRole("img", { name: /^Volume/ });
  expect(screen.queryByRole("img", { name: /^Saldo/ })).toBeNull();
});

it("mudar só a competência não altera o Recorte nem dispara nova consulta", async () => {
  respondWith({});
  const scope = { municipio: "Olinda", classe: "todas" };
  const { rerender } = renderBlock({ ...scope, latestPeriod: "2026-06" });
  await screen.findByText("Recorte: Olinda · Todas as classes");
  expect(fetchMock).toHaveBeenCalledTimes(1);

  rerender(blockElement({ ...scope, latestPeriod: "2026-05" }));
  await new Promise((resolve) => setTimeout(resolve, 0));

  expect(screen.getByText("Recorte: Olinda · Todas as classes")).toBeVisible();
  expect(fetchMock).toHaveBeenCalledTimes(1);

  rerender(blockElement({ municipio: "Paulista", latestPeriod: "2026-05" }));
  expect(await screen.findByText(/^Recorte: Paulista/)).toBeVisible();
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

it("usa section e div, sem article, com um único bloco externo", async () => {
  respondWith({});
  renderBlock();

  await screen.findByText(FOOTNOTE);
  expect(block().tagName).toBe("SECTION");
  expect(block()).toHaveClass(
    "rounded-xl",
    "border",
    "border-border",
    "bg-surface",
  );
  expect(screen.queryByRole("article")).toBeNull();
  expect(
    screen.getByRole("region", { name: /^Preço observado adicionou/ }),
  ).toHaveClass("rounded-lg", "border-border", "bg-canvas/50");
});

it("mostra janelas, nota de período e Recorte em linhas compactas", async () => {
  respondWith({});
  renderBlock({ municipio: "Olinda", classe: "RESIDENCIAL" });

  const recorte = await screen.findByText("Recorte: Olinda · Residencial");
  expect(recorte.parentElement).toBe(
    screen.getByText(PERIOD_NOTE).parentElement,
  );
  expect(recorte.parentElement).toHaveTextContent(
    `${PERIOD_NOTE} · Recorte: Olinda · Residencial`,
  );
  expect(screen.getByRole("group", { name: /^ANTES:/ })).toHaveTextContent(
    "ANTESjul/2022 – jun/2023",
  );
  expect(screen.getByRole("group", { name: /^DEPOIS:/ })).toHaveTextContent(
    "DEPOISjul/2025 – jun/2026",
  );
});

it("marca a base parcial e não inventa o percentual ausente", async () => {
  respondWith({
    window: revenueWindow({
      status: "partial",
      incomplete_groups: 3,
      residual_brl: null,
      total_change_brl: null,
    }),
    diagnosis: revenueDiagnosis({
      status: "partial",
      volume_offset_percent: null,
    }),
  });
  renderBlock();

  await screen.findByRole("img", { name: /^Volume: −R\$\s402,00$/ });
  expect(screen.queryByText(/devolveu/)).toBeNull();
  const partial = screen.getByText("Base parcial: 3 grupos incompletos");
  expect(partial).toHaveClass("font-semibold");
  expect(partial.parentElement).toHaveTextContent(
    `Base parcial: 3 grupos incompletos · ${FOOTNOTE}`,
  );
  expect(partial.parentElement).toHaveClass("text-muted");
  expect(partial.parentElement).not.toHaveClass("font-semibold");
});

it("em base parcial, informa a base só no rodapé", async () => {
  respondWith({
    window: revenueWindow({
      status: "partial",
      incomplete_groups: 1,
      residual_brl: null,
    }),
    diagnosis: revenueDiagnosis({ status: "partial" }),
  });
  renderBlock();

  expect(
    await screen.findByText("O volume devolveu 37,2% do ganho de preço"),
  ).toBeVisible();
  expect(block()).not.toHaveTextContent("parcelas conhecidas");
  expect(
    screen.getByText("Base parcial: 1 grupo incompleto").parentElement,
  ).toHaveTextContent(`Base parcial: 1 grupo incompleto · ${FOOTNOTE}`);
});

it("mostra só o efeito que veio da API", async () => {
  respondWith({
    window: revenueWindow({
      status: "partial",
      incomplete_groups: 2,
      residual_brl: null,
      total_change_brl: null,
      components: { ...noComponents, preco: 1081 },
    }),
    diagnosis: revenueDiagnosis({ volume_offset_percent: null }),
  });
  renderBlock();

  await screen.findByRole("img", { name: /^Preço observado/ });
  expect(visibleText(headline())).toMatch(
    /^Preço observado adicionou R\$ 1,1 mil$/,
  );
  expect(screen.queryByRole("img", { name: /^Volume/ })).toBeNull();
  expect(block()).not.toHaveTextContent(/Indisponível|NaN|null/);
});

it("avisa quando há janelas, mas nenhum efeito ou percentual", async () => {
  respondWith({
    window: revenueWindow({
      status: "partial",
      incomplete_groups: 2,
      residual_brl: null,
      total_change_brl: null,
      components: noComponents,
    }),
    diagnosis: null,
  });
  renderBlock();

  expect(
    await screen.findByText(
      "Os efeitos de preço e volume não estão disponíveis neste recorte.",
    ),
  ).toBeVisible();
});

it.each([
  ["janela ausente", { window: null, diagnosis: null }],
  [
    "decomposição indisponível",
    {
      window: revenueWindow({
        status: "unavailable",
        windows: [],
        method: null,
        components: {},
        total_change_brl: null,
        residual_brl: null,
        group_count: 0,
      }),
      diagnosis: revenueDiagnosis({ status: "unavailable" }),
    },
  ],
])("mostra estado vazio com %s", async (_name, content) => {
  respondWith(content);
  renderBlock({ municipio: "Olinda" });

  expect(
    await within(block()).findByText(
      "Não há evidências suficientes para o diagnóstico deste recorte.",
    ),
  ).toBeVisible();
  expect(screen.queryByText(FOOTNOTE)).toBeNull();
  expect(screen.queryByRole("img")).toBeNull();
  expect(screen.queryByText(PERIOD_NOTE)).toBeNull();
  expect(screen.queryByText(/^Recorte:/)).toBeNull();
});

it("mantém o erro dentro do bloco e permite tentar novamente", async () => {
  const user = userEvent.setup();
  fetchMock.mockResolvedValueOnce(new Response("{}", { status: 500 }));
  renderBlock({ municipio: "Olinda" });

  const alert = await within(block()).findByRole("alert");
  expect(alert).toHaveTextContent(
    "Não foi possível consultar o diagnóstico comercial.",
  );
  expect(screen.queryByText(/^Recorte:/)).toBeNull();

  respondWith({});
  await user.click(
    within(alert).getByRole("button", { name: "Tentar novamente" }),
  );

  expect(await screen.findByText(FOOTNOTE)).toBeVisible();
  expect(screen.queryByRole("alert")).toBeNull();
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
});
