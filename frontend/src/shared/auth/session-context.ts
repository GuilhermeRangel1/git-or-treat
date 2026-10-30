import { createContext } from "react";
import type { User } from "oidc-client-ts";
import type { OrderAccess } from "./orderAccess";

export type SessionValue = {
  configured: boolean;
  loading: boolean;
  user: User | null;
  error: string | null;
  needsReauthentication: boolean;
  lastConfirmedAccess: { actor: string; access: OrderAccess } | null;
  rememberOrderAccess: (actor: string, access: OrderAccess) => void;
  beginLogin: () => Promise<void>;
  beginLogout: () => Promise<void>;
  finishLogin: () => Promise<void>;
  renewSession: () => Promise<void>;
  clearReauthentication: () => void;
};

export const SessionContext = createContext<SessionValue | null>(null);
