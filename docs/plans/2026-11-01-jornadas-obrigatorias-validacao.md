# Jornadas obrigatórias — validação para apresentação

Referências: requisitos WEB-01 a WEB-07 no [PRD](../PRD.md), [dicionário Gold](../dicionario_gold.md) e contratos de [UC](../contracts/uc360-gold-v2.md), [Inspeções](../contracts/inspection-gold-v2.md) e [Receita](../contracts/revenue-dev03.md). Esta lista não substitui o aceite de cada requisito nem certifica o conjunto inteiro de dados.

## Percursos a demonstrar

1. Panorama: abrir indicadores, ajustar competência e filtros e verificar origem, unidades e estado das métricas.
2. Receita: investigar município, bairro e classe. A decomposição usa janelas publicadas pela Gold; o filtro de alimentador não é suportado nessa decomposição. Preço observado e consumo medido não são tarifa homologada ou energia faturada.
3. Atendimento: buscar uma UC, observar o período, consumo, faturas, possível medidor, cadastro de GD, interrupções, chamados e tratativas. A quantidade em aberto e a data de pagamento são declarações de origem, não saldo ou recebimento confirmados.
4. Perdas: verificar posição, motivo, evidências e detalhe; criar e acompanhar uma ordem com perfil autorizado. A referência histórica por inspeção não é previsão individual de recuperação.
5. Operação: abrir ranking, detalhe e ocorrências observadas por alimentador, conferindo período e ressalvas sobre cobertura e vínculo cadastral. DEC/FEC são simplificados.

## Evidência e pendências

Em 01/11/2026, testes HTTP autenticados locais retornaram sucesso para Panorama, Receita, busca e overview de UC, históricos de faturas e tratativas, fila, opções e ocorrências de Operação. O navegador mostrou uma amostra da UC com tratativas e o detalhe de um alimentador com paginação de ocorrências. Estas observações não são uma revisão integral de todos os recortes, perfis, estados responsivos ou da reconciliação numérica da plataforma.

- WEB-04: desenvolver e validar com Dados/Produto uma previsão individual se for exigida no aceite. A Gold atual publica referência histórica por inspeção com limites de teste temporal, não valor individual. A proposta não deve converter a média diretamente em recuperação garantida; depende de validação fora da amostra, viés de seleção, intervalo, elegibilidade, uso de dados anteriores e decisão explícita do time. O trabalho não altera a Gold nesta rodada.
- WEB-02/ENT-01: a análise publicada usa consumo medido e preço observado; energia faturada e recebimento não podem ser reconstruídos sem fonte e definição adequadas. Validar recortes, janelas e reconciliação com responsáveis pelo diagnóstico.
- WEB-03: titular restrito e confirmação de recebimento exigem fonte e autorização próprias; ausência permanece explícita. O resumo de faturas não é posição contábil atual nem inclui pagamentos parciais.
- WEB-03: comparação lado a lado dos últimos meses com os mesmos meses do ano anterior ainda requer implementação e validação de cobertura; a comparação atual usa os extremos do período selecionado e não deve ser apresentada como série interanual completa.
- WEB-01/03/04/05/06/07: simular a demonstração completa com perfis apropriados, incluindo alteração de ordens em ambiente e conta autorizados, e testar estados vazios/erros e apresentação responsiva. Não se declara conclusão integral por uma única amostra.

O Assistente é acompanhado pela equipe responsável e não foi alterado nesta entrega.
