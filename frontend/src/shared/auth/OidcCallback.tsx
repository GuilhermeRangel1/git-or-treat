import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useSession } from "./useSession";

export default function OidcCallback() {
  const { finishLogin } = useSession();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const callback = useRef<Promise<void> | null>(null);
  useEffect(() => {
    let active = true;
    callback.current ??= finishLogin();
    void callback.current
      .then(() => {
        if (active) navigate("/panorama", { replace: true });
      })
      .catch(() => {
        if (active)
          setError(
            "Não foi possível concluir a autenticação. Tente entrar novamente.",
          );
      });
    return () => {
      active = false;
    };
  }, [finishLogin, navigate]);
  return error ? (
    <main className="mx-auto flex min-h-dvh max-w-lg flex-col items-start justify-center gap-4 p-6">
      <p role="alert" className="text-sm">
        {error}
      </p>
      <a className="underline" href="/">
        Voltar ao portal
      </a>
    </main>
  ) : (
    <p role="status" className="p-8 text-sm text-muted">
      Concluindo autenticação…
    </p>
  );
}
