import type { UCHistorySection } from "./uc360-state";

export const UC_STATES = [
  "available",
  "empty",
  "partial",
  "unavailable",
] as const;
export type UCStatus = (typeof UC_STATES)[number];

export type UCSource = {
  kind: string;
  version: string;
  is_demo: boolean;
  updated_at: string;
};
export type UCPeriod = { start: string; end: string; granularity: "month" };
export type UCMetadata = {
  contract_version: "1.1.0";
  status: UCStatus;
  period: UCPeriod;
  filters: Record<string, unknown>;
  source: UCSource;
  limitations: string[];
};
export type UCMeter = {
  meter_id: string;
  installed_at: string;
  removed_at: string | null;
};
export type UCProfile = {
  uc_id: string;
  customer_reference: string | null;
  customer_name: string | null;
  municipio: string;
  bairro: string;
  classe: string;
  alimentador: string;
  status: string;
};
export type UCMeasure = {
  value: number | null;
  status: UCStatus;
  limitations: string[];
};
export type UCChange = {
  delta: number | null;
  percent_change: number | null;
  status: UCStatus;
  limitations: string[];
};
export type UCOverview = {
  data: {
    profile: UCProfile;
    period: UCPeriod;
    comparison: {
      initial: {
        competencia: string;
        measured_energy_kwh: UCMeasure;
        billed_energy_kwh: UCMeasure;
        billed_amount: UCMeasure;
        paid_amount: UCMeasure;
      };
      final: {
        competencia: string;
        measured_energy_kwh: UCMeasure;
        billed_energy_kwh: UCMeasure;
        billed_amount: UCMeasure;
        paid_amount: UCMeasure;
      };
      measured_energy_kwh: UCChange;
      billed_energy_kwh: UCChange;
      billed_amount: UCChange;
      paid_amount: UCChange;
    };
    open_invoices: {
      count: number | null;
      status: UCStatus;
      limitations: string[];
    };
    current_meter: {
      item: UCMeter | null;
      status: UCStatus;
      limitations: string[];
    };
    distributed_generation: {
      items: Array<{ capacity_kw: number; status: string }>;
      status: UCStatus;
      limitations: string[];
    };
    section_status: Record<string, UCStatus>;
  };
  metadata: UCMetadata;
};
export type UCSearchItem = {
  uc_id: string;
  municipio: string;
  bairro: string;
  classe: string;
  alimentador: string;
  status: string;
};
export type UCSearchResponse = {
  data: { items: UCSearchItem[] };
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
  metadata: { status: UCStatus };
};
export type UCConsumptionItem = Record<string, unknown> & {
  competencia: string;
  measured_energy_kwh: number | null;
  status: UCStatus;
};
export type UCInvoiceItem = Record<string, unknown> & {
  invoice_id: string;
  competencia: string;
  billed_amount: number | null;
  paid_amount: number | null;
  billed_energy_kwh: number | null;
  due_date: string | null;
  payment_date: string | null;
  payment_status: "paid" | "partial" | "unpaid" | "unknown";
  currency_unit: "BRL";
};
export type UCMeterHistoryItem = Record<string, unknown> & {
  meter_id: string;
  installed_at: string;
  removed_at: string | null;
};
export type UCGenerationItem = Record<string, unknown> & {
  capacity_kw: number;
  status: string;
};
export type UCInterruptionItem = Record<string, unknown> & {
  event_id: string;
  feeder_id: string;
  competencia: string;
  duration_hours: number;
};
export type UCCallItem = Record<string, unknown> & {
  call_id: string;
  opened_at: string;
  category: string;
};
export type UCHistoryItem =
  | UCConsumptionItem
  | UCInvoiceItem
  | UCMeterHistoryItem
  | UCGenerationItem
  | UCInterruptionItem
  | UCCallItem;
export type UCHistory = {
  data: { items: UCHistoryItem[] };
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
  metadata: UCMetadata;
};

