# GENAI-15 — operação da Gold v2

Entrega local de 02/11/2026; branch `feat/genai-operacao-gold`, base `develop` em `93430c8`. Escopo IA-05, IA-06 e parcela GenAI de ENT-04. O fechamento técnico deste cartão não certifica a cobertura dos domínios nem conclui os requisitos oficiais inteiros.

## Caminho executado

Portal/API Backend → sessão individual → planejamento interno GenAI → prontidão e SQL no Backend → síntese interna GenAI → confirmação de auditoria → resposta. O entrypoint é `app.gold_runtime:create_gold_app`; o catálogo é `gold-catalog-v2`, schema `gold_v2`, contrato físico `gold-csv-v2`, fonte `gold.local`. Envelopes HTTP v1 continuam independentes da versão dos dados.

Reuso de `ExecutionController`, `GenAIRequestDeadline`, fábrica de provedores, cache, auditoria durável e executor existentes. A GenAI não recebe credencial de banco. Não há fallback para demonstração. O roteamento light/strong permanece rejeitado no perfil Gold; fallback explícito de provedores usa a mesma evidência e fundamentação. Não foi habilitado modelo leve para satisfazer uma política que exige modelo forte.

## Checklist original — 11/11 na entrega local

| Item | Evidência |
| --- | --- |
| P1 — fonte, catálogo, credenciais e auditoria por ambiente | Overlay e exemplo sem segredos; `check_genai_runtime.py` confere identidade/restrições do leitor, publicação v2, tipos físicos, catálogo entre serviços e persistência/leitura de evento operacional. Prontidão passou nos dois ambientes. |
| P2 — preparação separada e startup incompleto | Loader recebe `GOLD_LOADER_DATABASE_URL` exclusiva; Backend operacional e leitor mantêm senhas separadas. Banco vazio migrado/carregado; scripts reais de provisionamento passaram. Startup GenAI sem auditoria encerrou com erro; leitor ausente devolveu diagnóstico e exit 1. |
| P3 — readiness de banco, catálogo, lote e auditoria | CLI operacional passa somente com os componentes válidos. `/health` permanece liveness. Provedor configurado é distinto de geração comprovada por smoke/API. Prontidão não certifica cobertura nem concede acesso a perguntas. |
| P4 — fallback e guardrails | Teste HTTP pelo entrypoint Gold/fábrica normal: 503 passa ao secundário, observação inexistente é recusada e 401 não provoca fallback. Credenciais e mensagens privadas ausentes no retorno. |
| P5 — latência, volume, tokens e custo | Duas rodadas reais, 10 solicitações cada; SQL, modelo e duração acumulada por estágio reconciliados pela correlação. Tokens do SDK e custo padrão estimado abaixo; metas definidas após medir. |
| P6 — concorrência, fila e cancelamento | Carga Gold real com concorrência 1/3; fila do modelo observada zero nessa carga. Suíte PostgreSQL comprova cancelamento 57014 sob contenção paralela, recuperação da próxima consulta, oito conexões admitidas/nona negada e pools devolvidos. Testes assíncronos comprovam fila, cancelamento e devolução dos slots. Nenhum índice foi alterado sem necessidade medida. |
| R1 — ambiente, versões, startup e diagnóstico | Runbook abaixo; versões implantadas registradas. Token errado e auditoria sem conexão deram exit 1 e estados específicos, sem imprimir DSNs. |
| R2 — orçamento total e retentativas | Prazo Backend de 60 s compartilhado, SQL até 5 s, saldo interno decrescente. SDK sem retry implícito; fallback só transitório, limitado por chamadas/prazo e backoff configurável. Testes de deadline, limites e provedores passaram. |
| R3 — composição normal e política de modelo | Prova HTTP carrega `create_gold_app` e `build_model_adapter`; não substitui o núcleo por outro caminho. Fallback controlado não altera a evidência. Roteamento Gold segue bloqueado na configuração. |
| R4 — carga, cache, custo e liberação | Medições abaixo; cache real passou após recuperação do provedor, sem remover consulta/reautorização. Falhas não foram armazenadas. SQL real e cancelamento assíncrono comprovados em testes distintos; não se afirma cancelamento imediato por desconexão do navegador. |
| R5 — correlação, diagnóstico e investigação | Logs estruturados com correlação, duração/fila, linhas/bytes e tokens; auditoria existente separa fonte, modelo, autorização e qualidade. Runbook define alertas e investigação sem conteúdo privado. Rotação Compose: três arquivos de 10 MB por serviço. |

