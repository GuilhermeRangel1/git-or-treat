import {
  InMemoryWebStorage,
  UserManager,
  WebStorageStateStore,
} from "oidc-client-ts";

export type OidcConfig = { authority: string; clientId: string };

export function getOidcConfig(): OidcConfig | null {
  const authority = import.meta.env.VITE_OIDC_AUTHORITY?.trim();
  const clientId = import.meta.env.VITE_OIDC_CLIENT_ID?.trim();
  if (!authority && !clientId) return null;
  if (!authority || !clientId) {
    throw new Error("Configure VITE_OIDC_AUTHORITY e VITE_OIDC_CLIENT_ID.");
  }
  let issuer: URL;
  try {
    issuer = new URL(authority);
  } catch {
    throw new Error("VITE_OIDC_AUTHORITY deve ser uma URL válida.");
  }
  const loopback = ["localhost", "127.0.0.1", "[::1]"].includes(
    issuer.hostname,
  );
  if (
    issuer.username ||
    issuer.password ||
    issuer.search ||
    issuer.hash ||
    (issuer.protocol !== "https:" &&
      !(import.meta.env.DEV && issuer.protocol === "http:" && loopback))
  ) {
    throw new Error(
      "O provedor OIDC exige HTTPS; HTTP só é aceito em loopback local.",
    );
  }
  return { authority: issuer.toString().replace(/\/$/, ""), clientId };
}

export function createOidcUserManager(config: OidcConfig) {
  const origin = window.location.origin;
  return new UserManager({
    authority: config.authority,
    client_id: config.clientId,
    redirect_uri: `${origin}/auth/callback`,
    post_logout_redirect_uri: origin,
    response_type: "code",
    scope: "openid orders:read orders:write",
    userStore: new WebStorageStateStore({ store: new InMemoryWebStorage() }),
    stateStore: new WebStorageStateStore({ store: window.sessionStorage }),
    automaticSilentRenew: false,
  });
}
