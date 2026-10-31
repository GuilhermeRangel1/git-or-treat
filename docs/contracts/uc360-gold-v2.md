# UC 360 — Gold CSV v2

Escopo WEB-03 e WEB-07, dependências DE-06 e DE-08. A busca usa `gold_v2.visao_360_uc`; o overview e cada histórico consultam individualmente a mesma UC e publicação, sem cruzar fatos de granularidades diferentes. A carga e as consultas compartilham o lock de publicação. Nome e referência pessoal vêm de cadastro restrito não carregado e permanecem nulos.

- `consumo_mensal_uc`: UC/competência, consumo medido e faturamento independentes; competência ausente não é zero. Leituras parcialmente inválidas não são apresentadas no gráfico como valor completo. Na comparação, valores observados têm status parcial e percentual indisponível sem cobertura individual certificada.
- `faturas_uc`: uma linha por fatura, com competência, valor faturado e vencimento observado. Valor pago, energia faturada, data e situação de pagamento permanecem indisponíveis: status ou data isolados não comprovam quitação. Ordenação por pagamento não é oferecida.
- `medidor_uc`: vínculos observados por UC, inclusive instalação ou retirada nula. O período não filtra o snapshot de vínculos. A interface não escolhe um medidor atual quando vigência ou sobreposição não estão resolvidas.
- `atendimentos_uc` e `ocorrencias_uc`: uma linha por protocolo ou par ocorrência/UC, filtrada pela abertura. Datas de abertura ausentes não entram no período e não são contadas como ausência de evento. Duração nula continua nula; minutos são convertidos em horas. A cobertura incompleta fica explícita.
- `gd_uc`: potência cadastrada em kWp, data e modalidade observadas são retornadas separadamente; não são kW instantâneo nem geração ou compensação mensal. Histórico de GD continua indisponível no contrato antigo.

Os históricos são paginados e ordenados no banco, com desempate por identificador. Página além do fim não transforma uma fonte observada em inexistente. O gráfico carrega todas as páginas necessárias e não une meses ausentes ou nulos. As chaves das consultas incluem UC, período e seção; respostas divergentes ou de outra publicação não substituem o contexto atual.

O teste privado opt-in `tests/test_gold_uc_v2_real.py` reconcilia uma UC e contagens por fonte com o PostgreSQL isolado. O pacote cadastral restrito, a homologação das regras de pagamento e vigência, a cobertura individual e a reconciliação de mais recortes continuam pendentes. Não conclui WEB-03.
