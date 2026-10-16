# Regras de engenharia de dados

Leia `../docs/services/data-engineering.md` e os IDs DE de `../docs/PRD.md`.

- Preserve Bronze como extração rastreável.
- Documente e teste toda transformação Silver.
- Declare granularidade, fórmula e fonte de cada tabela Gold.
- Controle cardinalidade antes de unir fatos.
- Compare contagens e somas entre origem, Delta, CSV exportado e banco.
- Use apenas colunas observadas no dataset; registre ambiguidades em vez de inventar schema.
