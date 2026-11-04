import { useState, type ReactNode } from "react";
import { Link, Navigate } from "react-router-dom";
import { useSession } from "./useSession";
import Button from "@/shared/ui/Button";

export default function RequireSession({ children }: { children: ReactNode }) {
  const {
    configured,
    loading,
    user,
    error,
    logoutFailed,
    needsReauthentication,
    logout,
    reloadSession,
  } = useSession();
  const [checkingSession, setCheckingSession] = useState(false);

  if (loading) {
    return (
      <p role="status" className="p-8 text-sm text-muted">
        Verificando sessão…
      </p>
    );
  }
  if (error && logoutFailed) {
    return (
      <div
        role="alert"
        className="m-8 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-surface p-5"
      >
        <span>{error}</span>
        <Button onClick={() => void logout().catch(() => {})}>
          Tentar encerrar novamente
        </Button>
      </div>
    );
  }
  if (error) {
    return (
      <div
        role="alert"
        className="m-8 rounded-xl border border-border bg-surface p-5"
      >
        <p>{error}</p>
        <div className="mt-4 flex gap-3">
          <Button variant="outline" onClick={() => void reloadSession()}>
            Verificar novamente
          </Button>
          <Link className="self-center text-brand underline" to="/login">
            Ir para a entrada
          </Link>
        </div>
      </div>
    );
  }
  if (configured && !user) return <Navigate to="/login" replace />;

  return (
    <>
      {needsReauthentication ? (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-surface px-5 py-3 text-sm"
        >
          <span>
            A API recusou a sessão. Confirme seu acesso antes de continuar.
          </span>
          <Button
            variant="outline"
            disabled={checkingSession}
            onClick={() => {
              setCheckingSession(true);
              void reloadSession().finally(() => setCheckingSession(false));
            }}
          >
            {checkingSession ? "Verificando…" : "Verificar sessão"}
          </Button>
        </div>
      ) : null}
      <div
        key={
          configured && user
            ? JSON.stringify([
                user.id,
                user.profile,
                [...user.permissions].sort(),
              ])
            : configured
              ? "anonymous"
              : "demo"
        }
        hidden={needsReauthentication}
        inert={needsReauthentication}
      >
        {children}
      </div>
    </>
  );
}
