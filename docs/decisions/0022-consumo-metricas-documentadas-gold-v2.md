# ADR-0022 — Consumo das métricas documentadas na Gold v2

**Data:** 01/11/2026.
**Estado:** adotada para implementação e validação local, conforme a orientação da
pessoa usuária para usar as regras de Dados existentes; homologação do negócio e
certificação da origem não são presumidas.
**IDs:** IA-01, IA-02, IA-03 e IA-06; GENAI-10A/10B.

## Contexto

O dicionário e `data-engineering/notebook/Silver_to_gold.ipynb` já definem a
decomposição de receita, a variação fixa de consumo e a distinção entre ocorrência
e par UC–ocorrência. A ausência do consumidor GenAI estava sendo descrita de modo
impreciso como ausência de regra. A pessoa usuária autorizou usar essas referências
e ampliou expressamente a leitura local das colunas necessárias em 01/11/2026.

## Opções consideradas

1. Continuar tratando todas as capacidades como definição pendente, apesar das
   regras já documentadas; isso impede validar o consumidor.
2. Inferir janelas, tarifa, recebimento ou causas a partir dos agregados; isso
   altera a semântica da fonte e não atende ao PRD.
3. Consumir as definições publicadas, revalidando recorte, origem, controles e
   estados no fluxo existente, com limitações explícitas. Esta é a opção adotada.

## Decisão

- Receita e consumo comparam dois meses explícitos e ordenados, no mesmo recorte.
  A seleção contém somente os dois meses; não soma os meses intermediários.
  Percentual exige base bruta positiva. Comparação anual sem janelas equivalentes
  pede esclarecimento. As regras relativas da ADR-0018 permanecem aplicáveis.
- O ranking de perda de consumo por bairro usa a diferença absoluta antes do
  arredondamento, com desempate estável pelo bairro. Todos os grupos precisam dos
  dois meses; falta de um deles impede publicar um ranking parcial. O banco
  classifica os grupos antes do limite de saída.
- GD usa P1 julho/2022–junho/2023 e P2 julho/2025–junho/2026, com ao menos seis
  meses com leitura por janela e flag bruta de queda estritamente superior a 30%.
  C08/C09 precisam passar para a mesma publicação e população da Visão 360.
  Média publicada arredondada para zero não apaga uma elegibilidade bruta válida.
  A resposta identifica a população elegível; ausência de comparação não vira
  ausência de queda, e GD não prova origem solar nem causalidade.
- Interrupções contam IDs distintos por alimentador do evento e mês de abertura
  em UTC. Um evento associado a várias UCs conta uma vez. DEC/FEC preservam suas
  unidades e denominadores; cobertura mensal insuficiente continua bloqueada.
- Preço/volume consome somente `CALCULADA_BASE_COMUM`, método
  `PARES_MES_UC_PRECO_OBSERVADO_VOLUME_INTERACAO_V3`, duas janelas anuais equivalentes
  e origem Silver/Bronze da publicação atual. Confere todas as parcelas e
  contadores por linha antes de agregar. Preço, volume, interação e quatro
  parcelas de composição precisam reconciliar a variação total. Cobertura de
  consumo e faturamento é exigida nas competências das duas janelas.
- Contagens de UCs somadas entre recortes são apresentadas como participações,
  preservando a limitação do dicionário; não representam UCs únicas globais.

## Consequências e verificação

Backend continua sendo o único executor, com consultas construídas por código,
papel restrito e mesma autorização, publicação e auditoria. O núcleo recebe
observações minimizadas e componentes classificados; o modelo não calcula a
fórmula nem escolhe um resultado para ocultar as demais parcelas.

Os testes HTTP e PostgreSQL usam valores artificiais independentes; a conferência
local usa também o lote Gold v2 autorizado e SQL de controle separado. Os
resultados e limites ficam em [GENAI-10B](../contracts/genai-domain-implementation.md)
e no relatório sanitizado do GENAI-10A. Resultados privados e credenciais não são
versionados. A referência dos controles C01–C12 está em
[cobertura Gold](../gold-coverage-v0.md).

A mudança não aprova receita recebida, não fabrica amostras ausentes e não
homologa os quatro domínios. Mudança de janelas, método, grão ou elegibilidade
exige atualizar dicionário, catálogo, controles e esta decisão antes de liberar
outra semântica.
