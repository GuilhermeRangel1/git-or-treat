# Cobertura do protótipo e revisão

Use o PRD atual como autoridade. Esta matriz ajuda a organizar frames e caminhos de revisão; não define rotas, nomes de colunas, fórmulas ou estados operacionais aprovados.

## Jornadas e conteúdo

| Jornada | IDs a rastrear | Conteúdo e percurso a representar nos dois temas |
| --- | --- | --- |
| Diretoria / panorama | WEB-01, WEB-07 | Competências comparáveis, filtros, indicadores com unidade/definição, atualização e navegação ao recorte mantendo contexto. |
| Comercial / receita | WEB-02, WEB-07; apoio a ENT-01 | Receita residencial e comparação temporal; separar preço efetivo/volume e reajuste homologado; explorar município, bairro e classe; exibir contribuição absoluta e limites da evidência. |
| Atendimento / UC 360 | WEB-03 | Buscar por número de UC; reunir cliente/cadastro, consumo, faturas, medidor e histórico, GD, interrupções e chamados; diferenciar UC inexistente de fonte ausente. |
| Perdas / fila | WEB-04, WEB-07 | Prioridade, motivo, indicadores usados e energia potencialmente recuperável; abrir detalhe e iniciar ordem; linguagem de suspeita. |
| Perdas / ordens | WEB-05 | Criar, alterar status, registrar resultado e cancelar; mostrar confirmação, erro e repetição. Transições e regras de simultaneidade dependem de decisão operacional. |
| Operação | WEB-06, WEB-07; dependência DE-05 | Evolução e ordenação de DEC/FEC simplificados por alimentador; investigar ocorrências; fórmula/denominador disponíveis ou explicitamente pendentes. |
| Assistente e insight contextual | IA-01 a IA-06 | Acesso dentro do portal, pergunta em português, esclarecimento de ambiguidade, resposta fundamentada, insuficiência e indisponibilidade; ao menos um insight vinculado aos filtros/período da tela. |

DE-04, DE-06 e DE-08 sustentam dados, integração e definições das telas. ENT-01 depende de diagnóstico real; a visualização é apenas apoio. IA-06 exige controles e testes no sistema, que uma mensagem de recusa desenhada não comprova.

**Diferenciais a selecionar:** WEB-08 (exportar fila), WEB-09 (importar resultados e revisar erros/duplicatas), WEB-10 (perfis/autorização), IA-07 (follow-up). WEB-11, IA-08 e DE-09 são testes da implementação, não telas obrigatórias. Descreva os diferenciais escolhidos sem promovê-los a exigência do case.

## Matriz de trabalho

Registre uma linha por critério ou cenário relevante:

| ID / critério do PRD | Jornada / frame e link | Tema | Estado | Ação → destino / resultado visível | Fonte ou hipótese | Evidência / pendência |
| --- | --- | --- | --- | --- | --- | --- |

Preencha a matriz com o inventário acordado. Para o mesmo cenário, vincule as versões Claro e Escuro. O nome do frame pode incluir ID e jornada; use o ID real retornado pelo MCP nos links e no registro.

## Estados transversais

Cubra onde forem pertinentes: carregamento; sucesso; vazio legítimo; dados parciais/desatualizados; erro com nova tentativa; base pequena; denominador zero; filtro alterado e insight ainda não recalculado. Registre indisponibilidade como tal, sem convertê-la em zero. Filtros globais/locais e a preservação de contexto precisam ser reconhecíveis.

Respostas de IA quantitativas mostram unidade, período, filtros, fonte/trilha e ressalvas; diferenciam observação de interpretação e admitem falta de evidência. Esquemas e consultas ainda desconhecidos ficam como pendência, sem inventar SQL. A trilha visível preserva privacidade e omite credenciais/detalhes internos.

## Revisão de aceitação do design

- Conferir as quatro páginas e a paridade das jornadas, estados e interações entre temas.
- Percorrer início → decisão → detalhe/ação → retorno de cada jornada; revisar filtros, cancelamento e recuperação de erro. Verificar destinos de navegação e overlays, além de setas desenhadas.
- Inspecionar componentes reutilizados, variantes/propriedades, auto-layout, modos e vínculos semânticos. Os valores dos temas precisam estar definidos e aplicados aos frames corretos.
- Conferir textos, unidades, legenda, escalas, períodos e atualização; para dados sintéticos, verificar rótulo ilustrativo e coerência visual das séries.
- Revisar contraste com valores medidos, foco visível especificado, alternativa textual de gráficos e uso de sinais além de cor. Como referência de revisão, propor WCAG 2.2 AA; registrar esse alvo como proposta até acordado. Teclado, leitor de tela e comportamento responsivo real exigem validação na aplicação.
- Inspecionar capturas em zoom legível dos frames de cada tema e dos estados críticos. Corrigir cortes, sobreposição, hierarquia confusa e diferenças sem justificativa. Revalidar somente o que a correção afetou.

## Evidência e limite de conclusão

Entregue link do arquivo, links dos frames, matriz preenchida, capturas revisadas, decisões e pendências. Use o modelo do PRD §14 e identifique a evidência como **preparação** ou **protótipo**. Navegação simulada, contraste desenhado e componentes não comprovam Gold, API, segurança, acessibilidade executável ou diagnóstico; os IDs funcionais permanecem abertos até satisfazer o PRD com dados e aplicação reais.
