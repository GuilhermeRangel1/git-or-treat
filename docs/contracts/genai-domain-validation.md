# GENAI-10A — revalidação sanitizada da Gold v2

Data: 01/11/2026. Entregas separadas: PR #99 (runner/matriz) e branch
`feat/genai-cobertura-dominios` (implementação sobre develop). Os IDs IA mantêm seus estados.

SQL, sessão, autorização e auditoria reais; modelo controlado seleciona observações
validadas, sem calcular os valores de controle. As rodadas anteriores com Gemini
tiveram falhas e não são declaradas verdes. FAT-10 falhou na rodada principal por
truncamento indevido; após corrigir ranking top-1, foi reconciliado em execução separada.

Resultado da rodada completa mais recente: **43 PASS, 5 BLOQUEADO, 7 SEM_AMOSTRA_NO_LOTE, 2 NAO_EXECUTADO**. A rodada anterior tinha 37 PASS e onze bloqueios; seis cenários avançaram nesta fatia.
Não há FAIL inesperado remanescente nessa revalidação controlada. Nenhum domínio
está integralmente certificado; PASS exploratório e aceite técnico local não homologam Dados.

A pessoa usuária aprovou expressamente o uso dos controles nos 22 casos numéricos
reconciliados. A aprovação não certifica cobertura mensal, não homologa fórmulas
pendentes nem aprova cenários bloqueados. Cada aprovação está no caso da matriz.

| Cenário | Resultado observado | Aceite numérico local |
| --- | --- | --- |
| FAT-01 | PASS | Aprovado |
| FAT-02 | PASS | Aprovado |
| FAT-03 | PASS | Aprovado |
| FAT-04 | PASS | Aprovado |
| FAT-05 | PASS | Aprovado |
| FAT-06 | PASS | Aprovado |
| FAT-07 | PASS | Não se aplica / pendente |
| FAT-08 | BLOQUEADO | Não se aplica / pendente |
| FAT-09 | PASS | Aprovado nesta extensão |
| FAT-10 | PASS | Aprovado |
| FAT-11 | PASS | Aprovado nesta extensão |
| FAT-12 | SEM_AMOSTRA_NO_LOTE | Não se aplica / pendente |
| FAT-13 | SEM_AMOSTRA_NO_LOTE | Não se aplica / pendente |
| FAT-14 | PASS | Não se aplica / pendente |
| FAT-15 | SEM_AMOSTRA_NO_LOTE | Não se aplica / pendente |
| FAT-16 | PASS | Aprovado |
| FAT-17 | PASS | Não se aplica / pendente |
| CON-01 | PASS | Aprovado |
| CON-02 | PASS | Aprovado |
| CON-03 | PASS | Não se aplica / pendente |
| CON-04 | PASS | Aprovado |
| CON-05 | PASS | Aprovado |
| CON-06 | PASS | Aprovado nesta extensão |
| CON-07 | PASS | Aprovado nesta extensão |
| CON-08 | PASS | Aprovado nesta extensão |
| CON-09 | PASS | Não se aplica / pendente |
| CON-10 | SEM_AMOSTRA_NO_LOTE | Não se aplica / pendente |
| CON-11 | PASS | Não se aplica / pendente |
| INT-01 | BLOQUEADO | Não se aplica / pendente |
| INT-02 | BLOQUEADO | Não se aplica / pendente |
| INT-03 | BLOQUEADO | Não se aplica / pendente |
| INT-04 | PASS | Não se aplica / pendente |
| INT-05 | PASS | Não se aplica / pendente |
| INT-06 | SEM_AMOSTRA_NO_LOTE | Não se aplica / pendente |
| INT-07 | SEM_AMOSTRA_NO_LOTE | Não se aplica / pendente |
| ATE-01 | BLOQUEADO | Não se aplica / pendente |
| ATE-02 | SEM_AMOSTRA_NO_LOTE | Não se aplica / pendente |
| ATE-03 | PASS | Aprovado |
| ATE-04 | PASS | Aprovado |
| ATE-05 | PASS | Aprovado |
| ATE-06 | PASS | Não se aplica / pendente |
| ATE-07 | PASS | Não se aplica / pendente |
| AMB-01 | PASS | Não se aplica / pendente |
| AMB-02 | PASS | Não se aplica / pendente |
| AMB-03 | PASS | Não se aplica / pendente |
| AMB-04 | PASS | Aprovado |
| AMB-05 | PASS | Aprovado |
| AMB-06 | PASS | Não se aplica / pendente |
| AMB-07 | PASS | Não se aplica / pendente |
| AMB-08 | PASS | Não se aplica / pendente |
| SEG-01 | PASS | Não se aplica / pendente |
| SEG-02 | PASS | Não se aplica / pendente |
| SEG-03 | PASS | Não se aplica / pendente |
| SEG-04 | PASS | Não se aplica / pendente |
| SEG-05 | PASS | Não se aplica / pendente |
| SEG-06 | NAO_EXECUTADO | Não se aplica / pendente |
| SEG-07 | NAO_EXECUTADO | Não se aplica / pendente |

## Pendências concretas

- Implementação: FAT-09 e CON-06 (comparações), CON-07 (ranking de variação por bairro)
  e AMB-08 (comparação anual com os limites descritos no caso).
- Definição/fonte aprovada: FAT-08 (pagamento), FAT-11 (preço/volume), CON-08
  (GD/queda) e INT-03 (unicidade da contagem de ocorrências).
- Certificação de cobertura: INT-01/02 e ATE-01. Os controles aprovados não fecham meses.
- Amostras ausentes: FAT-12/13/15, CON-10, INT-06/07 e ATE-02. Não foram fabricadas.
- SEG-06/07 são regressões técnicas fora do runner. Os testes referenciados foram
  executados na suíte e no ensaio PostgreSQL; a classe NAO_EXECUTADO do runner é preservada.
