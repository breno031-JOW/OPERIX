# Como contribuir com o Operix

Obrigado pelo interesse em contribuir! Siga os passos abaixo.

## Preparando o ambiente

```bash
git clone https://github.com/breno031-JOW/OPERIX.git
cd OPERIX
python -m venv .venv
source .venv/bin/activate      # Linux/macOS
.venv\Scripts\activate         # Windows
pip install -r requirements-dev.txt
```

## Fluxo de trabalho

1. Crie uma branch a partir da `main`: `git checkout -b feat/minha-feature`
2. Faça as alterações e adicione testes quando mexer em regra de negócio (`operix/services/`)
3. Rode os testes e o linter:

   ```bash
   pytest
   ruff check .
   ```

4. Faça o commit seguindo o padrão abaixo e envie a branch
5. Abra um Pull Request descrevendo o que mudou e por quê

## Padrão de commits

Usamos mensagens curtas no formato `tipo: descrição`:

| Tipo | Quando usar |
|---|---|
| `feat` | nova funcionalidade |
| `fix` | correção de bug |
| `docs` | documentação |
| `refactor` | mudança de código sem alterar comportamento |
| `test` | criação ou ajuste de testes |
| `chore` | tarefas de manutenção |

Exemplo: `feat: adiciona edição de clientes`

## Regras do código

- Regras de negócio ficam em `operix/services/`, **nunca** nas telas. As telas só chamam serviços.
- Os serviços não podem importar `tkinter`.
- Toda consulta deve filtrar por `empresa_id` (isolamento entre empresas).
- Use *type hints* e docstrings nas funções públicas.
- Nunca grave senhas em texto puro: use `operix.security.gerar_hash`.
