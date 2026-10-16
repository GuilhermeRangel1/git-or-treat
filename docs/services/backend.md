# Serviço: backend e banco local

**Escopo:** sustenta WEB-01 a WEB-11 e IA-01 a IA-06 do [PRD](../PRD.md). **Estado:** especificado, sem API ou banco criados. **Stack do case:** FastAPI em Python; SQLite, PostgreSQL ou alternativa justificada.

## Responsabilidade

Importar tabelas Gold exportadas, servir recortes consistentes ao portal, manter estado das ordens de inspeção e disponibilizar acesso controlado ao agente. Gold é a fonte analítica; ordens/status/resultados digitados no portal são dados operacionais e devem ter modelo e trilha separados para não sobrescrever a extração.

## Contratos a definir antes de implementar

| Domínio | Operações necessárias | Condições de aceite |
| --- | --- | --- |
| Indicadores | Métricas agregadas, comparação temporal, filtros geográficos e por classe | Resposta inclui unidade, janela, filtros e metadados de atualização; reconcilia com Gold |
| Receita | Série e decomposição preço-volume | Valor total fecha com componentes; recortes não duplicam fatos |
| UC | Busca e resumo 360 | Histórico de consumo, fatura, medidor, GD, interrupções e chamados, com paginação e ausências claras |
| Inspeção | Listar fila, detalhar evidência, criar/alterar/cancelar ordem, registrar resultado | Prioridade explicável; validação e trilha de transições; idempotência para repetição |
| Operação | DEC/FEC por alimentador/período e ocorrências | Mesma fórmula da Gold, sem rótulo de conformidade regulatória |
| IA | Consulta controlada às Gold e trilha da resposta | Credencial somente leitura, allowlist de tabelas, limite/timeout de consultas |

Os endpoints e contratos JSON são **a definir** junto do frontend e agente; não há nomes de rota prescritos no case. Versionar contrato, paginação, erro, tipos, nulidade e exemplos sem dados pessoais no momento da implementação.

### Envelope conceitual de uma resposta analítica

O contrato final pode variar, mas cada resposta que sustenta um número deve permitir identificar: valor e unidade; período/competências; filtros efetivamente aplicados; população/denominador; versão ou data do lote Gold; indicador de cobertura/qualidade; definição do dicionário; e estado de indisponibilidade. Expor metadados por resposta ou por um contrato comum, conforme decisão da equipe. Não inventar campos da extração para preencher o envelope.

| Caso | Decisão que o contrato precisa explicitar |
| --- | --- |
| Filtro por município/bairro/classe | IDs/nomes válidos, hierarquia de filtros, comportamento para combinação impossível e preservação da granularidade. |
| Competência e comparação | Inclusão dos extremos, janelas incompletas e diferença entre competência de fatura, data de pagamento e momento de atualização. |
| Busca de UC | Identificação estável, autorização para ver dados pessoais, histórico com páginas e resposta quando a UC não existe ou não tem certa fonte. |
| Exportação | Mesmo recorte/ordem da tela, limite de tamanho e metadados de geração, caso WEB-08 seja implementado. |
| Erros | Códigos e mensagens distinguem entrada inválida, ausência legítima, dependência indisponível e falha interna. |

## Regras de segurança e consistência

- Segredos via ambiente/gerenciador; nunca no frontend ou Git.
- Validação de entradas, parâmetros e escopo de filtros no servidor; consulta ao banco parametrizada.
- Garantir autorização de escrita das ordens; se WEB-10 for implementado, mapear perfis para leitura e ações.
- Separar usuário/credencial de leitura da IA do usuário de escrita operacional.
- Informar competência, atualização e proveniência nas respostas para evitar interpretações falsas.
- Erros não expõem SQL, stack trace, dados de terceiros ou credenciais ao navegador.

## Ordens de inspeção: ciclo operacional a decidir

WEB-05 exige criar, atualizar status, registrar resultado e cancelar. Antes de implementar, definir estados permitidos, transições, quem pode executá-las, campos mínimos e vínculo com a versão da fila que motivou a ordem. Preservar trilha de criação, alterações e cancelamento. Uma UC pode ser priorizada novamente; a regra para ordens simultâneas e repetição da mesma requisição deve ser explícita. Inspeções históricas do Excel não devem ser tratadas automaticamente como ordens novas do portal.

## Carga da Gold e consistência

Registrar o lote exportado, esquema e contagens por tabela. Uma carga só passa a servir consultas depois que tabelas dependentes estiverem consistentes entre si; a segunda execução do mesmo lote precisa produzir os mesmos totais. Alterações na fórmula Gold exigem atualização coordenada do dicionário, API, portal, IA e diagnóstico. Testar um mesmo recorte no Databricks, banco local e resposta da API. Se o banco escolhido não suportar separação robusta de permissões, documentar controles compensatórios para o agente de IA antes de afirmar que consultas são somente leitura.

## Qualidade

Testar filtros combinados, estados vazios, UC inexistente, IDs inválidos, paginação, ordenação, idempotência da carga e transições das ordens. Quando houver alterações em métrica, fazer teste de contrato com amostra Gold reconciliada. Se PostgreSQL for escolhido, consultar a skill local `supabase-postgres-best-practices`; isso não impõe uso da plataforma Supabase.

WEB-11 pede testes automatizados como diferencial; a conclusão dos requisitos obrigatórios ainda requer verificação funcional e numérica reproduzível mesmo que esse diferencial não seja perseguido. Registrar no PRD quais fluxos e contratos foram testados, com comando/resultado e lote de dados.
