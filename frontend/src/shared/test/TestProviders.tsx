import { useState, type ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { createQueryClient } from "../api/query-client";
import { ThemeProvider } from "../theme/ThemeProvider";
import { SessionContext, type SessionValue } from "../auth/session-context";

const demoSession: SessionValue = {
  configured: false,
  loading: false,
  user: null,
  error: null,
  logoutFailed: false,
  needsReauthentication: false,
  lastConfirmedAccess: null,
  rememberOrderAccess: () => {},
  login: async () => {},
  logout: async () => {},
  reloadSession: async () => {},
  clearReauthentication: () => {},
};

export function DemoSessionProvider({ children }: { children: ReactNode }) {
  return (
    <SessionContext.Provider value={demoSession}>
      {children}
    </SessionContext.Provider>
  );
}

export default function TestProviders({ children }: { children: ReactNode }) {
  const [queryClient] = useState(createQueryClient);
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <DemoSessionProvider>{children}</DemoSessionProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
