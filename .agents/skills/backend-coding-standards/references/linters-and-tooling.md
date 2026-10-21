# Ferramentas e verificações do backend

## Descobrir antes de configurar

Leia `backend/requirements.txt`, `backend/README.md`, configurações presentes e `.github/workflows/quality.yml`. Este backend usa pip e pytest; não presuma que uv, Ruff, Pyright, Pylint ou import-linter estejam configurados porque outro serviço ou um guia externo os utiliza.

Na pasta `backend`, com o ambiente correto:

```bash
python -m pytest -q
python -m compileall -q app tests scripts
```

Sem PostgreSQL descartável configurado, testes de integração podem ser pulados; informe isso. Confira no README as verificações Docker e de migração aplicáveis à mudança. Testes de contrato HTTP e de banco têm propósitos distintos.

## Se a tarefa incluir novas ferramentas

Adote somente o que resolver um problema observado; configure versão, escopo e execução reproduzível na CI. Proponha uma mudança separada quando a adoção ampliar o escopo. Ruff pode cobrir lint/formatação; Pyright, tipos; import-linter, limites de importação. Um teste de arquitetura específico também pode bastar.

Ao configurar Ruff, use códigos válidos da versão escolhida: por exemplo `C901` para complexidade e `E741` para nomes ambíguos, não rótulos descritivos de regras como se fossem seletores. Alinhe `target-version` ao Python suportado. Ajuste exceções de testes/migrações por necessidade real e confira incompatibilidades entre regras e formatter; não copie uma configuração extensa sem executá-la.

Não atribua garantias que a ferramenta não fornece: lint não comprova ausência de I/O bloqueante, autorização, segurança de SQL ou reconciliação de métricas. Compileall valida sintaxe, não contratos nem dependências em execução. Um type checker não valida JSON externo.

## Ao relatar o resultado

Registre comando, ambiente e resultado realmente observados. Diferencie falha, teste pulado e verificação não executada. Rode verificações proporcionais ao comportamento alterado e os gates obrigatórios existentes; repita após correções que possam afetá-los.

Para criar ou alterar objetos PostgreSQL, use também a skill `supabase-postgres-best-practices`; ela orienta PostgreSQL e não exige adotar o produto Supabase. Atualizações de imagem/dependências exigem nova verificação da base e da imagem final; um scan anterior não garante ausência futura de vulnerabilidades.

Fontes: [seletores do Ruff](https://docs.astral.sh/ruff/linter/#rule-selection), [configuração Pyright](https://microsoft.github.io/pyright/#/configuration) e [contratos import-linter](https://import-linter.readthedocs.io/en/stable/contract_types/).
