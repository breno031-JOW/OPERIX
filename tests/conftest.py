"""Fixtures compartilhadas: banco temporário, oficina configurada e sessões por perfil."""

import pytest

from operix import config
from operix.database import Database
from operix.services import AuthService, Servicos


@pytest.fixture(autouse=True)
def hash_rapido(monkeypatch):
    """Reduz as iterações do PBKDF2 para os testes rodarem rápido."""
    monkeypatch.setattr(config, "PBKDF2_ITERACOES", 1_000)


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "teste.db")


@pytest.fixture
def admin(db) -> Servicos:
    sessao = AuthService(db).configurar_primeiro_acesso(
        "Oficina Teste", "", "Admin", "admin@teste.com", "senha123", "senha123"
    )
    return Servicos(db, sessao)


def _login(db, email, senha) -> Servicos:
    return Servicos(db, AuthService(db).autenticar(email, senha))


@pytest.fixture
def atendente(db, admin) -> Servicos:
    admin.usuarios.criar({"nome": "Ana", "email": "ana@teste.com", "perfil": "Atendente",
                          "senha": "senha123", "confirmacao": "senha123"})
    return _login(db, "ana@teste.com", "senha123")


@pytest.fixture
def mecanico(db, admin) -> Servicos:
    admin.usuarios.criar({"nome": "Zé", "email": "ze@teste.com", "perfil": "Mecânico",
                          "senha": "senha123", "confirmacao": "senha123"})
    return _login(db, "ze@teste.com", "senha123")


@pytest.fixture
def cenario(admin):
    """Cliente, veículo e duas peças com estoque."""
    cliente = admin.clientes.criar({"nome": "Carlos", "documento": "529.982.247-25", "telefone": "31988887777"})
    veiculo = admin.veiculos.criar(cliente, {"placa": "ABC-1234", "modelo": "Corolla", "km_atual": 1000})
    oleo = admin.estoque.criar({"codigo": "OL", "descricao": "Óleo", "unidade": "L", "custo": "20",
                                "preco": "40", "estoque_inicial": "10", "estoque_minimo": "2"})
    filtro = admin.estoque.criar({"codigo": "FI", "descricao": "Filtro", "custo": "10", "preco": "30",
                                  "estoque_inicial": "1"})
    return {"cliente": cliente, "veiculo": veiculo, "oleo": oleo, "filtro": filtro}
