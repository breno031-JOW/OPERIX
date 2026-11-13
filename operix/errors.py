"""Exceções de negócio do Operix.

Toda exceção derivada de :class:`OperixError` carrega uma mensagem pronta para
ser exibida ao usuário final. A interface captura essas exceções e mostra um
aviso amigável; qualquer outra exceção é tratada como erro inesperado, gravada
no log e exibida de forma genérica (sem fechar a aplicação).
"""


class OperixError(Exception):
    """Base de todos os erros de negócio (mensagem amigável ao usuário)."""

    titulo = "Atenção"

    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


class ValidacaoError(OperixError):
    """Dado informado pelo usuário é inválido (CPF, placa, valor...)."""

    titulo = "Dados inválidos"

    def __init__(self, mensagem: str, campo: str | None = None):
        super().__init__(mensagem)
        self.campo = campo


class RegraNegocioError(OperixError):
    """Operação viola uma regra do processo (ex.: aprovar OS já aprovada)."""

    titulo = "Operação não permitida"


class AutenticacaoError(OperixError):
    """E-mail ou senha incorretos, usuário inativo etc."""

    titulo = "Falha no login"


class AcessoNegadoError(OperixError):
    """O perfil do usuário não tem permissão para a operação."""

    titulo = "Acesso negado"


class NaoEncontradoError(OperixError):
    """Registro não existe (ou pertence a outra empresa)."""

    titulo = "Não encontrado"
