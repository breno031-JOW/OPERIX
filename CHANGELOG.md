# Changelog

Todas as mudanças relevantes deste projeto são documentadas aqui.
O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [1.0.0] - 2026-10-20

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
