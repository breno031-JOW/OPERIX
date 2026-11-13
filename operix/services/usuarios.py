"""Cadastro de usuários e dados da oficina (somente administradores)."""

import sqlite3

from operix.errors import NaoEncontradoError, RegraNegocioError, ValidacaoError
from operix.models import Empresa, Perfil, Permissao, Usuario
from operix.security import hash_senha, verificar_senha
from operix.services.auth import validar_nova_senha
from operix.services.base import ServicoBase, traduzir_integridade
from operix.utils import validators as val

_ERROS = {"usuarios.email": "Já existe um usuário com este e-mail."}


class UsuarioService(ServicoBase):
    def listar(self, incluir_inativos: bool = True) -> list[Usuario]:
        self.exigir(Permissao.GERENCIAR_USUARIOS)
        sql = "SELECT * FROM usuarios WHERE empresa_id = ?"
        if not incluir_inativos:
            sql += " AND ativo = 1"
        return [Usuario.da_linha(r) for r in self.db.consultar(sql + " ORDER BY nome", (self.empresa_id,))]

    def listar_mecanicos(self) -> list[Usuario]:
        """Usuários que podem ser responsáveis por uma OS (qualquer perfil ativo)."""
        linhas = self.db.consultar(
            "SELECT * FROM usuarios WHERE empresa_id = ? AND ativo = 1 ORDER BY perfil = 'Mecanico' DESC, nome",
            (self.empresa_id,),
        )
        return [Usuario.da_linha(r) for r in linhas]

    def obter(self, usuario_id: int) -> Usuario:
        linha = self.db.consultar_um(
            "SELECT * FROM usuarios WHERE id = ? AND empresa_id = ?", (usuario_id, self.empresa_id)
        )
        if not linha:
            raise NaoEncontradoError("Usuário não encontrado.")
        return Usuario.da_linha(linha)

    def _validar(self, dados: dict) -> tuple[str, str, str]:
        nome = val.validar_texto(dados.get("nome"), "Nome")
        email = val.validar_email(dados.get("email"), obrigatorio=True)
        try:
            perfil = Perfil.por_rotulo(dados.get("perfil") or "").value
        except ValueError:
            raise ValidacaoError("Selecione o perfil de acesso.", "perfil") from None
        return nome, email, perfil

    def criar(self, dados: dict) -> int:
        self.exigir(Permissao.GERENCIAR_USUARIOS)
        nome, email, perfil = self._validar(dados)
        senha = validar_nova_senha(dados.get("senha") or "", dados.get("confirmacao"))
        try:
            with self.db.conexao() as conn:
                return conn.execute(
                    "INSERT INTO usuarios (empresa_id, nome, email, senha_hash, perfil) VALUES (?, ?, ?, ?, ?)",
                    (self.empresa_id, nome, email, hash_senha(senha), perfil),
                ).lastrowid
        except sqlite3.IntegrityError as erro:
            raise traduzir_integridade(erro, _ERROS) from erro

    def atualizar(self, usuario_id: int, dados: dict) -> None:
        self.exigir(Permissao.GERENCIAR_USUARIOS)
        atual = self.obter(usuario_id)
        nome, email, perfil = self._validar(dados)
        if atual.perfil == Perfil.ADMINISTRADOR.value and perfil != atual.perfil:
            self._garantir_outro_admin(usuario_id)
        try:
            with self.db.conexao() as conn:
                conn.execute(
                    "UPDATE usuarios SET nome = ?, email = ?, perfil = ? WHERE id = ? AND empresa_id = ?",
                    (nome, email, perfil, usuario_id, self.empresa_id),
                )
                if dados.get("senha"):
                    senha = validar_nova_senha(dados["senha"], dados.get("confirmacao"))
                    conn.execute("UPDATE usuarios SET senha_hash = ? WHERE id = ?", (hash_senha(senha), usuario_id))
        except sqlite3.IntegrityError as erro:
            raise traduzir_integridade(erro, _ERROS) from erro

    def definir_ativo(self, usuario_id: int, ativo: bool) -> None:
        self.exigir(Permissao.GERENCIAR_USUARIOS)
        alvo = self.obter(usuario_id)
        if not ativo:
            if usuario_id == self.usuario.id:
                raise RegraNegocioError("Você não pode desativar o próprio usuário.")
            if alvo.perfil == Perfil.ADMINISTRADOR.value:
                self._garantir_outro_admin(usuario_id)
        with self.db.conexao() as conn:
            conn.execute(
                "UPDATE usuarios SET ativo = ? WHERE id = ? AND empresa_id = ?",
                (1 if ativo else 0, usuario_id, self.empresa_id),
            )

    def _garantir_outro_admin(self, usuario_id: int) -> None:
        outros = self.db.escalar(
            "SELECT COUNT(*) FROM usuarios WHERE empresa_id = ? AND perfil = 'Administrador' AND ativo = 1 AND id <> ?",
            (self.empresa_id, usuario_id),
        )
        if not outros:
            raise RegraNegocioError("A oficina precisa ter pelo menos um administrador ativo.")

    def alterar_propria_senha(self, senha_atual: str, nova: str, confirmacao: str) -> None:
        """Qualquer perfil pode trocar a própria senha."""
        armazenado = self.db.escalar("SELECT senha_hash FROM usuarios WHERE id = ?", (self.usuario.id,))
        if not verificar_senha(senha_atual or "", armazenado or ""):
            raise ValidacaoError("A senha atual está incorreta.", "senha_atual")
        validar_nova_senha(nova, confirmacao)
        with self.db.conexao() as conn:
            conn.execute("UPDATE usuarios SET senha_hash = ? WHERE id = ?", (hash_senha(nova), self.usuario.id))


class EmpresaService(ServicoBase):
    def obter(self) -> Empresa:
        return Empresa.da_linha(self.db.consultar_um("SELECT * FROM empresas WHERE id = ?", (self.empresa_id,)))

    def atualizar(self, dados: dict) -> Empresa:
        self.exigir(Permissao.CONFIGURAR_EMPRESA)
        valores = (
            val.validar_texto(dados.get("nome"), "Nome da oficina"),
            val.validar_cnpj_opcional(dados.get("cnpj")),
            val.validar_telefone(dados.get("telefone")),
            val.validar_email(dados.get("email")),
            val.validar_texto(dados.get("endereco"), "Endereço", obrigatorio=False, maximo=300),
            self.empresa_id,
        )
        with self.db.conexao() as conn:
            conn.execute(
                "UPDATE empresas SET nome = ?, cnpj = ?, telefone = ?, email = ?, endereco = ? WHERE id = ?", valores
            )
        empresa = self.obter()
        self.sessao.empresa = empresa  # mantém a sessão atualizada
        return empresa
