export type AccessTokenProvider = () => Promise<string | null>;
export type UnauthorizedHandler = () => void;

let accessTokenProvider: AccessTokenProvider | null = null;
let authorizationGeneration = 0;
let unauthorizedHandler: UnauthorizedHandler | null = null;
let reauthenticationRequired = false;

export function setAccessTokenProvider(provider: AccessTokenProvider | null) {
  accessTokenProvider = provider;
  if (!provider) reauthenticationRequired = false;
}

export function getAccessToken() {
  return accessTokenProvider?.() ?? Promise.resolve(null);
}

export function hasAccessTokenProvider() {
  return accessTokenProvider !== null;
}

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null) {
  unauthorizedHandler = handler;
}

export function notifyUnauthorized() {
  reauthenticationRequired = true;
  unauthorizedHandler?.();
}

export function isReauthenticationRequired() {
  return reauthenticationRequired;
}

export function clearReauthenticationRequired() {
  reauthenticationRequired = false;
}

export function advanceAuthorizationGeneration() {
  authorizationGeneration += 1;
  return authorizationGeneration;
}

export function captureAuthorizationGeneration() {
  return authorizationGeneration;
}

export function currentAuthorizationGeneration() {
  return authorizationGeneration;
}
