# GENAI-10B — integração incremental dos domínios Gold v2

Escopo: IA-01, IA-02, IA-03 e IA-06; integração executável, ainda sem aceite integral
Gold. Branch `feat/genai-cobertura-dominios`, criada de `develop` após o merge do PR #98.
O runner e os ajustes da matriz pertencem ao PR #99, em branch independente.

## Caminho executado

Portal → `POST /api/v1/ai/questions` → sessão e escopo Backend → planejador interno
GenAI → plano revalidado → executor Backend com `venergy_genai_reader` → guarda de
evidência → síntese → resposta e auditoria. Nenhum executor, catálogo ou endpoint
paralelo foi criado. Referência física: `gold-csv-v2`, `gold-catalog-v2`, `gold_v2`,
perfil `v-energy-grid-360-gold` e fonte `gold.local`.

## Capacidades desta fatia

- FAT-10: maior contribuição absoluta de receita por classe em uma competência,
  com agrupamento autorizado por métrica, ordem decrescente, limite de uma linha e
  desempate estável do executor existente. Não representa variação nem causalidade.
  Uma janela de vários meses pede esclarecimento. Acompanhamento conserva grupo e ordem.
- ATE-03/04: seleção da variante acumulada a partir do período explícito do pedido.
  A observação precisa manter a frase exata de histórico acumulado; uma competência
  mensal contraditória é recusada. O observador admite ausência de janela apenas na
  operação de domínios e não publica fatos de cobertura mensal nessa situação.
- ATE-01/03/04/05: o escopo de sessão passa a admitir as quatro métricas de atendimento
  já definidas no catálogo. A leitura ganha somente `atendimentos_uc(protocolo,
  data_abertura, nota_satisfacao)` e `visao_360_uc(total_chamados_callcenter)`.
  Esse alcance foi autorizado expressamente pela pessoa usuária em 01/11/2026 e aplicado
  no banco local. Texto, cadastro, escrita e demais colunas continuam fora da concessão.
- ATE-06: pedido explícito do que o cliente escreveu no chamado é recusado; contagens
  agregadas continuam permitidas. O executor não recebe acesso ao conteúdo livre.
- Município explicitamente qualificado resolve colisão de nome com bairro; menção
  sem qualificação permanece ambígua. Novos aliases reconhecem preço observado,
  consumo médio por unidade com leitura e “neste ano”.

## Evidências e verificações

- GenAI, após os ajustes de revisão: suíte com 3.970 testes aprovados e três skips
  de ambiente. Regressões incluem FAT-10, acompanhamento, acumulado com período
  contraditório, qualificação de dimensão e ATE-06.
- Backend: suíte com 855 aprovados e 101 skips; ensaio PostgreSQL opt-in separado,
  com migrações, papel restrito, sessão e rota pública, passou em 101,05 s. Quatro
  casos adicionais usam expectativas literais para FAT-10 e ATE-01/03/04.
- Após a correção do observador acumulado: 61 testes de prontidão/acesso aprovados,
  um skip. No PostgreSQL Gold local, observação real sem modelo resultou em
  `atendimento.uc_acumulado=available` e `atendimento.mensal=unavailable`, em 13,94 s.
  Isso comprova a distinção; não certifica fechamento mensal.
- Ruff dos arquivos alterados e `git diff --check` aprovados. Revisão independente
  encontrou perda de ranking no acompanhamento e aceitação de data mensal em
  evidência acumulada; ambos corrigidos com regressões.

Os dados dos testes são artificiais. As rodadas privadas do runner sobre a Gold
real ficaram no diretório ignorado da worktree do 10A. Elas revelaram falhas de
interpretação, configuração e prontidão; nenhuma falha ou falta de amostra foi
convertida em PASS. Contas temporárias foram removidas ao terminar cada rodada.

## Limites da primeira fatia (superados parcialmente pela extensão abaixo)

Continuam pendentes comparações entre períodos e ranking de variação por bairro,
perguntas de preço/volume e GD/queda conforme definições ainda bloqueadas no catálogo,
contagem de ocorrências com regra aprovada, certificação mensal de atendimento e
continuidade, aprovação dos controles por cenário e validação final no portal.
Sete cenários não encontraram a amostra exigida no lote da conferência; teste
sintético desses estados não substitui o aceite da fonte real.

A rodada real com Gemini não ficou integralmente verde: incluiu erros recuperáveis,
indisponibilidade e falhas de transporte. Não é evidência de 100% de cobertura.
Comparações ainda exigem implementação; não estão sendo classificadas como uma
simples dependência externa. Não há declaração de conclusão dos cartões ou dos IDs IA.


## Revalidação controlada com o lote real

A rodada pelo coordenador público, sessão e papel restrito reconciliou 17 cenários
numéricos com SQL independente. O FAT-10 encontrou e corrigiu um erro real adicional:
a linha excedente usada para detectar truncamento não se aplica a um ranking explícito
limitado. O compilador agora preserva essa linha nas consultas completas e usa o limite
exato no ranking; teste PostgreSQL com duas classes confere os dois comportamentos.
Após a correção: dez testes de executor/HTTP PostgreSQL aprovados em 102,97 s.

A consolidação registra 37 PASS, onze bloqueados, sete sem amostra e duas regressões
separadas, sem falha inesperada remanescente nessa rodada controlada. A pessoa usuária
aprovou expressamente os 17 cenários numéricos para esta entrega local. Isso não
homologa Dados, não certifica os meses de atendimento/continuidade e não conclui os
quatro domínios. A tabela sanitizada e as aprovações pertencem à entrega do PR #99;
parâmetros, valores e referências permanecem exclusivamente no diretório privado.


