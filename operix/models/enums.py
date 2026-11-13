"""Enumerações do domínio: status da OS, perfis de acesso e permissões."""

from enum import Enum

from operix.database.migrations import FORMAS_PAGAMENTO  # fonte única da lista

__all__ = ["FORMAS_PAGAMENTO", "Perfil", "Permissao", "StatusOrdem", "TipoItem"]


class StatusOrdem(str, Enum):
    """Ciclo de vida de uma Ordem de Serviço (começa como orçamento)."""

    ORCAMENTO = "ORCAMENTO"
    APROVADA = "APROVADA"
    REPROVADA = "REPROVADA"
    EM_EXECUCAO = "EM_EXECUCAO"
    AGUARDANDO_PECA = "AGUARDANDO_PECA"
    CONCLUIDA = "CONCLUIDA"
    ENTREGUE = "ENTREGUE"
    CANCELADA = "CANCELADA"

    @property
    def rotulo(self) -> str:
        return _ROTULOS[self]

    @property
    def cor(self) -> str:
        """Estilo do ttkbootstrap usado para destacar o status na interface."""
        return _CORES[self]

    @property
    def transicoes(self) -> tuple["StatusOrdem", ...]:
        return _TRANSICOES[self]

    def pode_ir_para(self, destino: "StatusOrdem") -> bool:
        return destino in _TRANSICOES[self]

    @property
    def permite_editar_itens(self) -> bool:
        return self in (StatusOrdem.ORCAMENTO, StatusOrdem.APROVADA, StatusOrdem.EM_EXECUCAO,
                        StatusOrdem.AGUARDANDO_PECA)

    @property
    def permite_pagamento(self) -> bool:
        return self in (StatusOrdem.APROVADA, StatusOrdem.EM_EXECUCAO, StatusOrdem.AGUARDANDO_PECA,
                        StatusOrdem.CONCLUIDA, StatusOrdem.ENTREGUE)

    @property
    def finalizada(self) -> bool:
        return self in (StatusOrdem.ENTREGUE, StatusOrdem.CANCELADA)

    @property
    def em_aberto(self) -> bool:
        """OS que ainda ocupa a oficina (veículo no pátio)."""
        return self in (StatusOrdem.APROVADA, StatusOrdem.EM_EXECUCAO, StatusOrdem.AGUARDANDO_PECA,
                        StatusOrdem.CONCLUIDA)

    @classmethod
    def por_rotulo(cls, rotulo: str) -> "StatusOrdem":
        for status, texto in _ROTULOS.items():
            if texto == rotulo:
                return status
        raise ValueError(rotulo)


_ROTULOS = {
    StatusOrdem.ORCAMENTO: "Orçamento",
    StatusOrdem.APROVADA: "Aprovada",
    StatusOrdem.REPROVADA: "Reprovada",
    StatusOrdem.EM_EXECUCAO: "Em execução",
    StatusOrdem.AGUARDANDO_PECA: "Aguardando peça",
    StatusOrdem.CONCLUIDA: "Pronta p/ entrega",
    StatusOrdem.ENTREGUE: "Entregue",
    StatusOrdem.CANCELADA: "Cancelada",
}

_CORES = {
    StatusOrdem.ORCAMENTO: "warning",
    StatusOrdem.APROVADA: "info",
    StatusOrdem.REPROVADA: "secondary",
    StatusOrdem.EM_EXECUCAO: "primary",
    StatusOrdem.AGUARDANDO_PECA: "danger",
    StatusOrdem.CONCLUIDA: "success",
    StatusOrdem.ENTREGUE: "dark",
    StatusOrdem.CANCELADA: "secondary",
}

# Transições permitidas (máquina de estados da OS)
_TRANSICOES = {
    StatusOrdem.ORCAMENTO: (StatusOrdem.APROVADA, StatusOrdem.REPROVADA, StatusOrdem.CANCELADA),
    StatusOrdem.REPROVADA: (StatusOrdem.ORCAMENTO, StatusOrdem.CANCELADA),
    StatusOrdem.APROVADA: (StatusOrdem.EM_EXECUCAO, StatusOrdem.CANCELADA),
    StatusOrdem.EM_EXECUCAO: (StatusOrdem.AGUARDANDO_PECA, StatusOrdem.CONCLUIDA, StatusOrdem.CANCELADA),
    StatusOrdem.AGUARDANDO_PECA: (StatusOrdem.EM_EXECUCAO, StatusOrdem.CANCELADA),
    StatusOrdem.CONCLUIDA: (StatusOrdem.ENTREGUE, StatusOrdem.EM_EXECUCAO),
    StatusOrdem.ENTREGUE: (),
    StatusOrdem.CANCELADA: (),
}


class TipoItem(str, Enum):
    PECA = "PECA"
    SERVICO = "SERVICO"

    @property
    def rotulo(self) -> str:
        return "Peça" if self is TipoItem.PECA else "Mão de obra"


class Permissao(str, Enum):
    """Permissões verificadas pelos serviços (e usadas para montar o menu)."""

    VER_DASHBOARD = "ver_dashboard"
    VER_FINANCEIRO = "ver_financeiro"
    GERENCIAR_CLIENTES = "gerenciar_clientes"
    CRIAR_ORDEM = "criar_ordem"
    EDITAR_ITENS_ORDEM = "editar_itens_ordem"
    APROVAR_ORDEM = "aprovar_ordem"
    ALTERAR_STATUS_EXECUCAO = "alterar_status_execucao"  # em execução / aguardando peça / concluída
    ENTREGAR_CANCELAR_ORDEM = "entregar_cancelar_ordem"
    VER_TODAS_ORDENS = "ver_todas_ordens"
    REGISTRAR_PAGAMENTO = "registrar_pagamento"
    ESTORNAR_PAGAMENTO = "estornar_pagamento"
    VER_ESTOQUE = "ver_estoque"
    MOVIMENTAR_ESTOQUE = "movimentar_estoque"
    GERENCIAR_CATALOGO = "gerenciar_catalogo"  # cadastro de peças/serviços e preços
    GERENCIAR_USUARIOS = "gerenciar_usuarios"
    CONFIGURAR_EMPRESA = "configurar_empresa"


class Perfil(str, Enum):
    ADMINISTRADOR = "Administrador"
    ATENDENTE = "Atendente"
    MECANICO = "Mecanico"

    @property
    def rotulo(self) -> str:
        return "Mecânico" if self is Perfil.MECANICO else self.value

    @property
    def permissoes(self) -> frozenset[Permissao]:
        return _PERMISSOES[self]

    @classmethod
    def por_rotulo(cls, rotulo: str) -> "Perfil":
        for perfil in cls:
            if perfil.rotulo == rotulo or perfil.value == rotulo:
                return perfil
        raise ValueError(rotulo)


_P = Permissao
_PERMISSOES = {
    Perfil.ADMINISTRADOR: frozenset(Permissao),
    Perfil.ATENDENTE: frozenset({
        _P.VER_DASHBOARD, _P.GERENCIAR_CLIENTES, _P.CRIAR_ORDEM, _P.EDITAR_ITENS_ORDEM, _P.APROVAR_ORDEM,
        _P.ALTERAR_STATUS_EXECUCAO, _P.ENTREGAR_CANCELAR_ORDEM, _P.VER_TODAS_ORDENS,
        _P.REGISTRAR_PAGAMENTO, _P.VER_ESTOQUE, _P.MOVIMENTAR_ESTOQUE,
    }),
    Perfil.MECANICO: frozenset({
        _P.VER_DASHBOARD, _P.ALTERAR_STATUS_EXECUCAO, _P.VER_ESTOQUE,
    }),
}
