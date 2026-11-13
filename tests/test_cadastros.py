"""Autenticação, cadastros, isolamento entre empresas e migração do banco antigo."""

import sqlite3

import pytest

from operix.database import Database
from operix.errors import AutenticacaoError, NaoEncontradoError, RegraNegocioError, ValidacaoError
from operix.models import StatusOrdem
from operix.security import hash_senha
from operix.services import AuthService, Servicos


def test_primeiro_acesso_e_login(db, admin):
    auth = AuthService(db)
    assert not auth.precisa_configuracao_inicial()
    with pytest.raises(RegraNegocioError):
        auth.configurar_primeiro_acesso("X", "", "Y", "y@y.com", "senha123", "senha123")
    assert auth.autenticar("ADMIN@teste.com ", "senha123").usuario.nome == "Admin"
    with pytest.raises(AutenticacaoError):
        auth.autenticar("admin@teste.com", "errada")
    senha = db.escalar("SELECT senha_hash FROM usuarios")
    assert senha.startswith("pbkdf2_sha256$")


def test_usuario_inativo_nao_loga(db, admin, atendente):
    admin.usuarios.definir_ativo(atendente.sessao.usuario.id, False)
    with pytest.raises(AutenticacaoError, match="desativado"):
        AuthService(db).autenticar("ana@teste.com", "senha123")


def test_nao_remove_ultimo_admin(admin):
    with pytest.raises(RegraNegocioError):
        admin.usuarios.definir_ativo(admin.sessao.usuario.id, False)
    with pytest.raises(RegraNegocioError):
        admin.usuarios.atualizar(admin.sessao.usuario.id, {"nome": "Admin", "email": "admin@teste.com",
                                                           "perfil": "Atendente"})


def test_cliente_documento_duplicado(admin):
    admin.clientes.criar({"nome": "A", "documento": "529.982.247-25"})
    with pytest.raises(RegraNegocioError, match="CPF/CNPJ"):
        admin.clientes.criar({"nome": "B", "documento": "52998224725"})
    with pytest.raises(ValidacaoError):
        admin.clientes.criar({"nome": "C", "documento": "123.456.789-00"})


def test_placa_duplicada_e_km(admin, cenario):
    with pytest.raises(RegraNegocioError, match="placa"):
        admin.veiculos.criar(cenario["cliente"], {"placa": "abc1234", "modelo": "Outro"})
    with pytest.raises(ValidacaoError):  # km não pode regredir
        admin.veiculos.atualizar(cenario["veiculo"], {"placa": "ABC1234", "modelo": "Corolla", "km_atual": 10})


def test_busca_cliente(admin, cenario):
    assert len(admin.clientes.listar("carl")) == 1
    assert len(admin.clientes.listar("abc-12")) == 1   # pela placa
    assert len(admin.clientes.listar("52998")) == 1    # pelo CPF
    assert admin.clientes.listar("zzz") == []


def test_inativar_cliente_com_os_aberta(admin, cenario):
    admin.ordens.criar({"cliente_id": cenario["cliente"], "veiculo_id": cenario["veiculo"]})
    with pytest.raises(RegraNegocioError):
        admin.clientes.definir_ativo(cenario["cliente"], False)


def test_isolamento_entre_empresas(db, admin, cenario):
    with db.conexao() as conn:
        empresa2 = conn.execute("INSERT INTO empresas (nome) VALUES ('Outra')").lastrowid
        conn.execute("INSERT INTO usuarios (empresa_id, nome, email, senha_hash, perfil) VALUES (?, ?, ?, ?, ?)",
                     (empresa2, "Intruso", "intruso@x.com", hash_senha("senha123"), "Administrador"))
    intruso = Servicos(db, AuthService(db).autenticar("intruso@x.com", "senha123"))
    assert intruso.clientes.listar() == []
    with pytest.raises(NaoEncontradoError):
        intruso.clientes.obter(cenario["cliente"])
    with pytest.raises(NaoEncontradoError):
        intruso.estoque.obter(cenario["oleo"])


