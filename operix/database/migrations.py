"""Migrações versionadas do esquema (controladas por ``PRAGMA user_version``).

Para evoluir o banco, acrescente uma nova função ``_migracao_N`` na lista
``MIGRACOES``. Cada migração roda uma única vez, dentro de uma transação.

A migração 1 cria o esquema completo do Operix 2 e, se encontrar um banco da
versão anterior (protótipo ``login_app.py``), converte os dados existentes:
senhas em texto puro viram hash, valores em reais viram centavos, clientes com
documento repetido são unificados e orçamentos/OS antigos viram ordens.
"""

import logging
import sqlite3

log = logging.getLogger(__name__)

STATUS_ORDEM = (
    "ORCAMENTO", "APROVADA", "REPROVADA", "EM_EXECUCAO",
    "AGUARDANDO_PECA", "CONCLUIDA", "ENTREGUE", "CANCELADA",
)
PERFIS = ("Administrador", "Atendente", "Mecanico")
FORMAS_PAGAMENTO = ("Dinheiro", "PIX", "Cartão de Débito", "Cartão de Crédito", "Boleto", "Transferência")

_LISTA_STATUS = ", ".join(f"'{s}'" for s in STATUS_ORDEM)
_LISTA_PERFIS = ", ".join(f"'{p}'" for p in PERFIS)
_LISTA_FORMAS = ", ".join(f"'{f}'" for f in FORMAS_PAGAMENTO)
_AGORA = "(strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))"

