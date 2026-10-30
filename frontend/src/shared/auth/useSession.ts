import { useContext, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { decodeOrderAccess, type OrderAccess } from "./orderAccess";
import { SessionContext } from "./session-context";

function identityOf(sub: string | undefined) {
  return sub || null;
}

export function useSession() {
  const value = useContext(SessionContext);
  if (!value) throw new Error("AuthProvider nao esta disponivel.");
  return value;
}

export function useOrderAccess() {
  const {
    configured,
    user,
    needsReauthentication,
    lastConfirmedAccess,
    rememberOrderAccess,
  } = useSession();
  const actor = identityOf(user?.profile.sub);
  const query = useQuery<OrderAccess>({
    queryKey: ["order-access", actor],
    enabled: configured && Boolean(actor) && !needsReauthentication,
    queryFn: async () =>
      decodeOrderAccess(await apiClient<unknown>("/api/v1/inspections/access")),
    staleTime: 0,
    gcTime: 0,
  });
  useEffect(() => {
    if (actor && query.data) rememberOrderAccess(actor, query.data);
  }, [actor, query.data, rememberOrderAccess]);
  const currentSnapshot =
    actor && lastConfirmedAccess?.actor === actor ? lastConfirmedAccess : null;
  return { ...query, lastConfirmedAccess: currentSnapshot };
}
