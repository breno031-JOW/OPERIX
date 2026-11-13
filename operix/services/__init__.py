"""Regras de negócio do Operix (independentes da interface gráfica)."""

from operix.database import Database
from operix.services.auth import AuthService
from operix.services.base import Sessao
from operix.services.clientes import ClienteService, VeiculoService
from operix.services.dashboard import DashboardService
from operix.services.estoque import CatalogoServicoService, EstoqueService
from operix.services.ordens import OrdemService
from operix.services.usuarios import EmpresaService, UsuarioService


class Servicos:
    """Fachada que reúne todos os serviços para a sessão do usuário logado."""

    def __init__(self, db: Database, sessao: Sessao):
        self.db = db
        self.sessao = sessao
        self.clientes = ClienteService(db, sessao)
        self.veiculos = VeiculoService(db, sessao)
        self.estoque = EstoqueService(db, sessao)
        self.catalogo = CatalogoServicoService(db, sessao)
        self.ordens = OrdemService(db, sessao)
        self.dashboard = DashboardService(db, sessao)
        self.usuarios = UsuarioService(db, sessao)
        self.empresa = EmpresaService(db, sessao)


__all__ = ["AuthService", "Database", "Servicos", "Sessao"]
