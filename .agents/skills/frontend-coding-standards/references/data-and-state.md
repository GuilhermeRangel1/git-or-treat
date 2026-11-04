# Contratos, estado remoto e formulários

## Um responsável por estado

| Informação | Onde manter |
| --- | --- |
| Período, filtros aplicados, ordenação e paginação compartilháveis | URL normalizada e validada pela feature. |
| Resposta da API, atualização e falha de consulta | TanStack Query. |
| Campos ainda não aplicados, menu ou diálogo | Estado local. |
| Tema | Provedor e preferência existentes. |
| Conversa/insight | Módulo próprio, com recorte e retenção acordados com backend/IA. |

Evite duas fontes independentes para o mesmo estado. Formulários podem ter um rascunho local e um recorte aplicado na URL; a confirmação faz a transição explicitamente. Formate rótulos para a pessoa usuária sem usar esses rótulos como identificadores instáveis da consulta.

## Fronteira HTTP

Use `shared/api/client.ts`. `apiClient<T>` informa o tipo esperado ao compilador, não valida JSON. Receba `unknown` onde a resposta externa precisar ser verificada, valide com decoder/schema e adapte para a tela. Siga [os contratos](../../../../docs/contracts/analytics-api.md); a implementação atual de `features/dev-contracts/contract.ts` mostra essa fronteira.

Não leia banco ou Gold pelo navegador. Variáveis `VITE_*` entram no bundle público: mantenha chaves e credenciais no servidor. Erros visíveis omitem SQL, stack traces e dados de terceiros. Mensagens da IA são conteúdo não confiável; mantenha escape de texto e sanitize HTML se algum renderer realmente o aceitar.

## Consultas e filtros

Inclua na `queryKey` todos os parâmetros normalizados que alteram a resposta: período, filtros, paginação e ordenação pertinentes. Prefixos como `['indicadores']` ajudam a invalidar grupos; sozinhos não distinguem recortes. Centralize chaves/opções quando houver reutilização real.

Encaminhe o `signal` recebido pela função de consulta até o transporte. A feature DEV-01 já demonstra cancelamento e decoder; não a torne dependência de páginas do produto. `queryOptions` é útil para compartilhar configuração, sem exigir uma fábrica para cada consulta simples.

O `QueryClient` atual desativa retries automáticos. Defina expiração, atualização e repetição conforme o contrato; não habilite retries globais por conveniência. Respostas antigas podem continuar visíveis durante atualização somente com contexto explícito. Um insight antigo não passa a explicar filtros novos só porque a tela mudou.

Distinga carregamento inicial, atualização em segundo plano, vazio, erro, parcial e indisponível. `null` não vira zero; denominador zero não produz percentual inventado. Mostre unidade, período, filtros efetivos, atualização e origem; dados sintéticos continuam identificados.

## Formulários e escritas

Use rótulos associados aos campos, mensagens próximas com `aria-describedby` e `aria-invalid`, indicação de envio e foco no erro pertinente. Preserve o preenchimento quando houver falha. Validação no cliente melhora a interação; o servidor valida autorização, regras e transições novamente.

Desabilite ações durante envio e trate submissão por teclado/formulário no mesmo caminho. Isso reduz duplicação local, mas não garante idempotência. Reenvio, múltiplas abas e perda de resposta exigem política no backend. Cancelar Fetch não desfaz uma escrita recebida pelo servidor; resultado desconhecido precisa ser reconciliado.

Após sucesso, atualize ou invalide os caches afetados. Atualização otimista exige rollback, tratamento de concorrência e regra de domínio clara; para ordens, a confirmação do servidor é a referência. Não introduza Zod ou um gerenciador de formulários sem necessidade concreta.

Fontes: [chaves TanStack Query 5](https://tanstack.com/query/latest/docs/framework/react/guides/query-keys), [cancelamento](https://tanstack.com/query/latest/docs/framework/react/guides/query-cancellation) e [invalidação após mutações](https://tanstack.com/query/latest/docs/framework/react/guides/invalidations-from-mutations).