## Medições reais

Cinco tipos de solicitação repetidos duas vezes: receita municipal, consumo municipal, comparação de meses, ranking municipal e recusa de escrita. Mesma publicação Gold autorizada, sessão individual temporária, Gemini `gemini-3.5-flash-lite`, cache desligado, sem fallback configurado. São uma referência da entrega local, não um ensaio de escala ou SLA de produção. Tempos incluem todo o fluxo público; p50/p95 usam nearest-rank e dez amostras por rodada.

| Medida | Concorrência 1 | Concorrência 3 |
| --- | ---: | ---: |
| Solicitações / resultado | 10: oito respostas, duas recusas | 10: oito respostas, duas recusas |
| Resultado inesperado | 0 | 0 |
| p50 total | 15.349,04 ms | 23.863,91 ms |
| p95 total | 16.823,99 ms | 29.562,98 ms |
| SQL/executor p95 | 20 ms | 193 ms |
| Modelo p95 | 1.653 ms | 1.401 ms |
| Fila de modelo máxima | 0 ms | 0 ms |
| Evidência máxima | 2 linhas / 1.289 bytes | 2 linhas / 1.289 bytes |
| Tokens de entrada observados | 11.814 | 11.814 |
| Tokens gerados incluindo pensamento, por total menos entrada | 260 | 274 |
| Estimativa padrão máxima observada (USD) | 0,00419420 | 0,00422920 |

Todas as 16 respostas têm metadados de uso e confirmação de modelo na trilha. Auditoria Backend mostrou que a fase acumulada até plano/prontidão consumiu a maior parte do prazo: máximo 15.223 ms/28.142 ms, respectivamente. O número SQL acima mede o executor; não inclui a observação de prontidão. Cache de modelo não elimina esse custo. Contas/sessões temporárias foram removidas, sem modificar as regras de aprovação do lote.

Preço padrão consultado em 02/11/2026: USD 0,30 por milhão de tokens de entrada e USD 2,50 de saída incluindo pensamento, conforme [documentação oficial Gemini](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite). Não houve ferramenta externa. Estimativa usa entrada sem descontar cache do provedor, de modo conservador; não é fatura nem afirmação de plano pago/gratuito. Metadado ausente fica nulo; falha sem uso reportado não é declarada gratuita. A contagem de tokens vem do SDK, sem salvar prompt/resposta.

### Cache e indisponibilidade observada

No ambiente recém-carregado, cache foi habilitado somente para o ensaio (TTL 60 s). Primeira rodada de três chamadas: três `recoverable_error`, p95 35.684,09 ms; o provedor também devolveu 504 no diagnóstico de prompt público mínimo. A tentativa de diagnosticar outra rede afetou a resolução dos serviços de teste: três erros controlados, p95 566,03 ms; rede exclusiva foi restaurada, prontidão reconfirmada. Essas falhas não foram descartadas nem contadas como sucesso.

Rechecagem final de três consultas: uma falha transitória (33.759,85 ms), uma resposta real (17.777,18 ms, modelo 2.633 ms, 1.452 tokens de entrada/29 de saída), seguida por resposta reutilizada (15.119,68 ms, modelo abaixo de 1 ms e nenhuma nova chamada ao provedor). Mesma identidade/publicação/consulta; autorização e leitura precedem o cache. Economia observada: uma geração, aproximadamente USD 0,00050810 na tarifa padrão acima. O cache principal permanece desligado. A suíte cobre invalidação por identidade/lote/catálogo, resposta sem fundamento, falha não armazenada e cancelamento quando todos os consumidores desistem.

Metas locais definidas após medir: p95 até 45 s com concorrência até três; SQL até 5 s; saída até 100 linhas/16.384 bytes; prazo total até 60 s. Investigar qualquer erro inesperado, qualquer resposta sem confirmação de auditoria, ausência de telemetria em geração executada ou consumo acima de USD 0,005 por rodada equivalente de dez solicitações. Isso é uma referência de regressão local; não autoriza ampliar concorrência/limites nem garante disponibilidade externa. O episódio 504 deve continuar visível no relatório operacional.

## Execução e reprodução

