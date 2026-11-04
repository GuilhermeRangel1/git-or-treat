import { createContext } from "react";
import type { OrderAccess } from "./orderAccess";
import type { SessionUser } from "./session-api";

export type SessionValue = {
  configured: boolean;
  loading: boolean;
  user: SessionUser | null;
  error: string | null;
  logoutFailed: boolean;
  needsReauthentication: boolean;
  lastConfirmedAccess: { actor: string; access: OrderAccess } | null;
  rememberOrderAccess: (actor: string, access: OrderAccess) => void;
  login: (username: string, password: string) => Promise<SessionUser | null>;
  logout: () => Promise<void>;
  reloadSession: () => Promise<void>;
  clearReauthentication: () => void;
};

export const SessionContext = createContext<SessionValue | null>(null);