export class UCContractError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "UCContractError";
  }
}
type Obj = Record<string, unknown>;
function obj(value: unknown, path: string): Obj {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new UCContractError(`${path} deve ser objeto.`);
  return value as Obj;
}
function str(value: unknown, path: string): string {
  if (typeof value !== "string")
    throw new UCContractError(`${path} deve ser texto.`);
  return value;
}
function n(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isFinite(value))
    throw new UCContractError(`${path} deve ser número finito.`);
  return value;
}
function nullableN(value: unknown, path: string): number | null {
  return value === null ? null : n(value, path);
}
function strings(value: unknown, path: string): string[] {
  if (!Array.isArray(value))
    throw new UCContractError(`${path} deve ser lista.`);
  return value.map((item, i) => str(item, `${path}[${i}]`));
}
function state(value: unknown, path: string): UCStatus {
  if (!(UC_STATES as readonly unknown[]).includes(value))
    throw new UCContractError(`${path} contém estado inválido.`);
  return value as UCStatus;
}
function month(value: unknown, path: string) {
  const parsed = str(value, path);
  if (!/^(?!0000)\d{4}-(0[1-9]|1[0-2])$/.test(parsed))
    throw new UCContractError(`${path} deve usar YYYY-MM.`);
  return parsed;
}
function period(value: unknown, path: string): UCPeriod {
  const input = obj(value, path);
  if (input.granularity !== "month")
    throw new UCContractError(`${path}.granularity inválida.`);
  const start = month(input.start, `${path}.start`);
  const end = month(input.end, `${path}.end`);
  if (start > end) throw new UCContractError(`${path} está invertido.`);
  return { start, end, granularity: "month" };
}
function meta(value: unknown, path: string): UCMetadata {
  const input = obj(value, path);
  if (input.contract_version !== "1.1.0")
    throw new UCContractError(`${path}.contract_version incompatível.`);
  const source = obj(input.source, `${path}.source`);
  if (typeof source.is_demo !== "boolean")
    throw new UCContractError(`${path}.source.is_demo inválido.`);
  return {
    contract_version: "1.1.0",
    status: state(input.status, `${path}.status`),
    period: period(input.period, `${path}.period`),
    filters: obj(input.filters, `${path}.filters`),
    source: {
      kind: str(source.kind, "source.kind"),
      version: str(source.version, "source.version"),
      is_demo: source.is_demo,
      updated_at: str(source.updated_at, "source.updated_at"),
    },
    limitations: strings(input.limitations, `${path}.limitations`),
  };
}
function measure(value: unknown, path: string): UCMeasure {
  const input = obj(value, path);
  const status = state(input.status, `${path}.status`);
  const number = nullableN(input.value, `${path}.value`);
  if (status === "available" && number === null)
    throw new UCContractError(`${path}.value deve existir quando disponível.`);
  if ((status === "empty" || status === "unavailable") && number !== null)
    throw new UCContractError(`${path}.value não corresponde ao estado.`);
  return {
    value: number,
    status,
    limitations: strings(input.limitations, `${path}.limitations`),
  };
}
function change(value: unknown, path: string): UCChange {
  const input = obj(value, path);
  const status = state(input.status, `${path}.status`);
  const delta = nullableN(input.delta, `${path}.delta`);
  const percent = nullableN(input.percent_change, `${path}.percent_change`);
  if (
    (status === "available" && delta === null) ||
    ((status === "empty" || status === "unavailable") &&
      (delta !== null || percent !== null)) ||
    (delta === null && percent !== null)
  )
    throw new UCContractError(`${path}.delta não corresponde ao estado.`);
  return {
    delta,
    percent_change: percent,
    status,
    limitations: strings(input.limitations, `${path}.limitations`),
  };
}
function profile(value: unknown): UCProfile {
  const p = obj(value, "data.profile");
  for (const key of ["customer_reference", "customer_name"] as const)
    if (p[key] !== null && typeof p[key] !== "string")
      throw new UCContractError(`data.profile.${key} deve ser texto ou null.`);
  return {
    uc_id: str(p.uc_id, "profile.uc_id"),
    customer_reference: p.customer_reference as string | null,
    customer_name: p.customer_name as string | null,
    municipio: str(p.municipio, "profile.municipio"),
    bairro: str(p.bairro, "profile.bairro"),
    classe: str(p.classe, "profile.classe"),
    alimentador: str(p.alimentador, "profile.alimentador"),
    status: str(p.status, "profile.status"),
  };
}
function meter(value: unknown, path: string): UCMeter {
  const m = obj(value, path);
  const removed = m.removed_at;
  if (removed !== null && typeof removed !== "string")
    throw new UCContractError(`${path}.removed_at inválido.`);
  return {
    meter_id: str(m.meter_id, `${path}.meter_id`),
    installed_at: str(m.installed_at, `${path}.installed_at`),
    removed_at: removed as string | null,
  };
}
export function decodeUCOverview(value: unknown): UCOverview {
  const root = obj(value, "response"),
    data = obj(root.data, "data"),
    cmp = obj(data.comparison, "comparison");
  const snapshot = (raw: unknown, path: string) => {
    const s = obj(raw, path);
    return {
      competencia: month(s.competencia, `${path}.competencia`),
      measured_energy_kwh: measure(
        s.measured_energy_kwh,
        `${path}.measured_energy_kwh`,
      ),
      billed_energy_kwh: measure(
        s.billed_energy_kwh,
        `${path}.billed_energy_kwh`,
      ),
      billed_amount: measure(s.billed_amount, `${path}.billed_amount`),
      paid_amount: measure(s.paid_amount, `${path}.paid_amount`),
    };
  };
  const open = obj(data.open_invoices, "open_invoices"),
    current = obj(data.current_meter, "current_meter"),
    gd = obj(data.distributed_generation, "distributed_generation"),
    statuses = obj(data.section_status, "section_status");
  if (!Array.isArray(gd.items))
    throw new UCContractError("distributed_generation.items deve ser lista.");
  const section_status = Object.fromEntries(
    Object.entries(statuses).map(([key, value]) => [
      key,
      state(value, `section_status.${key}`),
    ]),
  );
  const count = nullableN(open.count, "open_invoices.count");
  if (count !== null && (!Number.isInteger(count) || count < 0))
    throw new UCContractError("open_invoices.count inválido.");
  if (
    (open.status === "unavailable" && count !== null) ||
    (open.status === "available" && count === null)
  )
    throw new UCContractError("open_invoices.count não corresponde ao estado.");
  const item =
    current.item === null ? null : meter(current.item, "current_meter.item");
  return {
    data: {
      profile: profile(data.profile),
      period: period(data.period, "data.period"),
      comparison: {
        initial: snapshot(cmp.initial, "comparison.initial"),
        final: snapshot(cmp.final, "comparison.final"),
        measured_energy_kwh: change(
          cmp.measured_energy_kwh,
          "comparison.measured_energy_kwh",
        ),
        billed_energy_kwh: change(
          cmp.billed_energy_kwh,
          "comparison.billed_energy_kwh",
        ),
        billed_amount: change(cmp.billed_amount, "comparison.billed_amount"),
        paid_amount: change(cmp.paid_amount, "comparison.paid_amount"),
      },
      open_invoices: {
        count,
        status: state(open.status, "open_invoices.status"),
        limitations: strings(open.limitations, "open_invoices.limitations"),
      },
      current_meter: {
        item,
        status: state(current.status, "current_meter.status"),
        limitations: strings(current.limitations, "current_meter.limitations"),
      },
      distributed_generation: {
        items: gd.items.map((raw, index) => {
          const item = obj(raw, `generation[${index}]`);
          return {
            capacity_kw: n(
              item.capacity_kw,
              `generation[${index}].capacity_kw`,
            ),
            status: str(item.status, `generation[${index}].status`),
          };
        }),
        status: state(gd.status, "generation.status"),
        limitations: strings(gd.limitations, "generation.limitations"),
      },
      section_status,
    },
    metadata: meta(root.metadata, "metadata"),
  };
}
export function decodeUCSearch(value: unknown): UCSearchResponse {
  const root = obj(value, "response"),
    data = obj(root.data, "data"),
    p = obj(root.pagination, "pagination"),
    m = obj(root.metadata, "metadata");
  if (!Array.isArray(data.items))
    throw new UCContractError("data.items deve ser lista.");
  const integer = (x: unknown, path: string) => {
    const value = n(x, path);
    if (!Number.isInteger(value) || value < 0)
      throw new UCContractError(`${path} inválido.`);
    return value;
  };
  return {
    data: {
      items: data.items.map((raw, index) => {
        const item = obj(raw, `items[${index}]`);
        return {
          uc_id: str(item.uc_id, "uc_id"),
          municipio: str(item.municipio, "municipio"),
          bairro: str(item.bairro, "bairro"),
          classe: str(item.classe, "classe"),
          alimentador: str(item.alimentador, "alimentador"),
          status: str(item.status, "status"),
        };
      }),
    },
    pagination: {
      page: integer(p.page, "page"),
      page_size: integer(p.page_size, "page_size"),
      total: integer(p.total, "total"),
      total_pages: integer(p.total_pages, "total_pages"),
    },
    metadata: { status: state(m.status, "metadata.status") },
  };
}
export function decodeUCHistory(
  value: unknown,
  section: UCHistorySection,
): UCHistory {
  const root = obj(value, "response"),
    data = obj(root.data, "data"),
    p = obj(root.pagination, "pagination");
  if (!Array.isArray(data.items))
    throw new UCContractError("data.items deve ser lista.");
  const integer = (x: unknown, path: string) => {
    const value = n(x, path);
    if (!Number.isInteger(value) || value < 0)
      throw new UCContractError(`${path} inválido.`);
    return value;
  };
  const items = data.items.map((raw, index) => {
    const item = obj(raw, `items[${index}]`);
    const required = (key: string) => {
      if (!(key in item))
        throw new UCContractError(`items[${index}].${key} ausente.`);
    };
    const text = (key: string) => {
      required(key);
      return str(item[key], `items[${index}].${key}`);
    };
    const number = (key: string) => {
      required(key);
      return n(item[key], `items[${index}].${key}`);
    };
    const nullableNumber = (key: string) => {
      required(key);
      return nullableN(item[key], `items[${index}].${key}`);
    };
    switch (section) {
      case "consumption":
        text("competencia");
        month(item.competencia, `items[${index}].competencia`);
        const measuredEnergy = nullableNumber("measured_energy_kwh");
        const consumptionStatus = state(item.status, `items[${index}].status`);
        if (
          (consumptionStatus === "available" && measuredEnergy === null) ||
          ((consumptionStatus === "partial" ||
            consumptionStatus === "unavailable") &&
            measuredEnergy !== null)
        )
          throw new UCContractError(
            `items[${index}] tem status incompatível com measured_energy_kwh.`,
          );
        break;
      case "invoices":
        text("invoice_id");
        text("competencia");
        month(item.competencia, `items[${index}].competencia`);
        nullableNumber("billed_amount");
        nullableNumber("paid_amount");
        nullableNumber("billed_energy_kwh");
        if (
          !["paid", "partial", "unpaid", "unknown"].includes(
            text("payment_status"),
          )
        )
          throw new UCContractError(`items[${index}].payment_status inválido.`);
        if (item.currency_unit !== "BRL")
          throw new UCContractError(
            `items[${index}].currency_unit deve ser BRL.`,
          );
        for (const key of ["due_date", "payment_date"]) {
          required(key);
          if (item[key] !== null) text(key);
        }
        break;
      case "meters":
        text("meter_id");
        text("installed_at");
        required("removed_at");
        if (item.removed_at !== null) text("removed_at");
        break;
      case "distributed_generation":
        number("capacity_kw");
        text("status");
        break;
      case "interruptions":
        text("event_id");
        text("feeder_id");
        text("competencia");
        month(item.competencia, `items[${index}].competencia`);
        number("duration_hours");
        break;
      case "calls":
        text("call_id");
        text("opened_at");
        text("category");
        break;
    }
    return item as unknown as UCHistoryItem;
  });
  return {
    data: {
      items,
    },
    pagination: {
      page: integer(p.page, "page"),
      page_size: integer(p.page_size, "page_size"),
      total: integer(p.total, "total"),
      total_pages: integer(p.total_pages, "total_pages"),
    },
    metadata: meta(root.metadata, "metadata"),
  };
}
