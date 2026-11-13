"""Gerenciamento de conexões com o SQLite.

Cada operação abre uma conexão curta, executa dentro de uma transação e
**sempre** fecha a conexão ao final (o ``with sqlite3.connect()`` padrão do
Python só faz commit/rollback e deixa a conexão aberta, o que no Windows pode
manter o arquivo .db travado).
"""

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from operix.database import migrations
from operix.errors import OperixError

log = logging.getLogger(__name__)


class ErroBancoDados(OperixError):
    """Falha de acesso ao arquivo do banco (travado, sem permissão, corrompido)."""

    titulo = "Erro no banco de dados"


class Database:
    """Ponto único de acesso ao banco SQLite."""

    def __init__(self, caminho: str | Path, aplicar_migracoes: bool = True):
        self.caminho = Path(caminho)
        if self.caminho.parent and not self.caminho.parent.exists():
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
        if aplicar_migracoes:
            self.migrar()

    def _abrir(self) -> sqlite3.Connection:
        try:
            conn = sqlite3.connect(self.caminho, timeout=10)
        except sqlite3.Error as erro:
            log.exception("Não foi possível abrir o banco %s", self.caminho)
            raise ErroBancoDados(f"Não foi possível abrir o banco de dados:\n{self.caminho}") from erro
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def conexao(self):
        """Abre uma conexão transacional: commit no sucesso, rollback em erro."""
        conn = self._abrir()
        try:
            yield conn
            conn.commit()
        except sqlite3.OperationalError as erro:
            conn.rollback()
            log.exception("Erro operacional no SQLite")
            if "locked" in str(erro).lower():
                raise ErroBancoDados(
                    "O banco de dados está em uso por outro programa. Aguarde alguns segundos e tente novamente."
                ) from erro
            raise
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    # Atalhos de leitura -----------------------------------------------------
    def consultar(self, sql: str, parametros: tuple | dict = ()) -> list[sqlite3.Row]:
        with self.conexao() as conn:
            return conn.execute(sql, parametros).fetchall()

    def consultar_um(self, sql: str, parametros: tuple | dict = ()) -> sqlite3.Row | None:
        with self.conexao() as conn:
            return conn.execute(sql, parametros).fetchone()

    def escalar(self, sql: str, parametros: tuple | dict = ()):
        linha = self.consultar_um(sql, parametros)
        return linha[0] if linha else None

    # Migrações --------------------------------------------------------------
    def migrar(self) -> None:
        """Cria/atualiza o esquema até a versão mais recente."""
        conn = self._abrir()
        try:
            migrations.aplicar(conn)
        except sqlite3.DatabaseError as erro:
            log.exception("Falha ao migrar o banco")
            raise ErroBancoDados(
                "Não foi possível preparar o banco de dados. O arquivo pode estar corrompido.\n"
                f"Arquivo: {self.caminho}"
            ) from erro
        finally:
            conn.close()

    def versao(self) -> int:
        return self.escalar("PRAGMA user_version")
