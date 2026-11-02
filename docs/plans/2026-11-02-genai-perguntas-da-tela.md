# Perguntas da tela e apresentação Gold — 02/11/2026

Requisitos: IA-01, IA-02 e IA-06. Branch `fix/genai-prontidao-gold-local`, após `e88ca22`, com alterações locais. Fonte `gold.local`, perfil `v-energy-grid-360-gold`, contrato `gold-csv-v2`, catálogo `gold-catalog-v2`, schema `gold_v2`.

## Problema e comportamento entregue

O lote tem nomes iguais em município e bairro. As perguntas naturais das capturas usavam “em Recife”; a matriz anterior qualificava “no município de Recife”. Os casos FAT-01, FAT-04 e CON-01 agora usam as formas naturais efetivamente enviadas pela tela, com os mesmos controles SQL e critérios numéricos anteriores.

- “Em <nome>” seleciona o município quando o nome autorizado está simultaneamente no município e em um bairro. A regra usa a hierarquia declarada no perfil; não busca lugares externos ou cria valores. “No bairro <nome>” continua bairro, e um nome compartilhado sem qualificação continua pedindo esclarecimento. Escopo e catálogo são revalidados na síntese.
- “No bairro Brasília Teimosa, em Recife” preserva bairro, município e classe residencial. Receita e consumo “em Recife” selecionam somente o município, sem acrescentar bairro.
- A contagem inteira acumulada usa separador brasileiro e frase direta: “No histórico acumulado, foram registrados 318.871 chamados de atendimento.” Unidade e período estruturados continuam sendo protocolos e histórico acumulado; não se inventa intervalo mensal. Valores fracionários não são arredondados para parecerem inteiros.
- Um relatório da publicação atual com capacidade bloqueada exclusivamente por falta de cobertura/fonte/período retorna HTTP 503 `service_unavailable`, `retryable=false`, com explicação de cobertura insuficiente. Falha de controle, aprovação ou publicação permanece distinta. A recusa ocorre antes do executor quantitativo e do modelo.

Caminho: Assistente → API pública Backend → planejamento GenAI → prontidão → executor Gold restrito → síntese/auditoria → resposta validada pelo consumidor. Foram estendidos interpretador, apresentação determinística e tratamento da prontidão existentes.

## Evidência reproduzível

- Regressões HTTP das três frases exatas, com Recife também registrado como bairro e cobertura em junho/2026: filtros, métrica e período corretos. Controles negativos mantêm bairro explicitamente qualificado e esclarecimento para nome compartilhado sem qualificação.
- Suíte completa GenAI: **4.165 passaram, 5 skips** (smoke opt-in, symlink Windows e DSNs ausentes). Duas expectativas históricas precisaram acompanhar a convenção “em <município>” e o texto principal atualizado da matriz. Após a redação final da contagem, os testes HTTP e do runner foram repetidos: **130 passaram**.
- Backend completo, fixtures isoladas SQLite/sintéticas e documentos atuais montados: **907 passaram, 114 skips**, aviso preexistente Starlette/httpx. Casos dirigidos distinguem cobertura ausente de controle pendente e publicação inválida; a resposta HTTP não expõe detalhes privados.
- `python -m ruff check .` no GenAI, Ruff dos arquivos Backend alterados e `git diff --check`: passaram.

Conversa real pela API pública com Gemini e histórico das últimas três mensagens, reproduzindo as seis perguntas das capturas: `browser-20261102T110712_817469Z`, **cinco respostas numéricas reconciliadas e um bloqueio esperado**, zero divergências. B01/FAT-01: 15,79 s; B02/FAT-04: 15,69 s; B03/CON-01: 15,42 s; B04/AMB-04: 16,72 s; B05/ATE-03: 15,33 s; B06/INT-01: bloqueado em 14,30 s, com mensagem de cobertura insuficiente e sem repetição automática. A trilha confirmou modelo concluído nas cinco respostas numéricas e zero contas temporárias remanescentes. O texto final da contagem foi revalidado em `browser-20261102T111107_778524Z`: B05 PASS, HTTP 200 em 14,95 s.