def test_estoque_entrada_e_ajuste(admin, cenario):
    admin.estoque.entrada(cenario["filtro"], "5", "12,00")
    peca = admin.estoque.obter(cenario["filtro"])
    assert peca.estoque == 6 and peca.custo_centavos == 1200
    admin.estoque.ajustar(cenario["filtro"], "0", "Inventário")
    assert admin.estoque.obter(cenario["filtro"]).estoque == 0
    with pytest.raises(RegraNegocioError):
        admin.estoque.criar({"codigo": "fi", "descricao": "Duplicada", "preco": "1"})


def test_migracao_banco_legado(tmp_path):
    """Banco do protótipo (senha em texto, valores REAL) é convertido sem perda."""
    caminho = tmp_path / "legado.db"
    conn = sqlite3.connect(caminho)
    conn.executescript("""
        CREATE TABLE empresas (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, tipo_negocio TEXT NOT NULL);
        CREATE TABLE usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, empresa_id INTEGER, nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL, senha TEXT NOT NULL, perfil TEXT NOT NULL);
        CREATE TABLE clientes (id INTEGER PRIMARY KEY AUTOINCREMENT, empresa_id INTEGER, nome TEXT NOT NULL,
            documento TEXT NOT NULL, telefone TEXT, email TEXT);
        CREATE TABLE ativos (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER, tipo TEXT NOT NULL,
            identificador TEXT NOT NULL, detalhes TEXT);
        CREATE TABLE orcamentos (id INTEGER PRIMARY KEY AUTOINCREMENT, empresa_id INTEGER, cliente_id INTEGER,
            ativo_id INTEGER, status TEXT NOT NULL, desconto REAL DEFAULT 0.0, total REAL DEFAULT 0.0, data_criacao TEXT);
        CREATE TABLE ordens_servico (id INTEGER PRIMARY KEY AUTOINCREMENT, orcamento_id INTEGER UNIQUE, tecnico TEXT,
            status TEXT NOT NULL, data_inicio TEXT);
        INSERT INTO empresas VALUES (1, 'Oficina Mecânica Pro', 'Oficina Mecânica');
        INSERT INTO usuarios VALUES (1, 1, 'Administrador', 'admin@operix.com', '1234', 'Administrador');
        INSERT INTO clientes VALUES (1, 1, 'Carlos Silva', '123.456.789-00', '(31) 98888-7777', 'c@e.com');
        INSERT INTO clientes VALUES (2, 1, 'Carlos Duplicado', '12345678900', NULL, NULL);
        INSERT INTO ativos VALUES (1, 1, 'Veiculo', 'ABC-1234', 'Toyota Corolla 2020');
        INSERT INTO ativos VALUES (2, 2, 'Veiculo', 'XYZ9876', 'Gol');
        INSERT INTO orcamentos VALUES (1, 1, 1, 1, 'Aprovado', 0, 1250.90, '2026-10-01 10:00');
        INSERT INTO orcamentos VALUES (2, 1, 2, 2, 'Pendente', 0, 99.99, '2026-10-02 10:00');
        INSERT INTO ordens_servico VALUES (1, 1, 'Técnico', 'Concluída', '2026-10-01 11:00');
    """)
    conn.commit()
    conn.close()

    db = Database(caminho)
    assert db.versao() == 1
    sessao = AuthService(db).autenticar("admin@operix.com", "1234")  # senha antiga continua valendo
    s = Servicos(db, sessao)
    assert db.escalar("SELECT senha_hash FROM usuarios").startswith("pbkdf2_sha256$")
    assert len(s.clientes.listar()) == 1  # documentos repetidos unificados
    assert len(s.veiculos.listar()) == 2
    ordens = {o["numero"]: o for o in s.ordens.listar()}
    assert ordens[1]["status"] == StatusOrdem.CONCLUIDA.value and ordens[1]["total"] == 125090
    assert ordens[2]["status"] == StatusOrdem.ORCAMENTO.value and ordens[2]["total"] == 9999
    assert not {"_legado_usuarios", "orcamentos"} & {
        r[0] for r in db.consultar("SELECT name FROM sqlite_master WHERE type='table'")}
    Database(caminho)  # reabrir não reaplica a migração
