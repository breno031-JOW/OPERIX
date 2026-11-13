"""Autenticação e configuração inicial (primeiro acesso)."""

import logging

from operix import config
from operix.database import Database
from operix.errors import AutenticacaoError, RegraNegocioError, ValidacaoError
from operix.models import Empresa, Perfil, Usuario
from operix.security import hash_senha, precisa_rehash, verificar_senha
from operix.services.base import Sessao
from operix.utils import validators as val

log = logging.getLogger(__name__)


def validar_nova_senha(senha: str, confirmacao: str | None = None) -> str:
    if len(senha or "") < config.SENHA_MINIMA:
        raise ValidacaoError(f"A senha deve ter pelo menos {config.SENHA_MINIMA} caracteres.", "senha")
    if confirmacao is not None and senha != confirmacao:
        raise ValidacaoError("A confirmação não confere com a senha digitada.", "confirmacao")
    return senha


class AuthService:
    """Login e criação da primeira oficina/administrador."""

    def __init__(self, db: Database):
        self.db = db

    def precisa_configuracao_inicial(self) -> bool:
        """True quando ainda não existe nenhum usuário cadastrado."""
        return not self.db.escalar("SELECT COUNT(*) FROM usuarios")

    def configurar_primeiro_acesso(
        self, nome_oficina: str, cnpj: str | None, nome_admin: str, email: str, senha: str, confirmacao: str
    ) -> Sessao:
        """Cria a oficina e o usuário administrador na primeira execução."""
        if not self.precisa_configuracao_inicial():
            raise RegraNegocioError("O sistema já foi configurado. Faça login normalmente.")
        nome_oficina = val.validar_texto(nome_oficina, "Nome da oficina")
        cnpj = val.validar_cnpj_opcional(cnpj)
        nome_admin = val.validar_texto(nome_admin, "Seu nome")
        email = val.validar_email(email, obrigatorio=True)
        validar_nova_senha(senha, confirmacao)

        with self.db.conexao() as conn:
            empresa_id = conn.execute(
                "INSERT INTO empresas (nome, cnpj) VALUES (?, ?)", (nome_oficina, cnpj)
            ).lastrowid
            conn.execute(
                "INSERT INTO usuarios (empresa_id, nome, email, senha_hash, perfil) VALUES (?, ?, ?, ?, ?)",
                (empresa_id, nome_admin, email, hash_senha(senha), Perfil.ADMINISTRADOR.value),
            )
        log.info("Configuração inicial concluída para a empresa %s", empresa_id)
        return self.autenticar(email, senha)

    def autenticar(self, email: str, senha: str) -> Sessao:
        email = (email or "").strip().lower()
        if not email or not senha:
            raise AutenticacaoError("Informe o e-mail e a senha.")
        linha = self.db.consultar_um("SELECT * FROM usuarios WHERE email = ?", (email,))
        if not linha or not verificar_senha(senha, linha["senha_hash"]):
            log.warning("Tentativa de login inválida para %s", email)
            raise AutenticacaoError("E-mail ou senha incorretos.")
        if not linha["ativo"]:
            raise AutenticacaoError("Este usuário está desativado. Procure o administrador da oficina.")

        if precisa_rehash(linha["senha_hash"]):
            # Atualiza hashes antigos (menos iterações) de forma transparente
            with self.db.conexao() as conn:
                conn.execute("UPDATE usuarios SET senha_hash = ? WHERE id = ?", (hash_senha(senha), linha["id"]))

        usuario = Usuario.da_linha(linha)
        empresa = Empresa.da_linha(self.db.consultar_um("SELECT * FROM empresas WHERE id = ?", (usuario.empresa_id,)))
        log.info("Login: %s (%s)", usuario.email, usuario.perfil)
        return Sessao(usuario=usuario, empresa=empresa)
