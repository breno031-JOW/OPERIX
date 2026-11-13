-- Operix 2 - Modelo físico (SQLite)
-- Gerado a partir de operix/database/migrations.py (fonte oficial do esquema).
-- O banco é criado/atualizado automaticamente ao abrir o sistema; este arquivo é apenas documentação.

CREATE TABLE empresas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        tipo_negocio TEXT NOT NULL DEFAULT 'Oficina Mecânica',
        cnpj TEXT,
        telefone TEXT,
        email TEXT,
        endereco TEXT,
        criado_em TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
    );

CREATE TABLE usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id INTEGER NOT NULL REFERENCES empresas(id),
        nome TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE COLLATE NOCASE,
        senha_hash TEXT NOT NULL,
        perfil TEXT NOT NULL CHECK (perfil IN ('Administrador', 'Atendente', 'Mecanico')),
        ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
        criado_em TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
    );

CREATE TABLE clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id INTEGER NOT NULL REFERENCES empresas(id),
        nome TEXT NOT NULL,
        documento TEXT NOT NULL,
        telefone TEXT,
        email TEXT,
        endereco TEXT,
        observacoes TEXT,
        ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
        criado_em TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
        UNIQUE (empresa_id, documento)
    );

CREATE TABLE veiculos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id INTEGER NOT NULL REFERENCES empresas(id),
        cliente_id INTEGER NOT NULL REFERENCES clientes(id),
        placa TEXT NOT NULL,
        marca TEXT,
        modelo TEXT,
        ano INTEGER,
        cor TEXT,
        km_atual INTEGER NOT NULL DEFAULT 0 CHECK (km_atual >= 0),
        observacoes TEXT,
        ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
        criado_em TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
        UNIQUE (empresa_id, placa)
    );

CREATE TABLE pecas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id INTEGER NOT NULL REFERENCES empresas(id),
        codigo TEXT NOT NULL,
        descricao TEXT NOT NULL,
        unidade TEXT NOT NULL DEFAULT 'UN',
        custo_centavos INTEGER NOT NULL DEFAULT 0 CHECK (custo_centavos >= 0),
        preco_centavos INTEGER NOT NULL DEFAULT 0 CHECK (preco_centavos >= 0),
        estoque REAL NOT NULL DEFAULT 0 CHECK (estoque >= 0),
        estoque_minimo REAL NOT NULL DEFAULT 0 CHECK (estoque_minimo >= 0),
        ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
        criado_em TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
        UNIQUE (empresa_id, codigo)
    );

CREATE TABLE servicos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id INTEGER NOT NULL REFERENCES empresas(id),
        descricao TEXT NOT NULL,
        preco_centavos INTEGER NOT NULL DEFAULT 0 CHECK (preco_centavos >= 0),
        ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
        UNIQUE (empresa_id, descricao)
    );

CREATE TABLE ordens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id INTEGER NOT NULL REFERENCES empresas(id),
        numero INTEGER NOT NULL,
        cliente_id INTEGER NOT NULL REFERENCES clientes(id),
        veiculo_id INTEGER NOT NULL REFERENCES veiculos(id),
        mecanico_id INTEGER REFERENCES usuarios(id),
        status TEXT NOT NULL DEFAULT 'ORCAMENTO' CHECK (status IN ('ORCAMENTO', 'APROVADA', 'REPROVADA', 'EM_EXECUCAO', 'AGUARDANDO_PECA', 'CONCLUIDA', 'ENTREGUE', 'CANCELADA')),
        km_entrada INTEGER CHECK (km_entrada IS NULL OR km_entrada >= 0),
        defeito_relatado TEXT,
        diagnostico TEXT,
        observacoes TEXT,
        desconto_centavos INTEGER NOT NULL DEFAULT 0 CHECK (desconto_centavos >= 0),
        estoque_baixado INTEGER NOT NULL DEFAULT 0 CHECK (estoque_baixado IN (0, 1)),
        criado_por INTEGER REFERENCES usuarios(id),
        criado_em TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
        aprovado_em TEXT,
        concluido_em TEXT,
        entregue_em TEXT,
        cancelado_em TEXT,
        UNIQUE (empresa_id, numero)
    );

CREATE TABLE ordem_itens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ordem_id INTEGER NOT NULL REFERENCES ordens(id) ON DELETE CASCADE,
        tipo TEXT NOT NULL CHECK (tipo IN ('PECA', 'SERVICO')),
        peca_id INTEGER REFERENCES pecas(id),
        servico_id INTEGER REFERENCES servicos(id),
        descricao TEXT NOT NULL,
        quantidade REAL NOT NULL CHECK (quantidade > 0),
        valor_unitario_centavos INTEGER NOT NULL CHECK (valor_unitario_centavos >= 0),
        criado_em TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
        CHECK (tipo = 'SERVICO' OR peca_id IS NOT NULL)
    );

CREATE TABLE ordem_historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ordem_id INTEGER NOT NULL REFERENCES ordens(id) ON DELETE CASCADE,
        status_anterior TEXT,
        status_novo TEXT NOT NULL,
        usuario_id INTEGER REFERENCES usuarios(id),
        observacao TEXT,
        data TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
    );

CREATE TABLE pagamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id INTEGER NOT NULL REFERENCES empresas(id),
        ordem_id INTEGER NOT NULL REFERENCES ordens(id),
        valor_centavos INTEGER NOT NULL CHECK (valor_centavos > 0),
        forma TEXT NOT NULL CHECK (forma IN ('Dinheiro', 'PIX', 'Cartão de Débito', 'Cartão de Crédito', 'Boleto', 'Transferência')),
        data TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
        usuario_id INTEGER REFERENCES usuarios(id),
        observacao TEXT
    );

CREATE TABLE movimentos_estoque (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id INTEGER NOT NULL REFERENCES empresas(id),
        peca_id INTEGER NOT NULL REFERENCES pecas(id),
        tipo TEXT NOT NULL CHECK (tipo IN ('ENTRADA', 'SAIDA', 'AJUSTE', 'ESTORNO')),
        quantidade REAL NOT NULL,
        saldo_apos REAL NOT NULL,
        ordem_id INTEGER REFERENCES ordens(id),
        usuario_id INTEGER REFERENCES usuarios(id),
        observacao TEXT,
        data TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
    );

CREATE INDEX idx_usuarios_empresa ON usuarios(empresa_id);

CREATE INDEX idx_clientes_empresa ON clientes(empresa_id, nome);

CREATE INDEX idx_veiculos_cliente ON veiculos(cliente_id);

CREATE INDEX idx_pecas_empresa ON pecas(empresa_id, descricao);

CREATE INDEX idx_ordens_empresa_status ON ordens(empresa_id, status);

CREATE INDEX idx_ordens_veiculo ON ordens(veiculo_id);

CREATE INDEX idx_ordens_mecanico ON ordens(mecanico_id);

CREATE INDEX idx_itens_ordem ON ordem_itens(ordem_id);

CREATE INDEX idx_historico_ordem ON ordem_historico(ordem_id);

CREATE INDEX idx_pagamentos_ordem ON pagamentos(ordem_id);

CREATE INDEX idx_pagamentos_data ON pagamentos(empresa_id, data);

CREATE INDEX idx_movimentos_peca ON movimentos_estoque(peca_id, data);