ESQUEMA_V1 = [
    f"""CREATE TABLE empresas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        tipo_negocio TEXT NOT NULL DEFAULT 'Oficina Mecânica',
        cnpj TEXT,
        telefone TEXT,
        email TEXT,
        endereco TEXT,
        criado_em TEXT NOT NULL DEFAULT {_AGORA}
    )""",
    f"""CREATE TABLE usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id INTEGER NOT NULL REFERENCES empresas(id),
        nome TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE COLLATE NOCASE,
        senha_hash TEXT NOT NULL,
        perfil TEXT NOT NULL CHECK (perfil IN ({_LISTA_PERFIS})),
        ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
        criado_em TEXT NOT NULL DEFAULT {_AGORA}
    )""",
    f"""CREATE TABLE clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id INTEGER NOT NULL REFERENCES empresas(id),
        nome TEXT NOT NULL,
        documento TEXT NOT NULL,
        telefone TEXT,
        email TEXT,
        endereco TEXT,
        observacoes TEXT,
        ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
        criado_em TEXT NOT NULL DEFAULT {_AGORA},
        UNIQUE (empresa_id, documento)
    )""",
    f"""CREATE TABLE veiculos (
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
        criado_em TEXT NOT NULL DEFAULT {_AGORA},
        UNIQUE (empresa_id, placa)
    )""",
    f"""CREATE TABLE pecas (
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
        criado_em TEXT NOT NULL DEFAULT {_AGORA},
        UNIQUE (empresa_id, codigo)
    )""",
    """CREATE TABLE servicos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id INTEGER NOT NULL REFERENCES empresas(id),
        descricao TEXT NOT NULL,
        preco_centavos INTEGER NOT NULL DEFAULT 0 CHECK (preco_centavos >= 0),
        ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
        UNIQUE (empresa_id, descricao)
    )""",
    f"""CREATE TABLE ordens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id INTEGER NOT NULL REFERENCES empresas(id),
        numero INTEGER NOT NULL,
        cliente_id INTEGER NOT NULL REFERENCES clientes(id),
        veiculo_id INTEGER NOT NULL REFERENCES veiculos(id),
        mecanico_id INTEGER REFERENCES usuarios(id),
        status TEXT NOT NULL DEFAULT 'ORCAMENTO' CHECK (status IN ({_LISTA_STATUS})),
        km_entrada INTEGER CHECK (km_entrada IS NULL OR km_entrada >= 0),
        defeito_relatado TEXT,
        diagnostico TEXT,
        observacoes TEXT,
        desconto_centavos INTEGER NOT NULL DEFAULT 0 CHECK (desconto_centavos >= 0),
        estoque_baixado INTEGER NOT NULL DEFAULT 0 CHECK (estoque_baixado IN (0, 1)),
        criado_por INTEGER REFERENCES usuarios(id),
        criado_em TEXT NOT NULL DEFAULT {_AGORA},
        aprovado_em TEXT,
        concluido_em TEXT,
        entregue_em TEXT,
        cancelado_em TEXT,
        UNIQUE (empresa_id, numero)
    )""",
    f"""CREATE TABLE ordem_itens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ordem_id INTEGER NOT NULL REFERENCES ordens(id) ON DELETE CASCADE,
        tipo TEXT NOT NULL CHECK (tipo IN ('PECA', 'SERVICO')),
        peca_id INTEGER REFERENCES pecas(id),
        servico_id INTEGER REFERENCES servicos(id),
        descricao TEXT NOT NULL,
        quantidade REAL NOT NULL CHECK (quantidade > 0),
        valor_unitario_centavos INTEGER NOT NULL CHECK (valor_unitario_centavos >= 0),
        criado_em TEXT NOT NULL DEFAULT {_AGORA},
        CHECK (tipo = 'SERVICO' OR peca_id IS NOT NULL)
    )""",
    f"""CREATE TABLE ordem_historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ordem_id INTEGER NOT NULL REFERENCES ordens(id) ON DELETE CASCADE,
        status_anterior TEXT,
        status_novo TEXT NOT NULL,
        usuario_id INTEGER REFERENCES usuarios(id),
        observacao TEXT,
        data TEXT NOT NULL DEFAULT {_AGORA}
    )""",
    f"""CREATE TABLE pagamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id INTEGER NOT NULL REFERENCES empresas(id),
        ordem_id INTEGER NOT NULL REFERENCES ordens(id),
        valor_centavos INTEGER NOT NULL CHECK (valor_centavos > 0),
        forma TEXT NOT NULL CHECK (forma IN ({_LISTA_FORMAS})),
        data TEXT NOT NULL DEFAULT {_AGORA},
        usuario_id INTEGER REFERENCES usuarios(id),
        observacao TEXT
    )""",
    f"""CREATE TABLE movimentos_estoque (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id INTEGER NOT NULL REFERENCES empresas(id),
        peca_id INTEGER NOT NULL REFERENCES pecas(id),
        tipo TEXT NOT NULL CHECK (tipo IN ('ENTRADA', 'SAIDA', 'AJUSTE', 'ESTORNO')),
        quantidade REAL NOT NULL,
        saldo_apos REAL NOT NULL,
        ordem_id INTEGER REFERENCES ordens(id),
        usuario_id INTEGER REFERENCES usuarios(id),
        observacao TEXT,
        data TEXT NOT NULL DEFAULT {_AGORA}
    )""",
    "CREATE INDEX idx_usuarios_empresa ON usuarios(empresa_id)",
    "CREATE INDEX idx_clientes_empresa ON clientes(empresa_id, nome)",
    "CREATE INDEX idx_veiculos_cliente ON veiculos(cliente_id)",
    "CREATE INDEX idx_pecas_empresa ON pecas(empresa_id, descricao)",
    "CREATE INDEX idx_ordens_empresa_status ON ordens(empresa_id, status)",
    "CREATE INDEX idx_ordens_veiculo ON ordens(veiculo_id)",
    "CREATE INDEX idx_ordens_mecanico ON ordens(mecanico_id)",
    "CREATE INDEX idx_itens_ordem ON ordem_itens(ordem_id)",
    "CREATE INDEX idx_historico_ordem ON ordem_historico(ordem_id)",
    "CREATE INDEX idx_pagamentos_ordem ON pagamentos(ordem_id)",
    "CREATE INDEX idx_pagamentos_data ON pagamentos(empresa_id, data)",
    "CREATE INDEX idx_movimentos_peca ON movimentos_estoque(peca_id, data)",
]

