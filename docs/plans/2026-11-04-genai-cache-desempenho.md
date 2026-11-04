# Cache e desempenho das consultas GenAI

Estado: implementação e aceite técnico local; PR #123 aberto contra `develop`, CI remoto 41806936506 aprovado nos cinco jobs. Cartão: https://trello.com/c/0TsqnMQH. Branch `feat/genai-cache-desempenho`. Nenhum requisito obrigatório novo; extensão do núcleo Gold v2 existente.

## Caminho e alterações

Portal → Backend autenticado → plano/prontidão/SQL Gold v2 → síntese GenAI → revalidação de escopo/publicação e auditoria → resposta. Reutilizados `CachingModelAdapter`, `GenAIInsightClient` e `observe_domain_readiness`. Não há cache de autorização, prontidão ou resultado SQL entre consultas. O hit de modelo/insight continua depois da leitura autorizada, com revalidações finais do coordenador.

- Cache do modelo: TTL/LRU existentes, limite adicional de bytes serializados (hash + resposta), descarte de expirados, cópia profunda e limite de chaves em andamento. Sob saturação, o fluxo segue sem acrescentar outra tarefa ao registro de coalescência, sujeito aos limites de entrada/modelo existentes.
- Insight: coalescência por payload completo/escopo/publicação/namespace; correlação e auditoria próprias de cada chamador. Cancelar um solicitante não interrompe outro; cancelar todos encerra a tarefa. Cache somente de respostas respondidas e coerentes com contexto, observações, fonte e limitações. Falhas não são persistidas.
- O observador de prontidão lê três colunas de `visao_360_uc` e sete de `atendimentos_uc` nos controles C14/C15. Nas tabelas mensais, presença e competências são observadas na mesma consulta, preservando NULL, vazio e teto de 1.200 competências; existência nas demais usa `SELECT 1`. Não foram removidos controles, alterados grants, criados índices ou mudadas fórmulas.

## Configuração e operação

O overlay Docker Gold ativa `GENAI_MODEL_CACHE_TTL_SECONDS=120`, `GENAI_MODEL_CACHE_MAX_ENTRIES=256` e `GENAI_MODEL_CACHE_MAX_BYTES=4194304`, sobrescrevíveis pelo ambiente do Compose. Fora do overlay, o padrão do serviço conserva TTL zero. Modelo/provedor/prompt compõem automaticamente o namespace da fábrica, e a chave inclui evidência, contexto, escopo, plano e proveniência/catálogo físico. Não se normaliza livremente a frase do usuário nem se faz equivalência semântica para compartilhar respostas.

Backend: `GENAI_INSIGHT_CACHE_TTL_SECONDS=120`, `GENAI_INSIGHT_CACHE_MAX_ENTRIES=64`, `GENAI_INSIGHT_CACHE_MAX_BYTES=1048576` e `GENAI_INSIGHT_CACHE_NAMESPACE=insight-v1`. Ao implantar outro prompt/modelo/provedor no serviço remoto, atualizar esse namespace e reiniciar o Backend; reiniciar limpa o cache. Essa sincronização de implantação é necessária, pois o Backend não consulta a configuração secreta do provedor remoto em cada hit. O payload completo preserva filtros, comparação, lote e escopo. TTL zero desativa retenção e coalescência de insights.

Os limites de bytes medem payload serializado, não RSS Python; o overhead adicional é limitado pela quantidade de entradas. Cache exclusivamente em memória, por processo, sem Redis, persistência ou compartilhamento entre workers. Reinício perde as entradas; a aplicação continua funcional. Alterar TTL/limites/namespace exige reiniciar os processos. Para rollback, TTL zero nos dois serviços e reinício; nenhuma migração ou reversão de dados é necessária. Logs contêm apenas estado hit/miss/shared, contagem e bytes, sem chave, pergunta ou valor Gold.

## Evidência local em 04/11/2026

Microbenchmark `PYTHONPATH=. python scripts/benchmark_cache.py`, em `ai-agent/`, usa o adaptador real e provedor artificial com atraso de 20 ms. Vinte requisições por cenário: sem cache p50/p95 31,471/32,470 ms e 20 chamadas; frio 31,270/31,966 ms e 20; quente 0,040/0,056 ms e zero; concorrente 29,589/29,756 ms e uma chamada. O scheduler Windows acrescenta atraso; esses tempos não estimam a latência Gemini. O comando falha se a contagem de chamadas divergir, mas não impõe limiar temporal instável. No CI do PR #123, executou e publicou somente o JSON agregado desse benchmark, junto aos relatórios sanitizados existentes.

PostgreSQL 16 local, leitura somente, mesma publicação: cinco execuções por projeção com `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` e `psql` com `COPY (SELECT ...) TO /dev/null`. Nenhum registro foi impresso ou exportado para artefato. Visão UC: 45.000 linhas, payload de 6.582.125 para 2.519.472 bytes; mediana de leitura/serialização de 41,908 para 14,168 ms. Atendimento: 318.871 linhas, 39.335.511 para 23.124.527 bytes; mediana de 309,500 para 155,766 ms. EXPLAIN isolado não mostrou ganho no scan: a projeção acrescenta trabalho no executor; o benefício medido está em serialização/transporte. Não há justificativa para índice novo nessa leitura integral de controles.

