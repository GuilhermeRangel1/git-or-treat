import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { resetGoldPublication } from "@/shared/analytics/goldPublication";
import {
  advanceAuthorizationGeneration,
  clearReauthenticationRequired,
  currentAuthorizationGeneration,
  setSessionConfigured,
  setUnauthorizedHandler,
} from "./authorization";
import type { OrderAccess } from "./orderAccess";
import {
  getSession,
  loginSession,
  logoutSession,
  type SessionUser,
} from "./session-api";
import { SessionContext, type SessionValue } from "./session-context";

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [configured, setConfigured] = useState(false);
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<SessionUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [logoutFailed, setLogoutFailed] = useState(false);
  const [needsReauthentication, setNeedsReauthentication] = useState(false);
  const [lastConfirmedAccess, setLastConfirmedAccess] = useState<{
    actor: string;
    access: OrderAccess;
  } | null>(null);
  const identityRef = useRef<string | null>(null);
  const requestIdRef = useRef(0);
  const aliveRef = useRef(true);

  const clearIdentityData = useCallback(() => {
    advanceAuthorizationGeneration();
    void queryClient.cancelQueries();
    queryClient.clear();
    resetGoldPublication();
    clearReauthenticationRequired();
    setNeedsReauthentication(false);
    setLastConfirmedAccess(null);
  }, [queryClient]);

  const setCurrentSession = useCallback(
    (enabled: boolean, nextUser: SessionUser | null) => {
      const nextIdentity = enabled ? (nextUser?.id ?? null) : null;
      if (identityRef.current !== nextIdentity) clearIdentityData();
      identityRef.current = nextIdentity;
      setSessionConfigured(enabled);
      setConfigured(enabled);
      setUser(nextUser);
      setError(null);
    },
    [clearIdentityData],
  );

  const reloadSession = useCallback(async () => {
    const requestId = ++requestIdRef.current;
    const generation = advanceAuthorizationGeneration();
    try {
      const result = await getSession();
      if (
        !aliveRef.current ||
        requestId !== requestIdRef.current ||
        generation !== currentAuthorizationGeneration()
      )
        return;
      setCurrentSession(result.enabled, result.enabled ? result.user : null);
      if (result.enabled && result.user) {
        void queryClient.invalidateQueries({ queryKey: ["order-access"] });
      }
      clearReauthenticationRequired();
      setNeedsReauthentication(false);
    } catch (cause) {
      if (!aliveRef.current || requestId !== requestIdRef.current) return;
      setError(
        cause instanceof Error
          ? cause.message
          : "Não foi possível verificar a sessão.",
      );
    } finally {
      if (aliveRef.current && requestId === requestIdRef.current) {
        setLoading(false);
      }
    }
  }, [queryClient, setCurrentSession]);

  useEffect(() => {
    aliveRef.current = true;
    setUnauthorizedHandler(() => {
      setNeedsReauthentication(true);
      advanceAuthorizationGeneration();
      void queryClient.cancelQueries();
      queryClient.clear();
      resetGoldPublication();
    });
    // Hydrate auth state from the backend after this external request settles.
    // oxlint-disable-next-line react(set-state-in-effect)
    void reloadSession();
    return () => {
      aliveRef.current = false;
      requestIdRef.current += 1;
      setSessionConfigured(false);
      setUnauthorizedHandler(null);
    };
  }, [queryClient, reloadSession]);

  const login = useCallback(
    async (username: string, password: string) => {
      const requestId = ++requestIdRef.current;
      setError(null);
      setLogoutFailed(false);
      const result = await loginSession(username, password);
      if (!aliveRef.current || requestId !== requestIdRef.current) return;
      setCurrentSession(result.enabled, result.user);
      setLoading(false);
      clearReauthenticationRequired();
    },
    [setCurrentSession],
  );

  const logout = useCallback(async () => {
    ++requestIdRef.current;
    setLoading(true);
    setError(null);
    setLogoutFailed(false);
    clearIdentityData();
    identityRef.current = null;
    setUser(null);
    try {
      await logoutSession();
      setLoading(false);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Não foi possível encerrar a sessão. Tente novamente.",
      );
      setLogoutFailed(true);
      setLoading(false);
      throw cause;
    }
  }, [clearIdentityData]);

  const clearReauthentication = useCallback(() => {
    clearReauthenticationRequired();
    setNeedsReauthentication(false);
  }, []);
  const rememberOrderAccess = useCallback(
    (actor: string, access: OrderAccess) =>
      setLastConfirmedAccess({ actor, access }),
    [],
  );
  const value = useMemo<SessionValue>(
    () => ({
      configured,
      loading,
      user,
      error,
      logoutFailed,
      needsReauthentication,
      lastConfirmedAccess,
      rememberOrderAccess,
      login,
      logout,
      reloadSession,
      clearReauthentication,
    }),
    [
      configured,
      loading,
      user,
      error,
      logoutFailed,
      needsReauthentication,
      lastConfirmedAccess,
      rememberOrderAccess,
      login,
      logout,
      reloadSession,
      clearReauthentication,
    ],
  );
  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}
