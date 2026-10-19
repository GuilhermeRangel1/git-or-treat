import { QueryClient } from "@tanstack/react-query";

/** Sem consultas nesta etapa. Cada funcionalidade definirá sua política de atualização. */
export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}
