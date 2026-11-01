import { Link } from "react-router-dom";
import { getDefaultRoute } from "./platformAccess";
import { useSession } from "./useSession";

export default function AccessDenied() {
  const { user } = useSession();
  const destination = getDefaultRoute(user);

  return (
    <section
      role="alert"
      aria-labelledby="access-denied-title"
      className="mx-auto mt-8 w-full max-w-2xl rounded-xl border border-border bg-surface p-6"
    >
      <h1
        id="access-denied-title"
        className="font-heading text-xl font-semibold"
      >
        {user?.profile === null || !user
          ? "Acesso ainda não provisionado"
          : "Você não tem acesso a esta área"}
      </h1>
      <p className="mt-2 text-sm leading-6 text-muted">
        {user?.profile === null || !user
          ? "Peça ao administrador da plataforma para atribuir um perfil de acesso."
          : "Seu perfil não inclui a permissão necessária para este conteúdo."}
      </p>
      {destination ? (
        <Link
          className="mt-4 inline-flex min-h-11 items-center rounded-lg border border-control px-4 text-sm font-medium text-content hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          to={destination}
        >
          Ir para sua área inicial
        </Link>
      ) : null}
    </section>
  );
}
