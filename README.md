<div align="center">

# 🛠️ Operix

**Gestão inteligente para oficinas mecânicas**

Sistema desktop em Python para controlar o ciclo completo da oficina: cliente e veículo → orçamento → ordem de serviço → estoque → pagamento → entrega → histórico.

[![CI](https://github.com/breno031-JOW/OPERIX/actions/workflows/ci.yml/badge.svg)](https://github.com/breno031-JOW/OPERIX/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![GUI](https://img.shields.io/badge/GUI-Tkinter%20%2B%20ttkbootstrap-informational)
![SQLite](https://img.shields.io/badge/Database-SQLite3-003B57?logo=sqlite&logoColor=white)
![Tests](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

</div>

---

## 🚀 Funcionalidades

**Operação**
- 📋 **Ordens de serviço completas:** abertura com km e defeito relatado, mecânico responsável, diagnóstico, observações e histórico de cada mudança de status.
- 🔄 **Fluxo de status:** Orçamento → Aprovada → Em execução ⇄ Aguardando peça → Pronta p/ entrega → Entregue (com Reprovada e Cancelada). Só as transições válidas aparecem como botões.
- 🧮 **Orçamento com itens:** peças do estoque + mão de obra (livre ou do catálogo), desconto e totais automáticos.
- 📦 **Estoque com baixa automática:** ao aprovar a OS as peças saem do estoque. Se faltar saldo, nada é baixado e o sistema lista o que falta. Peças incluídas depois saem na hora, e ao cancelar a OS voltam ao estoque. Inclui entrada de mercadoria, ajuste de inventário, alerta de estoque mínimo e extrato de movimentações.
- 🔎 **Histórico por placa:** todas as OS, peças trocadas, km e gasto total do veículo.
- 💳 **Pagamentos:** parciais ou totais em várias formas (PIX, cartão, dinheiro…). A entrega exige quitação ou confirmação de saldo em aberto.

**Gestão**
- 📊 **Painel** com orçamentos pendentes, carros em execução, aguardando peça, prontos para entrega e estoque baixo. Os cartões são clicáveis.
- 💰 **Financeiro:** recebido no período, faturamento, ticket médio, contas a receber, receita de mão de obra, lucro bruto em peças, recebimentos por forma e peças mais usadas.
- 📄 **PDFs:** orçamento (com campo de autorização), ordem de serviço (com garantia), recibo e relatório financeiro, com os dados da oficina no cabeçalho.

**Segurança e qualidade**
- 🔒 Senhas com hash **PBKDF2-SHA256 + salt**, primeiro acesso guiado (sem senha padrão).
- 👥 **Perfis de acesso:** Administrador, Atendente e Mecânico (veja a tabela em [docs/ARQUITETURA.md](docs/ARQUITETURA.md)).
- ✅ Validação de **CPF/CNPJ** (dígitos verificadores), **placa** antiga e Mercosul, telefone, e-mail e valores (`150`, `150,50`, `1.250,90`).
- 🛡️ Erros nunca fecham o programa: avisos claros para o usuário e detalhes técnicos em `operix.log`.
- 🏢 Isolamento por empresa (multiempresa) em todas as consultas.

**Usabilidade**
- Tabelas com **busca instantânea** (sem diferenciar acentos), ordenação por coluna e cores por status.
- **Máscaras** de CPF/CNPJ, telefone, placa e moeda enquanto digita.
- **Atalhos:** `F2`/`Ctrl+N` novo · `F3`/`Ctrl+F` buscar · `F5` atualizar · `Enter` abrir/salvar · `Esc` cancelar · `Ctrl+1…8` menu · `Delete` remove item da OS.
- Avisos discretos de sucesso (toast) e confirmação antes de ações irreversíveis.

## 🏁 Como executar no Windows

### Pré-requisitos
- **Python 3.10 ou superior** ([python.org](https://www.python.org/downloads/)). Na instalação, marque *"Add python.exe to PATH"*. O Tkinter já vem junto.

### Passo a passo (PowerShell ou Prompt de Comando)

```bash
git clone https://github.com/breno031-JOW/OPERIX.git
```

```bash
cd OPERIX
```

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

> No PowerShell, se aparecer erro de "execução de scripts desabilitada", rode uma vez:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

```bash
pip install -r requirements.txt
```

```bash
python main.py
```

Na primeira execução o Operix abre o **assistente de primeiro acesso**: você cadastra a oficina e o usuário administrador. O banco `operix.db` é criado automaticamente na pasta do projeto.

### Quer testar com dados de exemplo?

Em um banco **vazio** (por exemplo, apontando para outro arquivo):

```bash
python main.py --demo --banco demo.db
```

| Perfil | E-mail | Senha |
|---|---|---|
| Administrador | `admin@demo.com` | `admin123` |
| Atendente | `atendente@demo.com` | `atend123` |
| Mecânico | `mecanico@demo.com` | `mec123` |

> Contas apenas para demonstração. Nunca use `--demo` no banco real da oficina.

### Já usava a versão anterior?

Basta abrir o Operix 2 com o mesmo `operix.db`: a migração automática converte os dados. As senhas viram hash e o login antigo continua funcionando; valores são convertidos, clientes com o mesmo documento são unificados e orçamentos/OS antigos viram ordens com o valor preservado. **Faça uma cópia do arquivo antes, por segurança.**

### Opções e arquivos

| O quê | Padrão | Como mudar |
|---|---|---|
| Banco de dados | `operix.db` na pasta do projeto | `--banco caminho.db` ou variável `OPERIX_DB` |
| PDFs gerados | pasta `documentos/` | variável `OPERIX_DOCS` |
| Log de erros | `operix.log` | variável `OPERIX_LOG` |

## 🧪 Testes

```bash
pip install -r requirements-dev.txt
```

```bash
pytest
```

São 56 testes cobrindo validações, moeda, senhas, cadastros, isolamento entre empresas, permissões por perfil, o fluxo completo da OS (estoque, pagamentos, entrega, cancelamento), histórico por placa, PDFs e a migração do banco antigo.

## 🗂️ Arquitetura

Camadas separadas: `database` → `models` → `services` (regras de negócio, testáveis sem interface) → `ui` / `reports`. Detalhes, diagrama de estados da OS e matriz de permissões em [docs/ARQUITETURA.md](docs/ARQUITETURA.md). O esquema do banco está em [Operix_Modelo_Fisico.sql](Operix_Modelo_Fisico.sql).

## 🗺️ Próximos passos sugeridos

- [ ] Empacotamento em executável (`.exe`) com PyInstaller
- [ ] Backup automático do banco
- [ ] Envio do orçamento por WhatsApp/e-mail
- [ ] Agenda de serviços e lembrete de revisão por km/data
- [ ] Suporte a PostgreSQL para várias máquinas em rede

## 🤝 Como contribuir

Veja o guia em [CONTRIBUTING.md](CONTRIBUTING.md).

## 📄 Licença

Distribuído sob a licença MIT. Consulte o arquivo [LICENSE](LICENSE).

## 👤 Autor

Desenvolvido por [@breno031-JOW](https://github.com/breno031-JOW).
Danilonunes.9102
Ygor Ricardo
jhomjhomdanix-prog
drumondfe
analuizzaslps@gmail.com
