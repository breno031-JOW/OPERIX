"""Infraestrutura comum aos serviços de negócio."""

import sqlite3
from dataclasses import dataclass

from operix.database import Database
from operix.errors import AcessoNegadoError, RegraNegocioError
from operix.models import Empresa, Permissao, Usuario


@dataclass
class Sessao:
    """Usuário autenticado e a empresa (oficina) à qual ele pertence."""

    usuario: Usuario
    empresa: Empresa

    @property
    def empresa_id(self) -> int:
        return self.empresa.id

    def pode(self, permissao: Permissao) -> bool:
        return self.usuario.pode(permissao)


class ServicoBase:
    """Classe base: guarda o banco e a sessão e verifica permissões.

    Toda consulta dos serviços filtra por ``empresa_id`` da sessão, garantindo
    o isolamento entre empresas (multiempresa).
    """

    def __init__(self, db: Database, sessao: Sessao):
        self.db = db
        self.sessao = sessao

    @property
    def empresa_id(self) -> int:
        return self.sessao.empresa_id

    @property
    def usuario(self) -> Usuario:
        return self.sessao.usuario

    def exigir(self, permissao: Permissao) -> None:
        """Levanta :class:`AcessoNegadoError` se o perfil não tiver a permissão."""
        if not self.sessao.pode(permissao):
            raise AcessoNegadoError(
                f"Seu perfil de acesso ({self.usuario.perfil_enum.rotulo}) não permite realizar esta operação.\n"
                "Peça a um administrador, se necessário."
            )


def traduzir_integridade(erro: sqlite3.IntegrityError, mensagens: dict[str, str]) -> RegraNegocioError:
    """Converte erros de UNIQUE/CHECK do SQLite em mensagens amigáveis.

    ``mensagens`` mapeia um trecho do texto do erro (ex.: 'clientes.documento')
    para a mensagem exibida ao usuário.
    """
    texto = str(erro)
    for trecho, mensagem in mensagens.items():
        if trecho in texto:
            return RegraNegocioError(mensagem)
    return RegraNegocioError("Não foi possível salvar: os dados violam uma regra de integridade do banco.")