## Extensão executável de comparação e regras de Dados — 01/11/2026

Decisões e fontes: [ADR-0022](../decisions/0022-consumo-metricas-documentadas-gold-v2.md),
`docs/dicionario_gold.md` e células de `Silver_to_gold.ipynb`. A pessoa usuária
orientou usar as regras existentes e autorizou explicitamente as novas concessões
locais; nenhuma aprovação de Dados foi inventada.

### Comportamento e limites

- FAT-09/CON-06 comparam dois meses explícitos, com campo opcional
  `comparison_periods` no plano. Fingerprints e envelopes sem o campo continuam
  iguais aos vetores legados. Backend revalida a operação, o filtro e a cobertura
  dos dois meses; meses intermediários não entram na consulta nem no percentual.
- CON-07 usa a diferença bruta absoluta por bairro antes de arredondar, com
  desempate por rótulo. SQL confere ambos os meses em todos os grupos, classifica
  no banco e só então limita a saída. Nenhum bairro incompleto é descartado para
  produzir um vencedor aparente; o estado é esclarecimento.
- CON-08 usa as janelas fixas publicadas, seis meses com leitura em cada uma e a
  flag bruta estritamente inferior a −30%. C08/C09 conferem população completa,
  município/GD da Visão 360, médias e contagens contra a série mensal. Valores
  não finitos não equivalem a ausência; a média arredondada zero não apaga uma
  flag bruta válida. O filtro GD=Sim é declarado e revalidado nos dois serviços.
- INT-03 conta IDs distintos de ocorrência por alimentador do evento e abertura
  UTC. Evento associado a duas UCs conta uma vez. C11 e cobertura mensal
  continuam obrigatórios; DEC/FEC mantêm seus grãos, unidades e denominadores.
- FAT-11 consome a decomposição V3 materializada. Confere janelas anuais
  equivalentes, estado CALCULADA_BASE_COMUM, origem da publicação, contadores por
  linha e identidade dos sete componentes financeiros. A síntese recebe todos
  os componentes classificados e as janelas reais; não recalcula via prompt.
  Ausência de configuração/base/cobertura ou mistura de estados não vira zero.
- A interpretação de agrupamento preserva município e classe mesmo quando
  existe bairro homônimo. A guarda usa os valores do perfil enriquecido pelo
  envelope interno; não aceita qualquer rótulo vindo da evidência.

### Acesso local autorizado

O provisionamento e sua matriz de verificação acrescentam somente:
`variacao_consumo_uc(municipio, possui_gd, consumo_medio_inicial,
consumo_medio_final, meses_com_leitura_p1, meses_com_leitura_p2,
queda_consumo_superior_30_pct)`; `ocorrencias_uc(id_ocorrencia, alimentador,
data_abertura)`; e as colunas analíticas/metadados já versionados de
`decomposicao_receita`. Aplicado no PostgreSQL local após autorização expressa.
Sem escrita, cadastro pessoal ou texto de chamados. O ensaio descartável prova
as negativas de acesso e mantém somente as colunas autorizadas.

### Verificações e aceite

- GenAI: 3.979 aprovados e três skips de ambiente, após catálogo/contratos ampliados.
- Backend completo: 858 aprovados e 101 skips; PostgreSQL restrito separado:
  90 testes aprovados na fatia ampliada, um aviso Starlette/httpx preexistente.
- Observação adicional no banco descartável `v_energy_test`: um teste aprovado.
  A primeira tentativa apontou nome de banco incompatível, sem alterar o teste
  para ignorar a proteção; a reexecução usou o banco descartável exigido.
- Runner/matriz do 10A contra núcleo/catálogo ampliados: 305 aprovados.
- Rodada completa privada sobre Gold v2: 43 PASS, cinco BLOQUEADO, sete
  SEM_AMOSTRA_NO_LOTE e duas regressões técnicas separadas, sem falha inesperada.
  SQL, sessão, ACL e auditoria reais; modelo controlado. Não houve novas chamadas
  Gemini. Contas temporárias removidas ao terminar.
- A pessoa usuária aprovou o aceite técnico local de FAT-09/FAT-11/CON-06/CON-07/CON-08,
  somando 22 casos numéricos aprovados localmente. Isso não certifica cobertura
  mensal nem substitui revisão de Dados/negócio ou jornada final no portal.

### Pendências reais

FAT-08 precisa de medida de recebimento comprovada. INT-01/02/03 e ATE-01 precisam
certificação mensal válida da origem; sete casos precisam amostras reais ainda
não encontradas. SEG-06/07 são regressões HTTP/PostgreSQL executadas separadamente,
sem PASS Gold artificial. Revisão de Dados e jornada visual final continuam
pendentes. A integração do PR #99 deve ocorrer depois desta implementação para
que a matriz possa referenciar as métricas novas sem duplicar commits.

Estado sincronizado no Trello: **9/10** entregáveis técnicos; aceite real integral por cenário permanece pendente.

Tentativa de jornada visual em 01/11/2026: portal isolado na porta 5183 e Backend com modelo controlado preparados; a ferramenta de navegador recusou acesso com `Local browser use is disabled in Work settings`. Nenhuma jornada foi declarada aprovada. O ambiente visual foi encerrado; nenhuma conta visual chegou a ser criada.
