import {
  decodeGoldMetadata,
  isGoldMetadata,
} from "@/shared/analytics/goldContract";
import {
  acceptGoldPublication,
  getGoldGeneration,
  markGoldPublicationStale,
  withGoldPublication,
} from "@/shared/analytics/goldPublication";
import {
  captureAuthorizationGeneration,
  currentAuthorizationGeneration,
  getAccessToken,
  hasAccessTokenProvider,
  isReauthenticationRequired,
  notifyUnauthorized,
} from "@/shared/auth/authorization";

type ApiErrorKind =
  "http" | "network" | "invalid-response" | "configuration" | "session-changed";

export class ApiError extends Error {
  status: number;
  data: unknown;
  kind: ApiErrorKind;
  constructor(
    message: string,
    status: number,
    data: unknown = undefined,
    kind: ApiErrorKind = "http",
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
    this.kind = kind;
  }
}

function apiBaseUrl() {
  const configured = import.meta.env.VITE_API_URL?.trim();
  if (configured) return configured.replace(/\/$/, "");
  if (import.meta.env.DEV) return "";
  throw new ApiError(
    "VITE_API_URL não foi configurada.",
    0,
    undefined,
    "configuration",
  );
}

function isAborted(error: unknown, signal: AbortSignal | null | undefined) {
  return (
    signal?.aborted || (error instanceof Error && error.name === "AbortError")
  );
}

/** Transporte JSON. T informa o tipo esperado; contratos/decodificação pertencem ao domínio. */
export async function apiClient<T = unknown>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  if (isReauthenticationRequired()) {
    throw new ApiError("Renove a sessão antes de continuar.", 401);
  }
  const authorizationGeneration = captureAuthorizationGeneration();
  const analytic =
    (!options.method || options.method === "GET") &&
    /^\/api\/v1\/(panorama(?:\?|$)|operations\/|inspections\/queue(?:\/|\?|$))/.test(
      endpoint,
    );
  const requestGeneration = getGoldGeneration();
  if (analytic) {
    const [path, search] = endpoint.split("?");
    const params = withGoldPublication(new URLSearchParams(search));
    endpoint = `${path}${params.size ? `?${params}` : ""}`;
  }
  const url = `${apiBaseUrl()}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
  const headers = new Headers(options.headers);
  const authenticatedSession = hasAccessTokenProvider();
  const accessToken = await getAccessToken();
  if (authorizationGeneration !== currentAuthorizationGeneration()) {
    throw new ApiError(
      "A sessão mudou durante a solicitação.",
      0,
      undefined,
      "session-changed",
    );
  }
  if (authenticatedSession && !accessToken) {
    notifyUnauthorized();
    throw new ApiError("Renove a sessão antes de continuar.", 401);
  }
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  if (typeof options.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  let raw: string;
  try {
    response = await fetch(url, { ...options, headers });
    raw = await response.text();
  } catch (error) {
    if (isAborted(error, options.signal)) throw error;
    throw new ApiError(
      "Não foi possível concluir a solicitação.",
      0,
      undefined,
      "network",
    );
  }
  if (authorizationGeneration !== currentAuthorizationGeneration()) {
    throw new ApiError(
      "A sessão mudou durante a solicitação.",
      0,
      undefined,
      "session-changed",
    );
  }

  let data: unknown = undefined;
  if (raw) {
    try {
      data = JSON.parse(raw);
    } catch {
      if (response.ok) {
        throw new ApiError(
          "Resposta inválida do serviço.",
          response.status,
          raw,
          "invalid-response",
        );
      }
      data = raw;
    }
  }

  if (!response.ok) {
    if (response.status === 401 && authenticatedSession) notifyUnauthorized();
    if (analytic && response.status === 409) markGoldPublicationStale();
    const detail =
      data && typeof data === "object" && "detail" in data
        ? data.detail
        : undefined;
    throw new ApiError(
      typeof detail === "string" ? detail : `Falha HTTP ${response.status}`,
      response.status,
      data,
    );
  }
  if (
    analytic &&
    data &&
    typeof data === "object" &&
    "metadata" in data &&
    isGoldMetadata(data.metadata)
  ) {
    const metadata = decodeGoldMetadata(data.metadata);
    if (
      requestGeneration !== getGoldGeneration() ||
      !acceptGoldPublication(metadata)
    ) {
      throw new ApiError(
        "A publicação Gold mudou. Atualize os dados da jornada.",
        409,
        { error: { code: "stale_batch" } },
      );
    }
  }
  return data as T;
}
