import { configure, render, screen, within } from "@testing-library/react";
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
} from "./revenue-diagnosis.test-support";

// A primeira renderização disputa a carga dos módulos com os demais workers.
configure({ asyncUtilTimeout: 4000 });

const GD_NOTE =
  "Comparação das mesmas UCs com ao menos seis pares mensais válidos. A relação com a data de conexão é observada; a Gold não mede energia gerada ou compensada e não comprova relação de causa entre GD e a redução.";
const CONCENTRATION_TITLE = "Onde a queda de volume se concentra";
const GD_TITLE = "Consumo por grupo de GD";
const INFO_NAME = "Sobre a comparação por grupo de GD";

const concentration = {
  dimension: "municipio",
  labels: ["RECIFE", "JABOATÃO DOS GUARARAPES"],
  share_negative_volume_percent: 69.5,
};
const gd = {
  status: "available",
  cohorts: [
    {
      group: "connected_between",
      uc_count: 1234,
      measured_energy_change_percent: -68.92,
    },
    {
      group: "connected_during",
      uc_count: 3,
      measured_energy_change_percent: null,
    },
    {
      group: "no_record",
      uc_count: 20000,
      measured_energy_change_percent: 0.46,
    },
  ],
  share_negative_volume_percent: 92.7,
  limitations: [],
};
const emptyGd = {
  status: "unavailable",
  cohorts: [],
  share_negative_volume_percent: null,
  limitations: [],
};
const fetchMock = vi.fn();

async function renderWith(
  diagnosis: Record<string, unknown> | null,
  scope = { municipio: "todos", classe: "todas" },
) {
  fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), "http://localhost:5173");
    return new Response(
      JSON.stringify(
        revenueResponse(url, { window: revenueWindow(), diagnosis }),
      ),
    );
  });
  render(
    <TestProviders>
      <PanoramaRevenueDiagnosis {...scope} latestPeriod="2026-06" />
    </TestProviders>,
  );
  await screen.findByRole("img", { name: /^Volume:/ });
}

const block = () =>
  screen.getByRole("region", { name: "Diagnóstico comercial" });
const card = (name: string) => screen.getByRole("region", { name });
const priceCard = () =>
  screen.getByRole("region", { name: /^Preço observado adicionou/ });
const cohortRows = () => within(block()).getAllByRole("listitem");

