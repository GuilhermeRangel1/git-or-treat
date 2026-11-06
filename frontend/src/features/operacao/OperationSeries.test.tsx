import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import OperationSeries from "./OperationSeries";

const period = {
  start: "2025-01",
  end: "2025-03",
  granularity: "month" as const,
};

it("mantém zero conhecido, lacuna indisponível e abre a tabela do período", async () => {
  const user = userEvent.setup();
  render(
    <OperationSeries
      period={period}
      series={[
        {
          period: { start: "2024-12", end: "2024-12", granularity: "month" },
          status: "available",
          dec_hours_per_uc: 4,
          fec_interruptions_per_uc: 3,
          denominator_uc_count: 10,
        },
        {
          period: { start: "2025-01", end: "2025-01", granularity: "month" },
          status: "available",
          dec_hours_per_uc: 0,
          fec_interruptions_per_uc: 0,
          denominator_uc_count: 10,
        },
        {
          period: { start: "2025-03", end: "2025-03", granularity: "month" },
          status: "empty",
          dec_hours_per_uc: null,
          fec_interruptions_per_uc: null,
          denominator_uc_count: 0,
        },
        {
          period: { start: "2025-04", end: "2025-04", granularity: "month" },
          status: "available",
          dec_hours_per_uc: 2,
          fec_interruptions_per_uc: 1,
          denominator_uc_count: 10,
        },
      ]}
    />,
  );

  const dec = screen.getByRole("region", { name: "Série mensal de DEC" });
  expect(dec).toHaveTextContent("Jan/2025: 0 h/UC");
  expect(dec).toHaveTextContent("Fev/2025: indisponível");
  expect(dec).toHaveTextContent("Mar/2025: indisponível");
  expect(dec).not.toHaveTextContent("Dez/2024");
  expect(dec).not.toHaveTextContent("Abr/2025");
  expect(dec.querySelectorAll(".operation-series__point")).toHaveLength(1);

  await user.click(
    screen.getAllByRole("button", { name: "Ver tabela da série →" })[0]!,
  );
  const table = await screen.findByRole("table", {
    name: "Série mensal de DEC simplificado",
  });
  expect(
    within(table).getByRole("row", { name: /Jan\/2025/ }),
  ).toHaveTextContent("0");
  expect(
    within(table).getByRole("row", { name: /Fev\/2025/ }),
  ).toHaveTextContent("Indisponível");
  expect(
    within(table).getByRole("row", { name: /Mar\/2025/ }),
  ).toHaveTextContent("Indisponível");
  expect(
    within(table).getByRole("row", { name: /Mar\/2025/ }),
  ).toHaveTextContent("0 · inválida");
  expect(
    within(table).queryByRole("row", { name: /Dez\/2024|Abr\/2025/ }),
  ).not.toBeInTheDocument();
});

it("destaca piora em vermelho e melhora em verde, com triângulo e texto além da cor", async () => {
  const user = userEvent.setup();
  const month = (start: string, dec: number, fec: number) => ({
    period: { start, end: start, granularity: "month" as const },
    status: "available" as const,
    dec_hours_per_uc: dec,
    fec_interruptions_per_uc: fec,
    denominator_uc_count: 10,
  });
  render(
    <OperationSeries
      period={period}
      series={[
        month("2025-01", 1, 1),
        month("2025-02", 2, 1),
        month("2025-03", 1.5, 1),
      ]}
    />,
  );

  const dec = screen.getByRole("region", { name: "Série mensal de DEC" });
  // Jan não tem mês anterior; Fev subiu (pior); Mar caiu (melhor).
  expect(dec).toHaveTextContent(
    "Fev/2025: 2 h/UC (piorou 100% em relação ao mês anterior)",
  );
  expect(dec).toHaveTextContent(
    "Mar/2025: 1,5 h/UC (melhorou 25% em relação ao mês anterior)",
  );
  expect(dec).not.toHaveTextContent("Jan/2025: 1 h/UC (");

  const triangles = dec.querySelectorAll("polygon");
  expect(triangles).toHaveLength(2);
  expect(triangles[0]).toHaveClass("fill-danger");
  expect(triangles[1]).toHaveClass("fill-success");
  expect(dec.querySelectorAll(".operation-series__point")).toHaveLength(3);
  expect(dec.querySelectorAll("path.stroke-danger")).toHaveLength(1);
  expect(dec.querySelectorAll("path.stroke-success")).toHaveLength(1);

  // FEC ficou igual nos três meses: sem triângulos, linhas neutras.
  const fec = screen.getByRole("region", { name: "Série mensal de FEC" });
  expect(fec.querySelectorAll("polygon")).toHaveLength(0);
  expect(fec.querySelectorAll("path.stroke-danger")).toHaveLength(0);
  expect(fec.querySelectorAll("path.stroke-success")).toHaveLength(0);

  const legend = within(dec).getByRole("list", {
    name: "Legenda de cores do gráfico",
  });
  expect(legend).toHaveTextContent("Piorou em relação ao mês anterior");
  expect(legend).toHaveTextContent("Melhorou em relação ao mês anterior");
  expect(legend).toHaveTextContent("Em DEC e FEC, valor maior é pior.");

  await user.hover(
    within(dec).getByRole("img", { name: /^Exibir Fev\/2025, DEC 2 h\/UC/ }),
  );
  expect(within(dec).getByRole("tooltip")).toHaveTextContent(
    "▲ +100% vs mês anterior",
  );
});
