CREATE TABLE IF NOT EXISTS empresas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    tipo_negocio TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER,
    nome TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    senha TEXT NOT NULL,
    perfil TEXT NOT NULL,
    FOREIGN KEY(empresa_id) REFERENCES empresas(id)
);

CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER,
    nome TEXT NOT NULL,
    documento TEXT NOT NULL,
    telefone TEXT,
    email TEXT,
    FOREIGN KEY(empresa_id) REFERENCES empresas(id)
);

CREATE TABLE IF NOT EXISTS ativos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER,
    tipo TEXT NOT NULL,
    identificador TEXT NOT NULL,
    detalhes TEXT,
    FOREIGN KEY(cliente_id) REFERENCES clientes(id)
);

CREATE TABLE IF NOT EXISTS orcamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER,
    cliente_id INTEGER,
    ativo_id INTEGER,
    status TEXT NOT NULL,
    desconto REAL DEFAULT 0.0,
    total REAL DEFAULT 0.0,
    data_criacao TEXT,
    FOREIGN KEY(empresa_id) REFERENCES empresas(id),
    FOREIGN KEY(cliente_id) REFERENCES clientes(id),
    FOREIGN KEY(ativo_id) REFERENCES ativos(id)
);

CREATE TABLE IF NOT EXISTS ordens_servico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    orcamento_id INTEGER UNIQUE,
    tecnico TEXT,
    status TEXT NOT NULL,
    data_inicio TEXT,
    FOREIGN KEY(orcamento_id) REFERENCES orcamentos(id)
);
