import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { User } from "oidc-client-ts";
import { resetGoldPublication } from "@/shared/analytics/goldPublication";
import {
  advanceAuthorizationGeneration,
  clearReauthenticationRequired,
  setAccessTokenProvider,
  setUnauthorizedHandler,
} from "./authorization";
import type { OrderAccess } from "./orderAccess";
import { createOidcUserManager, getOidcConfig } from "./oidc";
import { SessionContext, type SessionValue } from "./session-context";

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const managerResult = useMemo(() => {
    try {
      const config = getOidcConfig();
      return {
        manager: config ? createOidcUserManager(config) : null,
        error: null,
      };
    } catch (error) {
      return {
        manager: null,
        error:
          error instanceof Error
            ? error.message
            : "Configuração OIDC inválida.",
      };
    }
  }, []);
  const manager = managerResult.manager;
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(Boolean(manager));
  const [error, setError] = useState<string | null>(managerResult.error);
  const [needsReauthentication, setNeedsReauthentication] = useState(false);
  const [lastConfirmedAccess, setLastConfirmedAccess] = useState<{
    actor: string;
    access: OrderAccess;
  } | null>(null);
  const identityRef = useRef<string | null>(null);

  const setCurrentUser = useCallback(
    (next: User | null) => {
      const previousIdentity = identityRef.current;
      const nextIdentity = next?.profile.sub || null;
      if (previousIdentity !== nextIdentity) {
        advanceAuthorizationGeneration();
        void queryClient.cancelQueries();
        queryClient.clear();
        resetGoldPublication();
        setNeedsReauthentication(false);
        setLastConfirmedAccess(null);
      }
      identityRef.current = nextIdentity;
      setUser(next);
      setAccessTokenProvider(
        manager && nextIdentity
          ? async () => {
              const expectedIdentity = identityRef.current;
              let current = await manager.getUser();
              if (
                !current ||
                current.profile.sub !== expectedIdentity ||
                identityRef.current !== expectedIdentity
              )
                return null;
              if ((current.expires_in ?? 0) <= 30) {
                try {
                  current = (await manager.signinSilent()) ?? current;
                } catch {
                  if (current.expired) return null;
                }
              }
              return current.expired ||
                current.profile.sub !== expectedIdentity ||
                identityRef.current !== expectedIdentity
                ? null
                : current.access_token;
            }
          : null,
      );
    },
    [manager, queryClient],
  );

  useEffect(() => {
    if (!manager) return;
    let alive = true;
    const loaded = (next: User) => {
      if (alive) setCurrentUser(next);
    };
    const unloaded = () => {
      if (alive) setCurrentUser(null);
    };
    manager.events.addUserLoaded(loaded);
    manager.events.addUserUnloaded(unloaded);
    setUnauthorizedHandler(() => {
      setNeedsReauthentication(true);
      advanceAuthorizationGeneration();
      void queryClient.cancelQueries();
      queryClient.clear();
      resetGoldPublication();
    });
    void manager
      .getUser()
      .then((existing) => {
        if (alive) setCurrentUser(existing);
      })
      .catch(() => {
        if (alive) setError("Não foi possível restaurar a sessão OIDC.");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
      manager.events.removeUserLoaded(loaded);
      manager.events.removeUserUnloaded(unloaded);
      setAccessTokenProvider(null);
      setUnauthorizedHandler(null);
    };
  }, [manager, queryClient, setCurrentUser]);

  const beginLogin = useCallback(async () => {
    if (!manager) return;
    setError(null);
    await manager.signinRedirect();
  }, [manager]);

  const beginLogout = useCallback(async () => {
    if (!manager) return;
    const idTokenHint = user?.id_token;
    advanceAuthorizationGeneration();
    setAccessTokenProvider(null);
    void queryClient.cancelQueries();
    queryClient.clear();
    resetGoldPublication();
    setCurrentUser(null);
    await manager.removeUser();
    await manager.signoutRedirect({ id_token_hint: idTokenHint });
  }, [manager, queryClient, setCurrentUser, user]);

  const finishLogin = useCallback(async () => {
    if (!manager) return;
    const result = await manager.signinRedirectCallback();
    setCurrentUser(result);
  }, [manager, setCurrentUser]);

  const renewSession = useCallback(async () => {
    if (!manager) return;
    const result = await manager.signinSilent();
    if (!result || result.profile.sub !== identityRef.current) {
      throw new Error("A renovação não confirmou a identidade atual.");
    }
    setCurrentUser(result);
    clearReauthenticationRequired();
    setNeedsReauthentication(false);
  }, [manager, setCurrentUser]);

  const clearReauthentication = useCallback(
    () => setNeedsReauthentication(false),
    [],
  );
  const rememberOrderAccess = useCallback(
    (actor: string, access: OrderAccess) => {
      setLastConfirmedAccess({ actor, access });
    },
    [],
  );
  const value = useMemo<SessionValue>(
    () => ({
      configured: Boolean(manager) || Boolean(managerResult.error),
      loading,
      user,
      error,
      needsReauthentication,
      lastConfirmedAccess,
      rememberOrderAccess,
      beginLogin,
      beginLogout,
      finishLogin,
      renewSession,
      clearReauthentication,
    }),
    [
      manager,
      managerResult.error,
      loading,
      user,
      error,
      needsReauthentication,
      lastConfirmedAccess,
      rememberOrderAccess,
      beginLogin,
      beginLogout,
      finishLogin,
      renewSession,
      clearReauthentication,
    ],
  );
  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}