1. Copiar `.env.gold-v2.example` para `.env.gold-v2`, informar a pasta do manifesto/quinze CSVs e `GOLD_LOADER_DATABASE_URL` do migrador. Preparar `.env.db`, `backend/.env` e `ai-agent/.env` pelos exemplos existentes. Nunca versionar os valores. No Backend, `DATABASE_URL` é `v_energy_app`; `GENAI_GOLD_DATABASE_URL` é `venergy_genai_reader`. Tokens de serviço/auditoria são distintos e coincidem apenas entre seus respectivos consumidores.
2. Usar projeto/volume novos para provar instalação limpa. Não executar `down -v` no projeto com dados úteis. Na pasta do repositório, PowerShell:

```powershell
$dc = @('--env-file', '.env.gold-v2', '-p', 'genai15-local', '-f', 'docker-compose.yml', '-f', 'docker-compose.gold-v2.yml')
docker compose @dc config --quiet
docker compose @dc up -d db
docker compose @dc run --rm --no-deps gold-loader
```

3. Depois da migração/carga, administrador aplica `backend/scripts/provision_backend_app.sql` e `backend/scripts/provision_genai_gold_reader.sql` com `psql -X -v ON_ERROR_STOP=1 -f <arquivo>`, e define as senhas por `\password`, fora do histórico. Em banco novo exclusivo, revisar/revogar TEMP de PUBLIC e CREATE de PUBLIC no schema público antes do provisionamento. Em banco compartilhado, avaliar os demais papéis antes dessa alteração. Os scripts recusam privilégios herdados incompatíveis e não revogam PUBLIC silenciosamente. O papel operacional tem leitura das quinze tabelas analíticas/views e escrita somente nas tabelas operacionais explícitas; não escreve Gold ou migra schema. O leitor quantitativo mantém a allowlist de colunas. A credencial de migração não é injetada no processo do Backend.
4. Iniciar consumidores e conferir:

```powershell
docker compose @dc up -d --build ai-agent backend frontend
docker compose @dc exec backend python scripts/check_genai_runtime.py
Start-Process http://localhost:5173
```

As portas 5432/8000/5173 devem estar livres; os testes desta entrega usaram rede/containers exclusivos sem publicar portas adicionais. O ensaio limpo executou os mesmos entrypoints, migrações, loader e scripts SQL a partir de banco vazio; `compose config --quiet` conferiu a topologia. GenAI depende só de sua configuração para liveness; Backend inicia após carga/GenAI. Callback de auditoria ocorre depois que ambos estão de pé, sem ciclo de startup. Um serviço parado não recebe fallback sintético.

O diagnóstico operacional escreve e relê um evento técnico na tabela de auditoria para comprovar persistência. Não confere completude dos domínios, não consulta medidas e não testa a chave no provedor. O smoke separado é uma pergunta já suportada pela API pública ou o smoke de provedor com dados sintéticos autorizado para o ambiente.

### Carga reproduzível e relatório sanitizado

`backend/scripts/benchmark_genai.py` aceita JSON privado com uma lista de `{"question": "...", "expected_status": "answered"}`. Credenciais de uma conta local autorizada entram em `GENAI_BENCHMARK_USERNAME`/`GENAI_BENCHMARK_PASSWORD`; URL por `GENAI_BENCHMARK_URL`. Executar de ambiente com acesso ao Backend: `python scripts/benchmark_genai.py --cases <arquivo-privado.json> --output <relatorio-ignorado.json> --repeat 2 --concurrency 3`. Limites da ferramenta: oito chamadas simultâneas/cem solicitações, sem retry automático, logout ao final. Os testes desta entrega criaram/removeram contas temporárias por harness privado; a ferramenta versionada não cria usuários nem amplia permissões.

Coletar logs dos dois serviços em pasta ignorada e executar `python scripts/summarize_genai_benchmark.py --benchmark <relatorio.json> --logs <genai.log> <backend.log> --provider gemini --input-usd-per-million 0.30 --output-usd-per-million 2.50`. Conferir o preço vigente do modelo antes de cada rodada. O resumo filtra correlações da carga e só extrai campos permitidos. Relatórios/logs privados e referências de auditoria não integram commits. Cache hit explícito explica ausência legítima de uso; ausência de metadados em geração real exige investigação.

## Investigação e alertas