_TABELAS_LEGADAS = ("ordens_servico", "orcamentos", "ativos", "clientes", "usuarios", "empresas")


def _tabelas(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _colunas(conn: sqlite3.Connection, tabela: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({tabela})")}


def _e_banco_legado(conn: sqlite3.Connection) -> bool:
    return "usuarios" in _tabelas(conn) and "senha" in _colunas(conn, "usuarios")


def _migracao_1(conn: sqlite3.Connection) -> None:
    """Esquema completo do Operix 2 (+ conversão do banco do protótipo)."""
    legado = _e_banco_legado(conn)
    if legado:
        log.info("Banco da versão anterior detectado: convertendo dados.")
        existentes = _tabelas(conn)
        for tabela in _TABELAS_LEGADAS:
            if tabela in existentes:
                conn.execute(f"ALTER TABLE {tabela} RENAME TO _legado_{tabela}")

    for comando in ESQUEMA_V1:
        conn.execute(comando)

    if legado:
        _converter_legado(conn)
        for tabela in _TABELAS_LEGADAS:
            conn.execute(f"DROP TABLE IF EXISTS _legado_{tabela}")


def _converter_legado(conn: sqlite3.Connection) -> None:
    """Copia os dados do protótipo para o novo esquema."""
    # Importações locais para evitar dependência circular no carregamento do pacote
    from operix.security import hash_senha
    from operix.utils.validators import normalizar_placa, somente_digitos

    existentes = _tabelas(conn)

    def legado(tabela: str) -> list[dict]:
        if f"_legado_{tabela}" not in existentes:
            return []
        cursor = conn.execute(f"SELECT * FROM _legado_{tabela} ORDER BY id")
        nomes = [d[0] for d in cursor.description]
        return [dict(zip(nomes, linha, strict=True)) for linha in cursor.fetchall()]

    for e in legado("empresas"):
        conn.execute(
            "INSERT INTO empresas (id, nome, tipo_negocio) VALUES (?, ?, ?)",
            (e["id"], e["nome"], e["tipo_negocio"] or "Oficina Mecânica"),
        )

    for u in legado("usuarios"):
        perfil = u["perfil"] if u["perfil"] in PERFIS else "Atendente"
        conn.execute(
            "INSERT INTO usuarios (id, empresa_id, nome, email, senha_hash, perfil) VALUES (?, ?, ?, ?, ?, ?)",
            (u["id"], u["empresa_id"], u["nome"], u["email"], hash_senha(u["senha"] or ""), perfil),
        )

    # Clientes: unifica documentos repetidos dentro da mesma empresa
    mapa_clientes: dict[int, int] = {}
    vistos: dict[tuple, int] = {}
    empresa_do_cliente: dict[int, int] = {}
    for c in legado("clientes"):
        documento = somente_digitos(c["documento"]) or (c["documento"] or f"SEM-DOC-{c['id']}")
        chave = (c["empresa_id"], documento)
        if chave in vistos:
            mapa_clientes[c["id"]] = vistos[chave]
            continue
        conn.execute(
            "INSERT INTO clientes (id, empresa_id, nome, documento, telefone, email) VALUES (?, ?, ?, ?, ?, ?)",
            (c["id"], c["empresa_id"], c["nome"], documento, somente_digitos(c.get("telefone")) or None, c.get("email")),
        )
        vistos[chave] = c["id"]
        mapa_clientes[c["id"]] = c["id"]
        empresa_do_cliente[c["id"]] = c["empresa_id"]

    # Ativos -> veículos (placa normalizada, sem duplicar dentro da empresa)
    mapa_veiculos: dict[int, int] = {}
    placas: dict[tuple, int] = {}
    for a in legado("ativos"):
        cliente_id = mapa_clientes.get(a["cliente_id"])
        if cliente_id is None:
            continue
        empresa_id = empresa_do_cliente[cliente_id]
        placa = normalizar_placa(a["identificador"]) or f"SEMPLACA{a['id']}"
        chave = (empresa_id, placa)
        if chave in placas:
            mapa_veiculos[a["id"]] = placas[chave]
            continue
        observacao = None if a["tipo"] == "Veiculo" else f"Migrado como {a['tipo']}"
        conn.execute(
            "INSERT INTO veiculos (id, empresa_id, cliente_id, placa, modelo, observacoes) VALUES (?, ?, ?, ?, ?, ?)",
            (a["id"], empresa_id, cliente_id, placa, a["detalhes"], observacao),
        )
        placas[chave] = a["id"]
        mapa_veiculos[a["id"]] = a["id"]

    # Orçamentos + OS -> ordens (com um item de serviço com o valor total antigo)
    os_por_orcamento = {o["orcamento_id"]: o for o in legado("ordens_servico")}
    numeros: dict[int, int] = {}
    for orc in legado("orcamentos"):
        cliente_id = mapa_clientes.get(orc["cliente_id"])
        veiculo_id = mapa_veiculos.get(orc["ativo_id"])
        if cliente_id is None or veiculo_id is None:
            log.warning("Orçamento legado %s ignorado (cliente/ativo inexistente)", orc["id"])
            continue
        os_antiga = os_por_orcamento.get(orc["id"])
        if os_antiga:
            status = "CONCLUIDA" if os_antiga["status"] == "Concluída" else "EM_EXECUCAO"
        else:
            status = "APROVADA" if orc["status"] == "Aprovado" else "ORCAMENTO"
        numeros[orc["empresa_id"]] = numeros.get(orc["empresa_id"], 0) + 1
        criado_em = orc["data_criacao"] or None
        cursor = conn.execute(
            f"""INSERT INTO ordens (empresa_id, numero, cliente_id, veiculo_id, status, observacoes,
                    criado_em, aprovado_em, concluido_em)
                VALUES (?, ?, ?, ?, ?, ?, COALESCE(?, {_AGORA}), ?, ?)""",
            (
                orc["empresa_id"], numeros[orc["empresa_id"]], cliente_id, veiculo_id, status,
                f"Migrado da versão anterior (orçamento #{orc['id']})",
                criado_em,
                os_antiga["data_inicio"] if os_antiga else None,
                os_antiga["data_inicio"] if os_antiga and status == "CONCLUIDA" else None,
            ),
        )
        total_centavos = int(round(float(orc["total"] or 0) * 100))
        if total_centavos > 0:
            conn.execute(
                """INSERT INTO ordem_itens (ordem_id, tipo, descricao, quantidade, valor_unitario_centavos)
                   VALUES (?, 'SERVICO', 'Serviço (valor migrado da versão anterior)', 1, ?)""",
                (cursor.lastrowid, total_centavos),
            )
        conn.execute(
            "INSERT INTO ordem_historico (ordem_id, status_novo, observacao) VALUES (?, ?, 'Migração de dados')",
            (cursor.lastrowid, status),
        )


MIGRACOES = [_migracao_1]


def aplicar(conn: sqlite3.Connection) -> None:
    """Executa as migrações pendentes, cada uma em sua própria transação."""
    versao_atual = conn.execute("PRAGMA user_version").fetchone()[0]
    pendentes = MIGRACOES[versao_atual:]
    if not pendentes:
        return

    nivel_original = conn.isolation_level
    conn.isolation_level = None  # controle manual de transação
    conn.execute("PRAGMA foreign_keys = OFF")  # necessário para renomear/recriar tabelas
    try:
        for indice, migracao in enumerate(pendentes, start=versao_atual + 1):
            conn.execute("BEGIN")
            try:
                migracao(conn)
                problemas = conn.execute("PRAGMA foreign_key_check").fetchall()
                if problemas:
                    raise sqlite3.IntegrityError(f"Migração {indice} gerou chaves estrangeiras inválidas: {problemas[:5]}")
                conn.execute(f"PRAGMA user_version = {indice}")
                conn.execute("COMMIT")
                log.info("Migração %s aplicada", indice)
            except BaseException:
                conn.execute("ROLLBACK")
                raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.isolation_level = nivel_original