Comparação do observador original (`d76c7c4`) e atual no lote privado: duas execuções de cada, somente leitura; original 12.528,19/12.412,14 ms e 71 comandos SQL; atual 11.887,33/11.842,87 ms e 61 comandos. Os dicionários completos de fatos foram iguais nas quatro execuções. Amostra pequena local, sem promessa de ganho universal.

API real isolada em Docker, código desta branch, Gold v2 atual e Gemini configurado, com conta comercial temporária removida em finally: escalar, ranking, comparação e série, cada um repetido, responderam `answered` HTTP 200. Os 46 valores dos pontos coincidiram com SQL independente da mesma publicação, e as repetições preservaram os pontos. Tempos frio/quente: escalar 14.927/12.414 ms; ranking 13.545/12.413; comparação 13.539/12.455; série 13.635/12.348. Insight: 14.286/11.866 ms, ambos respondidos. Logs confirmaram miss→hit e ausência de nova geração no hit. O SELECT quantitativo ficou em 18–20 ms numa amostra de chat, incluindo a aquisição da conexão; a prontidão domina a latência restante. O cache não evita nem certifica esses controles.

A preparação isolada inicialmente usou origem/hostname incorretos, produzindo 403 de origem e 400 no ingresso de auditoria. Apenas os containers temporários foram ajustados para a origem 5181 já configurada e seus próprios hostnames. Um usuário legado sem perfil adequado recebeu 403 no Assistente; não teve permissões ampliadas. A prova posterior usou conta temporária comercial. Não atribuir os erros de configuração ao provedor ou mascará-los como sucesso.

## Verificações e limites

- GenAI completo em diretório limpo sem `.env`: 4.493 passaram e cinco skips opt-in. A execução inicial carregou token local e falhou no teste que exige serviço sem token; foi repetida corretamente isolada.
- Backend completo: 1.193 passaram, 114 skips e uma falha por `openpyxl` ausente no venv. Após instalar a dependência já exigida pelo projeto, cinco testes de arquivos passaram. Não se declara uma segunda suíte completa após essa instalação.
- Depois da redução de consultas mensais e do namespace: 103 testes dirigidos de prontidão/client/coordenador passaram e um opt-in foi ignorado. A regressão adicional de cancelamento total passou na rodada posterior de 35 testes do cliente.
- Escopo, catálogo, publicação, filtros, contexto, TTL, LRU, bytes, concorrência, falha e cancelamento exercitados pelas suítes existentes e ampliadas. A interface não recebeu alteração visual nem contrato público novo. Evidências privadas e segredos permanecem em `work/` ignorado.
- Código publicado no PR #123 e CI remoto 41806936506 aprovado nos cinco jobs. A evidência será sincronizada no Trello; a medição local não certifica cobertura de Dados ou disponibilidade contínua do Gemini.


Duas consultas reais simultâneas, na mesma conta temporária comercial, responderam HTTP 200 `answered` em 20.546,74 e 20.527,11 ms, com pontos iguais. Essa amostra confirma execução concorrente correta, mas não demonstra redução do tempo total sob concorrência: os controles de prontidão continuam consumindo CPU e consultas por solicitação. Contas e sessões de teste removidas em `finally`. Os containers temporários e arquivos temporários de ambiente foram removidos ao concluir; o banco iniciado para a rodada foi devolvido ao estado parado, com volume preservado.

### Reprodução das medições SQL

No PostgreSQL autorizado, abrir transação `READ ONLY` e aplicar `SET LOCAL statement_timeout='5s'`. Comparar `SELECT * FROM gold_v2.visao_360_uc` com `SELECT id_uc,total_chamados_callcenter,media_satisfacao_atendimento FROM gold_v2.visao_360_uc`. Para atendimento, comparar `SELECT * FROM gold_v2.atendimentos_uc` com `SELECT id_uc,nota_satisfacao,protocolo,_nota_invalida,_nota_negativa,data_abertura,_abertura_futura FROM gold_v2.atendimentos_uc`. Usar `EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON)` para o plano; no cliente `psql` isolado, `\timing on` e `\copy (<SELECT>) TO '/dev/null'` medem serialização/transporte sem imprimir registros. Não exportar essas linhas para arquivo de demonstração. Repetir cinco vezes e encerrar com rollback.

O comparativo de prontidão executou as duas versões de `observe_domain_readiness` com o mesmo engine, competência, aprovação de controles e `expected_batch_ref`, contando `before_cursor_execute` e comparando o dicionário completo retornado. Scripts privados da rodada ficam em `work/cache-runtime`; para o microbenchmark artificial versionado, usar o comando da seção anterior. Nenhum número de cliente ou registro pessoal foi incluído neste documento.


Rodada final do microbenchmark com `tracemalloc`: sem cache p50/p95 31,128/32,184 ms, frio 31,202/31,807, quente 0,141/0,156 e concorrente 27,060/27,895. Chamadas 20/20/0/1. Payload retido 0/3.160/158/158 bytes; pico de alocações Python 10.765/26.243/9.864/52.524 bytes, respectivamente. Instrumentação altera o custo observado; não equivale a RSS do processo ou vazamento em produção. A contagem de chamadas é o gate determinístico, tempos e memória são evidência descritiva.

Conferência final local: Ruff completo passou; compileall dos módulos afetados passou; YAML válido e o bloco documental do próprio CI conferiu configurações/imports e links em 184 documentos; `git diff --check` passou. PR #123 e CI remoto 41806936506 aprovados; o resultado será sincronizado no Trello. As evidências locais e remotas não certificam cobertura de Dados ou disponibilidade contínua do Gemini.
