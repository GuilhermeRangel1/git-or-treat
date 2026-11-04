# Inicialização Docker Gold v2

Escopo: execução local de DEV-12/DEV-13.1, autenticação WEB-10 e composição IA-04/IA-05/IA-06 existentes. Não altera fórmulas nem certifica cobertura de Dados.

## Fluxo e configuração

`scripts/configure-docker.ps1` recebe a pasta Gold v2 e gera o `.env` local com segredos distintos. Não sobrescreve configuração existente. `-GeminiEnvFile` reutiliza a chave de um arquivo local sem imprimi-la. Configurações Backend/GenAI legadas não são lidas implicitamente nesta composição.

`docker compose up --build -d` inicia `git-or-treat`: PostgreSQL saudável → loader (migrações, carga existente, grants versionados, contas) → API saudável → portal. GenAI usa runtime Gold com demonstração desativada e sem credenciais de banco. Só o loader recebe a credencial proprietária. API, leitor SQL GenAI e leitor cadastral usam papéis separados; tokens de serviço e auditoria são distintos.

Os quinze diretórios analíticos e `manifest.json` são obrigatórios. Cadastro opcional fica em `cadastro_titular_uc/` com seu manifesto. O inicializador copia temporariamente CSVs/manifestos e descarta somente marcadores Spark conhecidos (`_SUCCESS`, `_started_<n>`, `_committed_<n>`); rejeita arquivos inesperados e links. O importador original valida manifesto, inventário, hashes e pareamento. A origem permanece intacta; a área temporária é removida ao encerrar. Carga inválida impede a API. Repetir usa o carregador idempotente e preserva ordens/contas.

## Contas aprovadas

`-PresentationAccounts` habilita explicitamente `admin`, `comercial`, `atendimento`, `perdas`, `operacao` com `senha123`, somente para apresentação local. Os cinco perfis existentes permanecem separados. Sem a opção, senhas são aleatórias. Usuário existente nunca é promovido ou tem senha substituída; credenciais ficam em arquivo local ignorado. Esta opção não é uma política de credenciais para publicação pública.

## Desempenho e operação

Frontend em múltiplos estágios: Node só compila; imagem final contém Nginx e arquivos estáticos, gzip e cache dos assets com hash. HTML é revalidado. Proxy não bufferiza o fluxo do chat e conserva prazo de leitura. API sem reload e sem bind mount; pool operacional 5+5 conexões. Logs têm rotação (3 × 10 MB por serviço). Banco não publica porta no host; API/portal usam localhost. Cache GenAI existente permanece limitado.