- Falha de startup/carga: conferir código sanitizado do loader, compatibilidade do manifesto v2 e migrações; não iniciar consumidores sobre carga parcial. Corrigir a configuração e repetir o loader idempotente.
- Readiness não pronta: tratar o primeiro componente indisponível; conferir credencial/papel, publicação, drift físico e digest dos serviços. Não liberar capacidade nem promover controle aprovado por inferência.
- HTTP 401/403, contrato inválido ou fundamentação: não repetir com modelo/acesso mais permissivo. Conferir correlação na trilha restrita; não compartilhar pergunta, SQL, filtro ou cadastro em logs.
- 429/5xx/timeout do modelo: comparar tempos/contagens com limites, disponibilidade e cota no provedor. Fallback requer configuração explícita e credencial válida, mesma evidência e orçamento. Não aumentar o prazo automaticamente nem desativar fundamentação.
- p95/fila acima da referência: comparar tempo acumulado de plano/prontidão, SQL e síntese. A observação de prontidão domina a amostra; otimizar só após medição/revisão do dono do banco. Não enviar mais linhas ao modelo para contornar lentidão.
- Auditoria indisponível ou reconciliação divergente: bloquear a resposta, corrigir a fonte/armazenamento e revalidar; não servir cache anterior como resposta atual. Retenção de auditoria permanece 30 dias. Logs operacionais têm rotação local, sem conteúdo de negócio.
- Cancelamento: SQL usa prazo no servidor e libera conexão após interrupção/rollback; cancelar uma coroutine não interrompe uma thread sincrônica imediatamente. A prova limita trabalho restante, não promete cancelamento instantâneo do provedor por fechamento da aba.

## Verificações e limites

- GenAI completo: **4.189 passaram, cinco skips**, 54,63 s. Smoke remoto opt-in, symlink Windows e três opt-ins PostgreSQL não executados por essa suíte; PostgreSQL foi comprovado pelo Backend separadamente. Após o log explícito de cache, **60 testes dirigidos passaram** (observabilidade, resiliência e limites).
- Backend completo em PostgreSQL 16 descartável/cinco bancos: **1.012 passaram, 11 skips**, 233,83 s. Skips de dialeto/pacote privado/opt-ins; um aviso preexistente Starlette/httpx. Após log de duração HTTP, **24 passaram** (chat/health/métricas).
- Teste novo de composição Gold: cinco passaram, incluindo diagnóstico privado, metadado inválido/nulo e os três resultados de fallback. Ruff GenAI, compilação Python, `git diff --check` e Compose config passaram.
- Versões implantadas: Python 3.12; PostgreSQL 16; google-genai 2.34.0; FastAPI 0.162.0; httpx 0.28.1; Pydantic 2.14.2; sqlglot 30.27.0; SQLAlchemy 2.1.6; psycopg 3.3.6. Telemetria usa `GenerateContentResponse.usage_metadata`, conferido no SDK instalado; consulta Context7 ao SDK oficial não trouxe trecho correspondente. Preço verificado na fonte oficial acima.
- Fonte real permanece local/autorizada; não houve ampliação de grants no banco principal, escrita Gold de negócio, aumento de timeout ou exposição pública. O provisionamento foi aplicado somente ao banco novo de teste. Dados faltantes dos outros cartões continuam ausentes. Revisão desta entrega é técnica pelo agente; não homologa Dados/negócio.

Revisão final corrigiu dois riscos: resumo não associa logs sem correlação às chamadas da carga; provisionamento operacional rejeita CREATE em qualquer schema não sistêmico e CREATE/TEMP no banco. A prontidão também passou a verificar SELECT efetivo nas colunas das fontes autorizadas; fontes exclusivas de UC continuam fora do escopo, sem novos grants. Revogar SELECT de uma medida requerida no PostgreSQL isolado fez o diagnóstico retornar exit 1/catalog indisponível; restaurar a concessão recuperou todos os componentes. O script revisado de provisionamento passou novamente no banco isolado.

Após revisão, três regressões de resumo passaram; CREATE concedido no banco isolado foi rejeitado pelo provisionamento. Contas/sessões temporárias, quatro containers descartáveis, rede e arquivos privados de senhas foram removidos. Relatórios ignorados permanecem em `work/genai15-validation/`; ambiente principal foi preservado. Alterações ainda sem commit/push.
