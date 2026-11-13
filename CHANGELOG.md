# Changelog

Todas as mudanças relevantes deste projeto são documentadas aqui.
O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [2.0.0] - 2026-11-13

### Corrigido
- `main.py` importava o pacote `operix/`, que não existia no repositório (o sistema não abria). O pacote foi criado de fato.
- Senhas eram gravadas em texto puro e a tela de login vinha preenchida com o admin.
- Conexões SQLite nunca eram fechadas (`with sqlite3.connect()` só faz commit).
- Valor `1.5` era gravado como `15` (todo ponto era removido).
- Aprovar orçamento/concluir OS não conferiam a empresa nem o status atual no banco.
- Cadastro duplicava clientes com o mesmo CPF e não permitia mais de um veículo por cliente.
- Testes de integração falhavam (3 de 3) por falta de dados iniciais.

### Adicionado
- Arquitetura em camadas: `database`, `models`, `services`, `ui`, `reports`.
- Migrações versionadas com conversão automática do banco da versão anterior.
- OS com itens (peças + mão de obra), desconto, fluxo de 8 status e histórico.
- Estoque: baixa automática na aprovação, estorno no cancelamento, entradas, ajustes e alerta de mínimo.
- Pagamentos parciais, contas a receber e dashboard financeiro.
- Histórico por placa.
- PDFs de orçamento, ordem de serviço, recibo e relatório financeiro.
- Perfis Administrador / Atendente / Mecânico com permissões verificadas nos serviços.
- Validação de CPF, CNPJ, placa (antiga e Mercosul), telefone e e-mail, com máscaras na digitação.
- Interface com ttkbootstrap: tabelas com busca e ordenação, atalhos de teclado e avisos (toasts).
- Tratador central de erros com log em arquivo.
- Assistente de primeiro acesso e modo `--demo`.
- 56 testes automatizados e CI no GitHub Actions (Windows).

### Removido
- `login_app (1).py` (protótipo em arquivo único, substituído pelo pacote `operix`).

## [1.0.0] - 2026-10-20 (documentado, mas o código não foi publicado)

### Adicionado
- Estrutura modular em pacote (`models`, `services`, `ui`, `database`, `security`)
- Hash de senhas com PBKDF2-SHA256 e salt, com migração automática de senhas antigas
- Validação de valores monetários (`150`, `150,50`, `1.250,90`)
- Exceções de negócio tipadas (`ValidacaoError`, `AutenticacaoError`, `RegraDeNegocioError`)
- Modelo `Equipamento` e fábrica `criar_ativo`
- Suíte de testes com pytest e integração contínua (GitHub Actions)
- Documentação: README, arquitetura com diagramas, guia de contribuição e screenshots

### Alterado
- Aprovar orçamento e concluir OS agora validam status e empresa (não é mais possível aprovar duas vezes ou concluir uma OS já concluída)
- Valores exibidos em formato monetário brasileiro; tabelas com barra de rolagem
- Login também pode ser confirmado com a tecla Enter
- Ponto de entrada passou de `login_app.py` para `main.py` (ou `python -m operix`)

### Corrigido
- Texto do dashboard não promete mais "baixa de estoque" (funcionalidade ainda no roadmap)

## [0.1.0]

- Versão inicial: protótipo em um único arquivo com login, dashboard, clientes, orçamentos e ordens de serviço.
