"""Entidades do domínio.

São ``dataclasses`` simples, criadas a partir das linhas do banco com
``Entidade.da_linha(row)``. A lógica de cálculo (totais, saldo, estoque baixo,
permissões) fica aqui, perto dos dados, e é reaproveitada pela interface e
pelos relatórios PDF.
"""

from dataclasses import dataclass, field, fields
from sqlite3 import Row

from operix.models.enums import Perfil, Permissao, StatusOrdem, TipoItem
from operix.utils import formatters as fmt
from operix.utils import validators as val


class _Entidade:
    """Mixin que constrói a dataclass a partir de um ``sqlite3.Row``/dict."""

    @classmethod
    def da_linha(cls, linha: Row | dict):
        dados = dict(linha)
        nomes = {f.name for f in fields(cls)}  # type: ignore[arg-type]
        return cls(**{k: v for k, v in dados.items() if k in nomes})


@dataclass
class Empresa(_Entidade):
    id: int
    nome: str
    tipo_negocio: str = "Oficina Mecânica"
    cnpj: str | None = None
    telefone: str | None = None
    email: str | None = None
    endereco: str | None = None


@dataclass
class Usuario(_Entidade):
    id: int
    empresa_id: int
    nome: str
    email: str
    perfil: str
    ativo: int = 1

    @property
    def perfil_enum(self) -> Perfil:
        return Perfil(self.perfil)

    def pode(self, permissao: Permissao) -> bool:
        return bool(self.ativo) and permissao in self.perfil_enum.permissoes

    @property
    def e_mecanico(self) -> bool:
        return self.perfil_enum is Perfil.MECANICO


@dataclass
class Cliente(_Entidade):
    id: int
    empresa_id: int
    nome: str
    documento: str
    telefone: str | None = None
    email: str | None = None
    endereco: str | None = None
    observacoes: str | None = None
    ativo: int = 1

    @property
    def documento_formatado(self) -> str:
        return val.formatar_documento(self.documento)

    @property
    def telefone_formatado(self) -> str:
        return val.formatar_telefone(self.telefone)


@dataclass
class Veiculo(_Entidade):
    id: int
    empresa_id: int
    cliente_id: int
    placa: str
    marca: str | None = None
    modelo: str | None = None
    ano: int | None = None
    cor: str | None = None
    km_atual: int = 0
    observacoes: str | None = None
    ativo: int = 1

    @property
    def placa_formatada(self) -> str:
        return val.formatar_placa(self.placa)

    def descricao(self) -> str:
        """Ex.: 'ABC-1234 · Toyota Corolla 2020 (Prata)'."""
        partes = " ".join(p for p in (self.marca, self.modelo, str(self.ano) if self.ano else None) if p)
        if self.cor:
            partes = f"{partes} ({self.cor})" if partes else self.cor
        return f"{self.placa_formatada} · {partes}" if partes else self.placa_formatada


@dataclass
class Peca(_Entidade):
    id: int
    empresa_id: int
    codigo: str
    descricao: str
    unidade: str = "UN"
    custo_centavos: int = 0
    preco_centavos: int = 0
    estoque: float = 0
    estoque_minimo: float = 0
    ativo: int = 1

    @property
    def estoque_baixo(self) -> bool:
        return self.estoque_minimo > 0 and self.estoque <= self.estoque_minimo

    @property
    def margem_percentual(self) -> float | None:
        if not self.custo_centavos:
            return None
        return (self.preco_centavos - self.custo_centavos) / self.custo_centavos * 100


@dataclass
class ServicoCatalogo(_Entidade):
    """Serviço de mão de obra pré-cadastrado (ex.: 'Troca de óleo')."""

    id: int
    empresa_id: int
    descricao: str
    preco_centavos: int = 0
    ativo: int = 1


@dataclass
class ItemOrdem(_Entidade):
    id: int
    ordem_id: int
    tipo: str
    descricao: str
    quantidade: float
    valor_unitario_centavos: int
    peca_id: int | None = None
    servico_id: int | None = None

    @property
    def tipo_enum(self) -> TipoItem:
        return TipoItem(self.tipo)

    @property
    def total_centavos(self) -> int:
        return fmt.total_item(self.quantidade, self.valor_unitario_centavos)


@dataclass
class Pagamento(_Entidade):
    id: int
    ordem_id: int
    valor_centavos: int
    forma: str
    data: str
    usuario_id: int | None = None
    observacao: str | None = None
    usuario_nome: str | None = None


@dataclass
class RegistroHistorico(_Entidade):
    id: int
    ordem_id: int
    status_novo: str
    data: str
    status_anterior: str | None = None
    observacao: str | None = None
    usuario_nome: str | None = None


@dataclass
class MovimentoEstoque(_Entidade):
    id: int
    peca_id: int
    tipo: str
    quantidade: float
    saldo_apos: float
    data: str
    ordem_id: int | None = None
    observacao: str | None = None
    usuario_nome: str | None = None
    ordem_numero: int | None = None


@dataclass
class OrdemServico(_Entidade):
    """Ordem de Serviço. Enquanto está em ``ORCAMENTO`` funciona como orçamento."""

    id: int
    empresa_id: int
    numero: int
    cliente_id: int
    veiculo_id: int
    status: str
    criado_em: str
    mecanico_id: int | None = None
    km_entrada: int | None = None
    defeito_relatado: str | None = None
    diagnostico: str | None = None
    observacoes: str | None = None
    desconto_centavos: int = 0
    estoque_baixado: int = 0
    aprovado_em: str | None = None
    concluido_em: str | None = None
    entregue_em: str | None = None
    cancelado_em: str | None = None
    # Dados "desnormalizados" carregados via JOIN para exibição
    cliente_nome: str | None = None
    cliente_documento: str | None = None
    cliente_telefone: str | None = None
    veiculo_placa: str | None = None
    veiculo_descricao: str | None = None
    mecanico_nome: str | None = None
    itens: list[ItemOrdem] = field(default_factory=list)
    pagamentos: list[Pagamento] = field(default_factory=list)
    historico: list[RegistroHistorico] = field(default_factory=list)

    @property
    def status_enum(self) -> StatusOrdem:
        return StatusOrdem(self.status)

    @property
    def total_pecas(self) -> int:
        return sum(i.total_centavos for i in self.itens if i.tipo == TipoItem.PECA.value)

    @property
    def total_servicos(self) -> int:
        return sum(i.total_centavos for i in self.itens if i.tipo == TipoItem.SERVICO.value)

    @property
    def subtotal(self) -> int:
        return self.total_pecas + self.total_servicos

    @property
    def total(self) -> int:
        return max(self.subtotal - (self.desconto_centavos or 0), 0)

    @property
    def total_pago(self) -> int:
        return sum(p.valor_centavos for p in self.pagamentos)

    @property
    def saldo(self) -> int:
        return max(self.total - self.total_pago, 0)

    @property
    def numero_formatado(self) -> str:
        return f"{self.numero:05d}"