- Revisão com Dados/negócio e jornada final do portal continuam pendentes.

## Reprodução e limites

Em `ai-agent/`: `python scripts/run_gold_domain_scenarios.py --dry-run`; para rodada
integrada, configurar as variáveis `GENAI10A_*` conforme o contrato e usar `--strict`.
O relatório privado completo mantém parâmetros, valores e referências no diretório
ignorado da worktree 10B: `work/genai10/consolidated/`. Não é exportado para o Git.
O ensaio controlado usa a composição pública Backend e o transporte ASGI do núcleo
em processo separado; somente o adaptador de modelo é controlado. Não é um ensaio
de qualidade de linguagem do Gemini nem uma validação visual no navegador.

Verificações: 303 testes de matriz/runner na branch 10A; 3.970 testes GenAI e três
skips na branch 10B; Backend 855 aprovados/101 skips antes da correção top-1;
após a correção, 10 testes de executor e HTTP/PostgreSQL aprovados. Ruff e diff-check
aprovados. Os testes sintéticos não substituem os controles reais desta tabela.


## Extensão de comparação e regras documentadas — 01/11/2026

A rodada completa de 57 casos usou a matriz desta worktree com o núcleo e catálogo
ampliados da branch `feat/genai-cobertura-dominios`, sem duplicar seus commits.
SQL, sessão, permissões e auditoria são reais; somente a fronteira de geração do
modelo é controlada. Nenhuma chamada Gemini adicional foi feita. Contas
provisórias foram removidas ao terminar. Os cinco novos aceites numéricos foram
expressamente aprovados pela pessoa usuária após a reconciliação.

- FAT-09 e CON-06: controles independentes conferem valores inicial/final,
  diferença e percentual vinculados aos respectivos meses. Valores invertidos
  não passam por simples presença do mesmo conjunto de números.
- CON-07: controle exige ambos os meses em todos os bairros, escolhe a maior
  perda absoluta e confere também o rótulo do bairro. Ranking parcial não é aceito.
- CON-08: janelas fixas e elegibilidade mínima documentadas; C08/C09 reobservados
  no lote real, com população e dimensões conferidas contra a Visão 360.
- FAT-11: todos os componentes e contagens por participação são conferidos por
  rótulo; as janelas publicadas devem coincidir. Não há inferência causal.
- AMB-08: esclarecimento é o comportamento definido para comparação anual sem
  janelas equivalentes, não um bloqueio de implementação genérico.

Restam cinco bloqueios observados: valor recebido sem medida comprovada (FAT-08),
continuidade mensal não certificada (INT-01/02/03) e atendimento mensal não
certificado (ATE-01). Sete cenários continuam sem amostra real. SEG-06/07 são
regressões técnicas separadas, verificadas na suíte HTTP/PostgreSQL; o runner
não as converte em PASS Gold. Não fabricar amostras, certificação ou homologação.

Verificação conjunta: 305 testes de runner/matriz aprovados com os arquivos
exatos do 10A e o catálogo/núcleo ampliados do 10B, em diretório ignorado de
integração. O CI do PR #99 precisa receber a nova base do 10B depois de sua
integração em develop: as métricas novas não devem ser copiadas para esta branch.

Estado sincronizado no Trello: **6/10** entregáveis. Revisão de Dados/negócio, prova integral por caso e jornada final do portal continuam abertas.

Tentativa de jornada visual em 01/11/2026: portal isolado na porta 5183 e Backend com modelo controlado preparados; a ferramenta de navegador recusou acesso com `Local browser use is disabled in Work settings`. Nenhuma jornada foi declarada aprovada. O ambiente visual foi encerrado; nenhuma conta visual chegou a ser criada.


## Inventário de evidência por cenário — 01/11/2026

Os 57 casos da rodada já executada foram cruzados por ID com a matriz, sem nova chamada ao modelo e sem exportar valores privados. O registro sanitizado `docs/contracts/genai-domain-case-evidence.md` pertence à branch 10A e reúne estado esperado, estado observado, HTTP e classe de cada caso. Não substitui a conferência privada dos valores nem encerra o aceite integral.


### Revalidação HTTP pública — 01/11/2026

Rodada `20261101T195433_504518Z`: 57 casos avaliados com cliente HTTP externo ao processo do Backend isolado, login e cookies reais, endpoint público `/api/v1/ai/questions`, leitura Gold restrita e auditoria reais. Modelo controlado, sem novas chamadas Gemini. O transporte entre Backend e núcleo usa o adaptador de integração de teste existente; não comprova tráfego HTTP entre esses dois serviços nem qualidade de linguagem do provedor.

Resultado por ID idêntico ao anterior: 43 PASS, cinco BLOQUEADO, sete SEM_AMOSTRA_NO_LOTE e dois NAO_EXECUTADO (SEG-06/07, provas técnicas separadas). Sem divergências ou erros de execução. As duas contas temporárias e suas sessões foram removidas; Backend isolado encerrado.

Comando na worktree 10B: `docker exec --env-file work/genai10/.env.genai10b-backend -w /repo/backend genai10b-tests python /repo/work/genai10/http-acceptance.py`. Script e valores privados permanecem ignorados. A primeira tentativa foi rejeitada no login por Host interno não permitido; o cliente passou a enviar o Host local autorizado, sem mudar a proteção do servidor.

A fronteira HTTP pública foi comprovada; renderização/interação no navegador, revisão de Dados e lacunas de fonte continuam pendentes. Critérios e estados preservados.
