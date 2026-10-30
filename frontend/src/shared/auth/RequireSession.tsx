import type { ReactNode } from "react";
import { useSession } from "./useSession";
import Button from "@/shared/ui/Button";

export default function RequireSession({ children }: { children: ReactNode }) {
  const session = useSession();
  if (!session.configured) return <>{children}</>;
  if (session.loading) {
    return (
      <p role="status" className="p-8 text-sm text-muted">
        Verificando sessão…
      </p>
    );
  }
  if (session.error) {
    return (
      <p
        role="alert"
        className="m-8 rounded-xl border border-border bg-surface p-5"
      >
        {session.error}
      </p>
    );
  }
  if (!session.user) {
    return (
      <main className="mx-auto flex min-h-dvh max-w-lg flex-col items-start justify-center gap-4 p-6">
        <h1 className="font-heading text-2xl font-semibold">
          Acesse o Grid 360
        </h1>
        <p className="text-sm leading-6 text-muted">
          Entre com sua conta corporativa para consultar o portal.
        </p>
        <Button onClick={() => void session.beginLogin()}>
          Entrar com SSO
        </Button>
      </main>
    );
  }
  return (
    <>
      {session.needsReauthentication ? (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-surface px-5 py-3 text-sm"
        >
          <span>
            A API recusou a sessão. Renove o acesso e repita a ação pendente.
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() =>
                void session.renewSession().catch(() => session.beginLogin())
              }
            >
              Renovar sessão
            </Button>
            <Button variant="outline" onClick={() => void session.beginLogin()}>
              Entrar novamente
            </Button>
          </div>
        </div>
      ) : null}
      <div
        hidden={session.needsReauthentication}
        inert={session.needsReauthentication}
      >
        {children}
      </div>
    </>
  );
}
