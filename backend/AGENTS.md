# Regras de backend

Leia `../docs/services/backend.md` e os IDs WEB/IA relevantes de `../docs/PRD.md`.

- Trate Gold como fonte analítica; mantenha ordens de inspeção em dados operacionais separados.
- Valide parâmetros, paginação, autorização e transições no servidor.
- Mantenha o acesso da IA somente leitura.
- Reconcilie contratos e métricas com o dicionário Gold.
- Não exponha segredos nem SQL interno nas respostas.
- Execute as verificações do serviço antes de marcar requisitos como concluídos.
