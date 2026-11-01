# GENAI-10A — revalidação sanitizada da Gold v2

Data: 01/11/2026. Entregas separadas: PR #99 (runner/matriz) e branch
`feat/genai-cobertura-dominios` (implementação sobre develop). Os IDs IA mantêm seus estados.

SQL, sessão, autorização e auditoria reais; modelo controlado seleciona observações
validadas, sem calcular os valores de controle. As rodadas anteriores com Gemini
tiveram falhas e não são declaradas verdes. FAT-10 falhou na rodada principal por
truncamento indevido; após corrigir ranking top-1, foi reconciliado em execução separada.

Resultado consolidado: **37 PASS, 11 BLOQUEADO, 7 SEM_AMOSTRA_NO_LOTE, 2 NAO_EXECUTADO**.
Não há FAIL inesperado remanescente nessa revalidação controlada. Nenhum domínio
está integralmente certificado; PASS exploratório e aceite técnico local não homologam Dados.

A pessoa usuária aprovou expressamente o uso dos controles nos 17 casos numéricos
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
| FAT-09 | BLOQUEADO | Não se aplica / pendente |
| FAT-10 | PASS | Aprovado |
| FAT-11 | BLOQUEADO | Não se aplica / pendente |
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
| CON-06 | BLOQUEADO | Não se aplica / pendente |
| CON-07 | BLOQUEADO | Não se aplica / pendente |
| CON-08 | BLOQUEADO | Não se aplica / pendente |
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
| AMB-08 | BLOQUEADO | Não se aplica / pendente |
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