beforeEach(() => {
  resetGoldPublication();
  acceptGoldIdentity(PUBLICATION);
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

it("organiza um único bloco com dois sub-blocos em duas colunas", async () => {
  await renderWith(revenueDiagnosis({ concentration, gd }));

  expect(block()).toHaveClass("rounded-xl", "border", "bg-surface");
  expect(
    within(block())
      .getAllByRole("heading", { level: 3 })
      .map((heading) => heading.textContent),
  ).toEqual([
    expect.stringMatching(/^Preço observado adicionou/),
    CONCENTRATION_TITLE,
  ]);
  const columns = priceCard().parentElement;
  expect(columns).toHaveClass("grid", "md:grid-cols-2");
  expect(columns).not.toHaveClass("items-start");
  expect(columns).toContainElement(card(CONCENTRATION_TITLE));
  for (const panel of [priceCard(), card(CONCENTRATION_TITLE)])
    expect(panel).toHaveClass(
      "flex",
      "flex-col",
      "rounded-lg",
      "border",
      "bg-canvas/50",
    );
  expect(
    within(card(CONCENTRATION_TITLE)).getByRole("heading", {
      level: 4,
      name: GD_TITLE,
    }),
  ).toBeVisible();
});

it("mostra os dois destaques juntos, com os números e nomes da API", async () => {
  await renderWith(revenueDiagnosis({ concentration, gd }));

  const section = within(card(CONCENTRATION_TITLE));
  const first = section.getByText("69,5%");
  const second = section.getByText("92,7%");
  expect(first.parentElement!.parentElement).toBe(
    second.parentElement!.parentElement,
  );
  expect(first.parentElement).toHaveTextContent(
    "69,5%da queda de volume está em Recife e Jaboatão dos Guararapes",
  );
  expect(second.parentElement).toHaveTextContent(
    "92,7%da queda de volume está em UCs com conexão de GD",
  );
  for (const number of [first, second]) {
    expect(number).toHaveClass("text-content");
    expect(number.parentElement).toHaveClass("bg-selected");
    expect(number.parentElement!.outerHTML).not.toMatch(/danger|success/);
  }
});

it("distribui destaques e barras para o conteúdo da direita ocupar a altura toda", async () => {
  await renderWith(revenueDiagnosis({ concentration, gd }));

  const list = within(card(CONCENTRATION_TITLE)).getByRole("list");
  expect(list).toHaveClass("flex-1", "justify-between");
  expect(list.parentElement).toHaveClass("flex-1");
  expect(list.parentElement!.parentElement).toHaveClass("flex-1");
});

it("sem GD, esconde o destaque de GD e as barras e mantém a concentração", async () => {
  await renderWith(revenueDiagnosis({ concentration, gd: emptyGd }));

  const section = within(card(CONCENTRATION_TITLE));
  expect(section.getByText("69,5%")).toBeVisible();
  expect(section.queryByText(/UCs com conexão de GD/)).toBeNull();
  expect(section.queryByRole("list")).toBeNull();
  expect(screen.queryByRole("button", { name: INFO_NAME })).toBeNull();
});

it("sem participação nem concentração, mantém as barras sem o título da concentração", async () => {
  await renderWith(
    revenueDiagnosis({
      concentration: null,
      gd: { ...gd, share_negative_volume_percent: null },
    }),
  );

  expect(screen.queryByText(CONCENTRATION_TITLE)).toBeNull();
  expect(screen.getByText(GD_TITLE)).toBeVisible();
  expect(cohortRows()).toHaveLength(3);
});

it("sem concentração nem GD, some o sub-bloco e o da esquerda ocupa a largura", async () => {
  await renderWith(revenueDiagnosis({ concentration: null, gd: emptyGd }));

  expect(screen.queryByText(CONCENTRATION_TITLE)).toBeNull();
  expect(screen.queryByText(GD_TITLE)).toBeNull();
  expect(priceCard().parentElement).not.toHaveClass("md:grid-cols-2");
});

it("exibe os bairros que a API devolve ao filtrar por município", async () => {
  await renderWith(
    revenueDiagnosis({
      concentration: {
        dimension: "bairro",
        labels: ["BOA VIAGEM", "CASA AMARELA"],
        share_negative_volume_percent: 18.2,
      },
    }),
    { municipio: "RECIFE", classe: "todas" },
  );

  const [request] = fetchMock.mock.calls.map(
    ([input]) => new URL(String(input), "http://localhost:5173"),
  );
  expect(request.searchParams.get("municipio")).toBe("RECIFE");
  expect(
    screen.getByText("da queda de volume está em Boa Viagem e Casa Amarela"),
  ).toBeVisible();
  expect(screen.getByText("18,2%")).toBeVisible();
});

it("mostra um único grupo quando a API devolve só um", async () => {
  await renderWith(
    revenueDiagnosis({
      concentration: { ...concentration, labels: ["RECIFE"] },
    }),
  );

  expect(screen.getByText("da queda de volume está em Recife")).toBeVisible();
});

it("sem concentração, esconde só esse destaque e mantém o de GD e as barras", async () => {
  await renderWith(revenueDiagnosis({ concentration: null, gd }));

  const section = within(card(CONCENTRATION_TITLE));
  expect(section.queryByText("69,5%")).toBeNull();
  expect(section.getByText("92,7%")).toBeVisible();
  expect(section.getByText(GD_TITLE)).toBeVisible();
  expect(cohortRows()).toHaveLength(3);
  expect(screen.queryByRole("alert")).toBeNull();
});

it("deixa o title só nas colunas e nas datas, e nenhum número recebe foco", async () => {
  await renderWith(revenueDiagnosis({ concentration, gd }));

  const titled = Array.from(block().querySelectorAll("[title]")).map(
    (element) => element.getAttribute("aria-label"),
  );
  expect(titled).toHaveLength(5);
  expect(titled.slice(0, 2)).toEqual([
    expect.stringMatching(/^ANTES:/),
    expect.stringMatching(/^DEPOIS:/),
  ]);
  expect(titled.slice(2)).toEqual([
    expect.stringMatching(/^Preço observado:/),
    expect.stringMatching(/^Volume:/),
    expect.stringMatching(/^Saldo:/),
  ]);
  expect(block().querySelector("[tabindex]")).toBeNull();
  expect(screen.queryByRole("tooltip")).toBeNull();
});

it("mostra uma linha por grupo de GD, com UCs, barra e valor", async () => {
  await renderWith(revenueDiagnosis({ gd }));

  expect(screen.queryByRole("table")).toBeNull();
  const [between, , noRecord] = cohortRows();
  expect(between).toHaveTextContent(
    "Conexão de GD entre as janelas1.234 UCs−68,92%",
  );
  expect(noRecord).toHaveTextContent(
    "Sem registro de GD e com cadastro negativo20.000 UCs+0,46%",
  );
  const negative = within(between).getByRole("img", {
    name: "Conexão de GD entre as janelas: variação do consumo medido de −68,92%, 1.234 UCs",
  }).firstElementChild as HTMLElement;
  const positive = within(noRecord).getByRole("img", {
    name: /^Sem registro de GD.*\+0,46%/,
  }).firstElementChild as HTMLElement;
  expect(negative.style.width).toBe("100%");
  expect(negative).toHaveClass("bg-danger/50");
  expect(Number.parseFloat(positive.style.width)).toBeCloseTo(0.667, 2);
  expect(positive).toHaveClass("bg-success/50");
});

it("sem a participação da API, mantém as linhas e esconde só o destaque de GD", async () => {
  await renderWith(
    revenueDiagnosis({
      gd: { ...gd, share_negative_volume_percent: null },
    }),
  );

  expect(screen.queryByText(/da queda de volume está em UCs/)).toBeNull();
  expect(cohortRows()).toHaveLength(3);
});

it("destaca o nome do grupo em peso médio, as UCs em cor secundária e a variação em semibold", async () => {
  await renderWith(revenueDiagnosis({ gd }));

  const row = within(cohortRows()[0]);
  expect(row.getByText("Conexão de GD entre as janelas")).toHaveClass(
    "font-medium",
    "text-content",
  );
  expect(row.getByText("1.234 UCs")).toHaveClass("text-muted");
  expect(row.getByText("−68,92%")).toHaveClass("font-semibold", "text-content");
});

it("mostra Base insuficiente, sem barra, quando a API não traz a variação", async () => {
  await renderWith(revenueDiagnosis({ gd }));

  const row = cohortRows()[1];
  expect(row).toHaveTextContent(
    "Conexão de GD na janela final3 UCsBase insuficiente",
  );
  expect(within(row).queryByRole("img")).toBeNull();
});

it.each([
  ["grupos vazios", revenueDiagnosis({ concentration, gd: emptyGd })],
  ["diagnóstico ausente", null],
])("esconde só a parte de GD com %s", async (_name, diagnosis) => {
  await renderWith(diagnosis);

  expect(screen.queryByText(GD_TITLE)).toBeNull();
  expect(
    screen.queryByRole("button", { name: INFO_NAME }),
  ).not.toBeInTheDocument();
  expect(screen.queryByRole("alert")).toBeNull();
  expect(screen.getByRole("img", { name: /^Volume/ })).toBeVisible();
});

it("abre a nota de GD pelo botão de informação, usando só o teclado", async () => {
  const user = userEvent.setup();
  await renderWith(revenueDiagnosis({ gd }));

  const info = screen.getByRole("button", { name: INFO_NAME });
  expect(screen.queryByText(GD_NOTE)).toBeNull();
  expect(info).toHaveAttribute("aria-expanded", "false");

  await user.tab();
  expect(info).toHaveFocus();
  await user.keyboard("{Enter}");
  expect(screen.getByText(GD_NOTE)).toBeVisible();
  expect(info).toHaveAttribute("aria-expanded", "true");
  expect(document.getElementById(info.getAttribute("aria-controls")!)).toBe(
    screen.getByText(GD_NOTE),
  );

  await user.keyboard("{Escape}");
  expect(screen.queryByText(GD_NOTE)).toBeNull();
  expect(info).toHaveFocus();

  await user.keyboard(" ");
  expect(screen.getByText(GD_NOTE)).toBeVisible();
  await user.tab();
  expect(screen.queryByText(GD_NOTE)).toBeNull();
});

it("não usa article nem linguagem causal no bloco inteiro, com a nota aberta", async () => {
  const user = userEvent.setup();
  await renderWith(revenueDiagnosis({ concentration, gd }));
  await user.click(screen.getByRole("button", { name: INFO_NAME }));
  expect(screen.getByText(GD_NOTE)).toBeVisible();

  expect(screen.queryByRole("article")).toBeNull();
  const labels = Array.from(block().querySelectorAll("[aria-label], [title]"))
    .flatMap((element) => [
      element.getAttribute("aria-label"),
      element.getAttribute("title"),
    ])
    .filter(Boolean);
  expect(`${block().textContent} ${labels.join(" ")}`).not.toMatch(
    /porque|devido a|causou|por causa de|em razão de|reduziu o ganho|anulou/i,
  );
});

it("usa só as cores semânticas suaves e neutros", async () => {
  await renderWith(revenueDiagnosis({ concentration, gd }));

  const classes = new Set(
    Array.from(block().querySelectorAll("*")).flatMap((element) =>
      Array.from(element.classList),
    ),
  );
  const colored = [...classes].filter((name) =>
    /success|danger|warning|brand|goiaba|pistache/.test(name),
  );
  expect(colored.filter((name) => !name.includes("outline")).sort()).toEqual([
    "bg-danger/50",
    "bg-success/50",
    "bg-success/70",
    "text-[var(--status-success-text)]",
  ]);
});
