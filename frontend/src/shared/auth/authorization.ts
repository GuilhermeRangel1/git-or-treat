export type UnauthorizedHandler = () => void;

let authorizationGeneration = 0;
let unauthorizedHandler: UnauthorizedHandler | null = null;
let reauthenticationRequired = false;
let sessionConfigured = false;

export function setSessionConfigured(configured: boolean) {
  sessionConfigured = configured;
  if (!configured) reauthenticationRequired = false;
}

export function isSessionConfigured() {
  return sessionConfigured;
}

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null) {
  unauthorizedHandler = handler;
}

export function notifyUnauthorized() {
  if (!sessionConfigured) return;
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