Harness privado: `backend python /repo/work/genai-assistente-cleanup/run_browser_phrases_real.py`; somente B05: acrescentar `B05`. Compose Gold local, worktree montada somente leitura e saída privada gravável em `work/genai-local-validation/`. Credenciais são criadas em memória e contas/sessões temporárias removidas no `finally`. Nenhuma ampliação de permissões, nova carga ou envio de linhas brutas/dados pessoais. As chamadas do modelo usam a chave privada já configurada.

## Alcance

A validação real reproduz a conversa pela API; não é uma nova jornada visual no navegador. Os serviços locais foram atualizados para essa versão. Não foi refeita a matriz completa de 57 casos nesta fatia: ela permanece histórica, e os seis casos acima cobrem a regressão das capturas. Cobertura de DEC/FEC e atendimento mensal continua pendente na fonte; não se concluem domínios ou estados oficiais por essas correções.

## Continuação — esclarecimentos dos exemplos do case

Uma pergunta completa de volume residencial após um esclarecimento de solar herdava o texto anterior e produzia duas métricas artificiais. O interpretador agora reconhece uma nova pergunta interrogativa completa antes de combinar uma resposta curta ao esclarecimento. A regressão de “Receita faturada” após “receita arrecadada” continua preservando município, classe e período. Solar passou a usar “Os dados identificam geração distribuída (GD)”, sem expor a versão interna da Gold ou afirmar fonte solar.

Sequência real `browser-20261102T112811_814003Z`, com os mesmos três textos das capturas e as últimas três mensagens de contexto: solar pede confirmação de GD (0,59 s); volume residencial pede “Qual período deve servir de base para essa comparação?” (0,66 s); receita comercial sem período pede “Qual período você quer consultar ou comparar?” (0,69 s). Três esclarecimentos esperados pela API local Gold v2, sem respostas numéricas ou novos aceites de domínio. Conta/sessões temporárias removidas. Harness privado: `work/genai-assistente-cleanup/run_case_clarifications_real.py`. Não houve alteração no Backend nesta continuação.

Regressões HTTP: **72 passaram**. Suíte GenAI final: **4.168 passaram, 5 skips**, com o mesmo comando completo e processo limpo anteriores; Ruff e diff passaram. Os testes verificam a mensagem exata de comparação com/sem contexto solar e o esclarecimento de período da receita. Não houve nova jornada visual ou matriz completa de 57 casos.

## Continuação — exemplos nas mensagens de esclarecimento

As respostas Gold que pedem esclarecimento agora tentam anexar “Exemplo de pergunta: …”. O planejador usa competências declaradas na publicação, nomes de mês em português e os filtros/pergunta atuais quando válidos. Para solar, o perfil declara um exemplo de GD com município publicado. O candidato só é exibido se passar pela interpretação, montagem do plano e aprovação no mesmo escopo; gerar o exemplo não consulta o banco nem chama o modelo. Sem competência publicada ou candidato autorizado, a mensagem não inventa uma opção. Um exemplo aprovado no plano não certifica cobertura ou disponibilidade futura da fonte.

O sufixo visual é separado do motivo ao processar contexto, para preservar respostas curtas de refinamento e período. O texto do exemplo copiado é tratado como uma nova pergunta completa e passa novamente pelos controles. Casos negativos verificam escopo restrito à métrica de consumo e competências vazias; casos positivos verificam a cópia de exemplos de múltiplos indicadores, período, comparação de bairro, local desconhecido e GD. O exemplo de comparação mantém classe residencial e agrupamento por bairro; a receita comercial mantém município e classe.

Suíte final: **4.176 passaram, 5 skips**; Ruff e `git diff --check` passaram. Harness privado `work/genai-assistente-cleanup/test_examples_real.py`: quatro esclarecimentos pela API Gold local, seguidos da cópia literal do exemplo com contexto, retornaram HTTP 200 `answered` e modelo concluído na auditoria:

- Receita: “Quero consultar receita faturada em junho de 2026.” — 19,06 s.
- GD: contagem com GD em Olinda e queda acima de 30% — 20,53 s.
- Bairro: volume residencial entre maio e junho/2026 — 19,56 s.
- Receita comercial em Jaboatão: crescimento entre maio e junho/2026 — 19,84 s.

Conta e sessões temporárias removidas. Essa prova verifica a usabilidade dos exemplos pela API e a conclusão do modelo; não acrescenta uma rodada de reconciliação SQL independente ou uma jornada visual à matriz anterior. Não houve nova carga, ampliação de permissões ou conclusão de domínios.
