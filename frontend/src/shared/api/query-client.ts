import { QueryClient } from "@tanstack/react-query";

/** Sem consultas nesta etapa. Cada funcionalidade definirá sua política de atualização. */
export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, networkMode: "always" },
      mutations: { retry: false, networkMode: "always" },
    },
  });
}
