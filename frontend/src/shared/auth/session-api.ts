export type SessionUser = {
  id: string;
  username: string;
  permissions: Array<"orders:read" | "orders:write">;
};

export type SessionEnvelope = {
  enabled: boolean;
  user: SessionUser | null;
  expires_at: string | null;
};

export class SessionApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "SessionApiError";
    this.status = status;
  }
}

function baseUrl() {
  const configured = import.meta.env.VITE_API_URL?.trim();
  if (configured) return configured.replace(/\/$/, "");
  if (import.meta.env.DEV) return "";
  throw new SessionApiError("A API não está configurada.", 0);
}

function decodeSession(value: unknown): SessionEnvelope {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new SessionApiError("Não foi possível validar a sessão.", 0);
  }
  const envelope = value as Record<string, unknown>;
  if (
    typeof envelope.enabled !== "boolean" ||
    (envelope.expires_at !== null &&
      (typeof envelope.expires_at !== "string" ||
        !/(Z|\+00:00)$/.test(envelope.expires_at) ||
        !Number.isFinite(Date.parse(envelope.expires_at)))) ||
    (!envelope.enabled && envelope.user !== null)
  ) {
    throw new SessionApiError("Não foi possível validar a sessão.", 0);
  }
  let user: SessionUser | null = null;
  if (envelope.user !== null) {
    if (
      !envelope.user ||
      typeof envelope.user !== "object" ||
      Array.isArray(envelope.user)
    ) {
      throw new SessionApiError("Não foi possível validar a sessão.", 0);
    }
    const row = envelope.user as Record<string, unknown>;
    if (
      typeof row.id !== "string" ||
      !row.id ||
      typeof row.username !== "string" ||
      !row.username ||
      !Array.isArray(row.permissions) ||
      !row.permissions.every(
        (permission) =>
          permission === "orders:read" || permission === "orders:write",
      )
    ) {
      throw new SessionApiError("Não foi possível validar a sessão.", 0);
    }
    user = {
      id: row.id,
      username: row.username,
      permissions: [...new Set(row.permissions)] as SessionUser["permissions"],
    };
  }
  if ((user === null) !== (envelope.expires_at === null)) {
    throw new SessionApiError("Não foi possível validar a sessão.", 0);
  }
  return {
    enabled: envelope.enabled,
    user,
    expires_at: envelope.expires_at as string | null,
  };
}

async function request(
  path: string,
  body?: unknown,
): Promise<SessionEnvelope | null> {
  let response: Response;
  try {
    response = await fetch(`${baseUrl()}/api/v1/auth/${path}`, {
      method: path === "session" ? "GET" : "POST",
      credentials: "include",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch {
    throw new SessionApiError(
      "Não foi possível conectar ao serviço de acesso.",
      0,
    );
  }
  if (path === "logout" && response.status === 204) return null;
  if (path === "logout" && response.ok) {
    throw new SessionApiError("Resposta inesperada ao encerrar a sessão.", 0);
  }
  const raw = await response.text();
  let data: unknown = undefined;
  if (raw) {
    try {
      data = JSON.parse(raw);
    } catch {
      if (response.ok) {
        throw new SessionApiError("Resposta inválida do serviço de acesso.", 0);
      }
    }
  }
  if (!response.ok) {
    const message =
      path === "login" && response.status === 401
        ? "Usuário ou senha incorretos. Confira os dados e tente novamente."
        : response.status === 429
          ? "Muitas tentativas. Aguarde um pouco antes de tentar novamente."
          : response.status === 403
            ? "A origem desta solicitação não foi autorizada. Atualize a página e tente novamente."
            : "Não foi possível concluir a solicitação de acesso. Tente novamente.";
    throw new SessionApiError(message, response.status);
  }
  if (path === "logout") return null;
  return decodeSession(data);
}

export async function getSession() {
  return (await request("session")) as SessionEnvelope;
}

export async function loginSession(username: string, password: string) {
  const envelope = (await request("login", {
    username,
    password,
  })) as SessionEnvelope;
  if (!envelope.enabled || !envelope.user) {
    throw new SessionApiError("O serviço não confirmou a sessão.", 0);
  }
  return envelope;
}

export async function logoutSession() {
  await request("logout");
}
