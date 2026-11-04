import type { VisualEvidenceData } from "./VisualEvidence";

function cell(value: string) {
  const safe = /^[\s]*[=+@\-\t\r]/.test(value) ? `'${value}` : value;
  return `"${safe.replaceAll('"', '""')}"`;
}
export function chartCsv(data: VisualEvidenceData) {
  const points = data.tablePoints ?? data.points;
  const shares = points.some((p) => p.percentage != null);
  const rows = [
    ["Indicador", data.title],
    ["Recorte", data.scope],
    ["Unidade", data.unit],
    ["Fonte", data.isDemo ? "Dados de demonstração" : "Dados internos"],
    ...(data.note ? [["Alcance e observações", data.note]] : []),
    [
      data.categoryLabel ?? "Período",
      "Valor",
      ...(shares ? ["Participação (%)"] : []),
    ],
  ].map((row) => row.map(cell).join(";"));
  // Numeric cells are generated from finite numbers, not untrusted strings.
  for (const p of points)
    rows.push(
      `${cell(p.label)};${p.value === null ? "" : String(p.value).replace(".", ",")}${shares ? `;${p.percentage == null ? "" : String(p.percentage).replace(".", ",")}` : ""}`,
    );
  return `\uFEFF${rows.join("\r\n")}\r\n`;
}
function save(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function exportChartCsv(data: VisualEvidenceData) {
  save(
    new Blob([chartCsv(data)], { type: "text/csv;charset=utf-8" }),
    "dados-do-recorte.csv",
  );
}
export async function exportChartPng(
  svg: SVGSVGElement,
  data: VisualEvidenceData,
  canExport: () => boolean | Promise<boolean>,
) {
  const clone = svg.cloneNode(true) as SVGSVGElement;
  const computed = getComputedStyle(svg);
  const colors = {
    "var(--accent-goiaba)": computed.getPropertyValue("--accent-goiaba"),
    "var(--accent-pistache)": computed.getPropertyValue("--accent-pistache"),
    "var(--line)": computed.getPropertyValue("--line"),
    currentColor: computed.color,
  };
  for (const node of [clone, ...clone.querySelectorAll("*")]) {
    for (const attr of ["fill", "stroke"]) {
      const value = node.getAttribute(attr);
      if (value && value in colors)
        node.setAttribute(attr, colors[value as keyof typeof colors].trim());
    }
  }
  const exportViewBox = svg.getAttribute("data-export-viewbox");
  if (exportViewBox) clone.setAttribute("viewBox", exportViewBox);
  for (const node of clone.querySelectorAll<SVGElement>("[data-export-only]"))
    node.style.display = "inline";
  clone.setAttribute("font-family", "Arial, sans-serif");
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  const imageWidth = Math.max(
    1200,
    Math.min(3600, clone.viewBox.baseVal.width),
  );
  clone.setAttribute("width", String(imageWidth));
  const chartHeight = Math.round(
    (imageWidth * clone.viewBox.baseVal.height) / clone.viewBox.baseVal.width,
  );
  clone.setAttribute("height", String(chartHeight));
  const url = URL.createObjectURL(
    new Blob([new XMLSerializer().serializeToString(clone)], {
      type: "image/svg+xml",
    }),
  );
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas indisponível");
    const lines = (text: string, font: string) => {
      ctx.font = font;
      const result: string[] = [""];
      for (const word of text.split(/\s+/)) {
        const last = result.length - 1;
        const candidate = `${result[last]}${result[last] ? " " : ""}${word}`;
        if (ctx.measureText(candidate).width > imageWidth - 80 && result[last])
          result.push(word);
        else result[last] = candidate;
      }
      return result;
    };
    const titles = lines(data.title, "600 28px Arial, sans-serif");
    const scopes = lines(data.scope, "20px Arial, sans-serif");
    const notes = data.note ? lines(data.note, "20px Arial, sans-serif") : [];
    const headerHeight = 30 + titles.length * 34 + scopes.length * 28;
    const footerHeight = 65 + notes.length * 28;
    canvas.width = imageWidth;
    canvas.height = headerHeight + chartHeight + footerHeight;
    ctx.fillStyle =
      computed.getPropertyValue("--bg-surface").trim() || "#fffcf6";
    ctx.fillRect(0, 0, imageWidth, canvas.height);
    ctx.fillStyle = computed.color;
    ctx.font = "600 28px sans-serif";
    titles.forEach((line, i) => ctx.fillText(line, 40, 38 + i * 34));
    ctx.font = "20px sans-serif";
    scopes.forEach((line, i) =>
      ctx.fillText(line, 40, 38 + titles.length * 34 + i * 28),
    );
    ctx.drawImage(image, 0, headerHeight, imageWidth, chartHeight);
    ctx.fillText(
      data.isDemo ? "Dados de demonstração" : "Fonte de dados interna",
      40,
      headerHeight + chartHeight + 35,
    );
    notes.forEach((line, i) =>
      ctx.fillText(line, 40, headerHeight + chartHeight + 65 + i * 28),
    );
    const blob = await new Promise<Blob>((resolve, reject) =>
      canvas.toBlob(
        (b) => (b ? resolve(b) : reject(new Error("PNG indisponível"))),
        "image/png",
      ),
    );
    if (!(await canExport())) throw new Error("Contexto alterado");
    save(blob, "grafico-do-recorte.png");
  } finally {
    URL.revokeObjectURL(url);
  }
}
