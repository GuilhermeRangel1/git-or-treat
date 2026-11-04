export const filterLabels: Record<string, string> = {
  municipio: "Município",
  bairro: "Bairro",
  classe: "Classe",
  alimentador: "Alimentador",
};
export function queueQuery(params: URLSearchParams): {
  request: string;
  detail: string | null;
} {
  const request = new URLSearchParams();
  const allowed = [
    "page",
    "page_size",
    "order_by",
    "direction",
    "uc",
    ...Object.keys(filterLabels),
  ];
  for (const key of params.keys()) {
    if (!allowed.includes(key) || params.getAll(key).length !== 1)
      throw new Error(
        "Parâmetros de inspeção inválidos. Limpe os filtros para continuar.",
      );
  }
  for (const key of Object.keys(filterLabels)) {
    const value = params.get(key);
    if (value !== null) {
      if (!value.trim() || value.length > 100)
        throw new Error("Filtro inválido.");
      request.set(key, value);
    }
  }
  const page = params.get("page") ?? "1",
    size = params.get("page_size") ?? "10";
  if (
    !/^[1-9]\d*$/.test(page) ||
    !Number.isSafeInteger(Number(page)) ||
    !/^[1-9]\d*$/.test(size) ||
    Number(size) > 100
  )
    throw new Error("Paginação inválida.");
  const order = params.get("order_by"),
    direction = params.get("direction");
  if (
    (order !== null &&
      ![
        "priority",
        "uc_id",
        "potential_recoverable_energy_kwh",
        "category",
        "queue_position",
      ].includes(order)) ||
    (direction !== null && !["asc", "desc"].includes(direction))
  )
    throw new Error("Ordenação inválida.");
  request.set("page", page);
  request.set("page_size", size);
  if (order !== null) request.set("order_by", order);
  if (direction !== null) request.set("direction", direction);
  const detail = params.get("uc");
  if (detail !== null && !/^[A-Za-z0-9-]{1,60}$/.test(detail))
    throw new Error("UC inválida.");
  return { request: request.toString(), detail };
}
