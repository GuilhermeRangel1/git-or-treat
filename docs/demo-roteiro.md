# Roteiro de demonstração — DEV-16

**Estado:** roteiro preparado, ainda sem ensaio integral independente. ENT-02 exige narrativa executiva revisada e demonstração ao vivo; ENT-04 depende de outra pessoa reproduzir a instalação e as jornadas. Não apresentar dados reais publicamente até confirmação de confidencialidade.

## Preparação

1. Siga [instalação e inicialização](../README.md#executar-localmente-com-docker). Confirme loader concluído, serviços saudáveis e login; use contas por perfil. Separe uma UC e um recorte autorizados do lote carregado, sem registrá-los neste repositório. Cadastro pareado é necessário para apresentar dados cadastrais disponíveis.
2. Confirme o lote e período publicados, disponibilidade da chave do modelo e controles já aprovados. Tenha à mão o [dicionário](dicionario_gold.md), [diagnóstico](revenue-diagnosis.md) e [registro do Workflow](../data-engineering/evidencias/workflow/run-limpo-250327107715287.md). O run registrado é histórico: confirme que corresponde ao lote demonstrado antes de afirmar identidade.
3. Em caso de erro, consulte `docker compose ps -a` e `docker compose logs --tail 100 gold-loader backend ai-agent`. Uma fonte inválida impede a API; ausência de chave ou controle pode impedir a resposta da IA. Não substitua dados por números inventados.

## Jornadas

Para a apresentação de 15 minutos, use como referência a [narrativa executiva](apresentacao-diretoria.md), ajustando o tempo para demonstrar o Workflow, as jornadas e, quando disponível, o Assistente e o insight. A lista abaixo serve também para o ensaio completo.


1. **Dados:** apresente as seis tarefas do Workflow e a exportação Gold v2 no registro vinculado. Explique que a execução ocorreu no Databricks e que o Compose importa um pacote previamente gerado.
2. **Panorama e Receita:** entre como Comercial, escolha período, município e classe disponíveis; mostre indicadores, variação e recorte. Anote para conferência a métrica, unidade, período e lote. Consulte o dicionário para a definição e cobertura.
3. **Atendimento:** entre como Atendimento, busque uma UC autorizada e percorra histórico de consumo, faturas e eventos disponíveis. A ausência de cadastro ou de dado não deve ser apresentada como zero.
4. **Perdas e ordens:** entre como Perdas, examine a fila e os motivos; abra uma suspeita, crie uma ordem local e acompanhe seu estado em Ordens. A ação altera o banco local; identifique-a como demonstração e registre resultado apenas quando disponível.
5. **Operação:** entre como Operação, examine DEC/FEC por alimentador e período e explique a cobertura exibida. São indicadores simplificados, sem afirmação de conformidade regulatória.
6. **Assistente:** entre com perfil autorizado e pergunte pelo faturamento no mesmo município e período selecionados em Receita. Confira unidade, filtros, evidência e valor com a tela para o mesmo lote. Se houver ausência de evidência, erro ou diferença, registre a ocorrência; não declare reconciliação. Faça também uma pergunta fora do escopo e observe a recusa ou esclarecimento.
7. **Diretoria:** apresente a pergunta, método, decomposição, incertezas e recomendações do diagnóstico somente após revisão analítica. Preço efetivo não é tarifa homologada; consumo medido não é energia faturada; decomposição não prova causalidade. A narrativa executiva e seu aceite permanecem dependentes de ENT-01/ENT-02.

## Ensaio e aceite

Outra pessoa deve partir de um ambiente preparado, seguir o README sem orientação adicional e registrar data, versão/commit, ambiente, lote, comandos e resultados, jornadas executadas e falhas sem dados sensíveis. Confronte o resultado com ENT-02 a ENT-05 no [PRD](PRD.md). Evidência de um run histórico ou de testes isolados não substitui esse ensaio. O modo sintético descrito no README serve para explorar fila e ordens, não comprova o fluxo integrado com Gold ou o diagnóstico real.