Desenvolvimento explícito: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d`. Liga reload/HMR, preserva Gold v2 e desliga polling por padrão. CI artificial usa `docker-compose.ci.yml`, exclusivo do smoke descartável e sem dataset/chave real.

O projeto cria `git-or-treat_pgdata16`; não renomeia nem monta volumes `dev131-gold` ou PostgreSQL 18. Para parar: `docker compose down`, sem `-v`. Preserve `.env` junto do volume: regenerar senhas sem reprovisionar não autentica num banco existente. A carga inicial custa mais que reiniciar; loader termina com código zero e somente serviços permanentes continuam ativos.

HTTP local usa sessão individual. Publicação remota exige HTTPS, cookies Secure e revisão própria. Não publicar contas de apresentação. `GENAI_GOLD_APPROVED_CONTROLS` continua explícito; chave/cache não aprovam controles nem criam cobertura.

## Verificação

Validação local em 04/11/2026:

- Build das três imagens passou; frontend inclui TypeScript e Vite. Imagem final do portal: 93,8 MB, contra cerca de 850 MB da imagem anterior de desenvolvimento; redução aproximada de 89%. Observação ociosa do portal: 15,4 MiB e CPU 0%; não é benchmark de renderização nem ganho universal.
- Composição padrão, overlay de desenvolvimento e smoke CI passaram em `docker compose config --quiet`. O configurador PowerShell foi executado com a pasta local autorizada; chave e controles previamente aprovados foram mantidos somente no `.env` ignorado.
- Carga real Gold v2 e cadastro pareado concluídos no banco novo; loader encerrou com zero. Repetição retornou `unchanged` e preservou contas. A primeira carga processou cerca de 1,18 GB de CSVs e exigiu vários minutos; o loader encerra e libera seus recursos depois disso.
- 33 testes dirigidos passaram: `python -m pytest -q tests/test_docker_bootstrap.py tests/test_profile_provisioning.py tests/test_platform_authorization.py`, na imagem Backend. Incluem contrato de preparação dos CSVs, rejeição de destino externo antes de migrar, opt-in das contas e preservação de usuário existente. Aviso Starlette/httpx preexistente.
- Cinco logins reais, sessão e logout pelo proxy Nginx passaram; perfis e permissões conferidos. Atendimento/Perdas/Operação receberam 403 em Receita. Saúde da API pelo proxy: 200/online/connected; rota SPA `/assistente`: 200. Não foi feita nova revisão visual de todas as telas.
- Pergunta agregada de receita no Gemini pela API pública: HTTP 200, `answered`, com evidência, em 16,2 s. Foi usado o runtime Gold e a lista local de controles já aprovada, sem enviar cadastro ou linhas brutas. Esta prova demonstra composição, não nova certificação de cobertura ou benchmark comparativo do modelo.
- Privilégios reais: leitor GenAI sem SELECT no cadastro, INSERT em faturas ou TEMP; papel operacional sem CREATE. Sem alteração de grants fora da matriz versionada.
- Ruff dirigido, compilação, actionlint 1.7.12, links em 183 documentos e `git diff --check` passaram. Invariantes da configuração efetiva conferidas sem imprimir segredos: fonte Gold literal, runtime Gold sem demonstração, GenAI sem DSNs, banco sem porta pública e serviços normais sem binds de código. `.env` e credenciais conferidos como ignorados pelo Git. Estados oficiais do PRD preservados; CI remoto depende de publicação posterior autorizada.

Fonte técnica consultada em 04/11/2026: [Docker Compose](https://github.com/docker/compose/blob/main/docs/reference/compose.md), via Context7, sobre nome de projeto e dependências `service_healthy`/`service_completed_successfully`. Docker Engine local 29.8.0.

## Ajuste medido de memória e inicialização

Rodada adicional de 04/11/2026, solicitada pela pessoa usuária:

- O consumo inicial de cerca de 1,04 GiB era predominantemente cache de arquivos: cgroup registrava aproximadamente 11 MiB anônimos, 140 MiB de memória compartilhada e cache de arquivos. Não se tratava de 1 GiB de heap da aplicação PostgreSQL.
- Composição agora limita RAM do PostgreSQL a 512 MiB, ajustável por `POSTGRES_MEMORY_LIMIT`; reserva flexível de 256 MiB, shared_buffers 64 MiB, maintenance_work_mem 32 MiB e 64 conexões máximas. Work_mem, durabilidade, transações, validação e timeouts foram preservados. Volumes não foram removidos.
- Após quatro consultas concorrentes, catálogo, Receita e uma pergunta Gold/Gemini respondida com evidência em 16,31 s: Docker indicou 92,61 MiB; pico do cgroup de aproximadamente 156 MiB nesta rodada, com zero eventos OOM/oom_kill. O valor inicial de 1,04 GiB vinha de uma execução mais longa após a primeira carga; não é uma comparação controlada de memória com cache igualmente aquecido. Cargas maiores podem exigir elevar o limite; limites menores também podem aumentar I/O.
- Validação adicional após revisão: carga completa Gold v2 (cerca de 1,18 GB) e cadastro pareado executados em banco/volume vazios no projeto Docker isolado `git-or-treat-acceptance`, com o limite padrão de 512 MiB. `docker compose -p git-or-treat-acceptance run --build --rm gold-loader` concluiu com `Carga Gold v2: loaded; cadastro: loaded`, sem erro; PostgreSQL permaneceu saudável durante aproximadamente oito minutos. Leituras pontuais de memória durante a carga ficaram abaixo de 305 MiB; não são uma medição de pico. A rede e o volume temporários foram removidos depois. Isso comprova a carga limpa sob o teto configurado, mas não mede o tempo do build das demais imagens nem a subida completa do portal nesse mesmo projeto temporário.
- Healthchecks usam start_interval de 1 s durante start_period de 15 s. Subida do projeto parado com volume existente, sem tempo de build: 35,07 s antes e 17,58 s depois, uma amostra por configuração. É ganho local de prontidão; não significa reduzir pela metade o tempo da primeira importação ou a latência do modelo. Configuração verificada em Compose 5.5.1/Engine 29.8.0.
- A medição descobriu 503 anterior ao ajuste em analytics/options: GoldAnalyticsRepository ainda lia gold_carga_atual, negada ao papel operacional. Migração dockerpub0001 cria publicacao_analitica com identidade/tempo e apenas preco_volume_configuracao da origem. O repositório usa essa view no PostgreSQL; SQLite conserva o caminho dos testes. O papel operacional lê a view, sem SELECT na tabela de carga. O leitor GenAI não recebe acesso à nova view.
- Após corrigir a leitura, catálogo e dois recortes de Receita retornaram 200; quatro chamadas concorrentes passaram. Não há baseline de latência válido dessas rotas porque a versão anterior devolvia 503. Faturamento e fórmulas não foram alterados.
- Regressões: 18 testes dirigidos passaram, três opt-in inicialmente ignorados; rodada posterior de Ordens/migrações passou 13 com dois skips; ciclo de migrações repetido com TEST_POSTGRES_URL configurada passou 12/12 no PostgreSQL descartável. O banco docker_perf_test foi criado somente para fixtures artificiais e removido após a validação. Ruff dirigido, compilação das fixtures e Compose normal/dev passaram. Todos os serviços permanentes saudáveis; loader Exited(0). Sem commit ou push nesta rodada.

## Comparação A/B do chat Gold/Gemini

Em 04/11/2026, quatro blocos alternados (antigo, limitado, limitado, antigo), duas perguntas por bloco (receita escalar e comparação de consumo), cada uma executada e repetida imediatamente. Serviços Backend/GenAI reiniciados por bloco para limpar caches de processo; mesmo banco, publicação, identidade, perguntas e código. Parâmetros antigos: sem teto, shared_buffers 128 MB, max_connections 100, maintenance_work_mem 64 MB. Ajustados: teto 512 MiB, buffers 64 MB, 64 conexões, manutenção 32 MB. O cache de arquivos da VM/host não foi limpo: não representa leitura física fria.

| Mediana | Antigo | Limitado |
| --- | --- | --- |
| Resposta com cache miss (4 por configuração) | 14,477 s | 13,914 s |
| Repetição com cache hit (4 por configuração) | 12,921 s | 12,500 s |
| Etapa até evidência pronta, 8 por configuração | 12,793 s | 12,430 s |
| Incremento auditado source menos plan | 21,0 ms | 20,5 ms |

As 16 respostas concluídas foram answered. Hashes da resposta, contexto e visualização coincidiram por pergunta nas duas configurações. Telemetria confirmou oito misses e oito hits. Houve ainda uma tentativa no último bloco antigo com recoverable_error por limite da etapa do modelo após consulta bem-sucedida; esse bloco foi repetido e a falha fica explicitamente fora das medianas de sucesso. Não houve alteração de timeout nem desativação de guardas.

Diferença observada pequena (~0,4–0,6 s, 3–4%), insuficiente para afirmar ganho geral de latência; geração remota varia e a amostra tem só dois casos. A fase anterior à evidência, que inclui prontidão, continua dominante (~12,4 s), e o SQL numérico é cerca de 20 ms. O ganho demonstrado permanece menor consumo/limite de memória e inicialização mais rápida, sem regressão numérica nestes casos. Configuração limitada restaurada ao final. Script e resultados minimizados privados em work/docker-performance/, ignorados pelo Git; nenhum texto de resposta ou segredo publicado.
