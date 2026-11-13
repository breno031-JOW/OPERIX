"""Clientes e seus veículos (cadastro, edição, inativação e atalhos para OS/histórico)."""

import ttkbootstrap as ttk

from operix.models import Permissao
from operix.ui.shell import View, exigir_selecao
from operix.ui.widgets import Campo, Coluna, FormularioDialog, TabelaDados, confirmar, notificar, titulo_secao
from operix.utils import validators as val


def abrir_formulario_cliente(parent, servicos, ao_salvar=None, cliente=None) -> None:
    """Cadastro/edição de cliente. ``ao_salvar(cliente_id)`` é chamado após salvar."""
    campos = [
        Campo("nome", "Nome completo / Razão social", obrigatorio=True, largura=40, linha_inteira=True),
        Campo("documento", "CPF ou CNPJ", obrigatorio=True, mascara="documento", largura=22),
        Campo("telefone", "Telefone / WhatsApp", mascara="telefone", largura=22),
        Campo("email", "E-mail", largura=40, linha_inteira=True),
        Campo("endereco", "Endereço", largura=40, linha_inteira=True),
        Campo("observacoes", "Observações", "multilinha", largura=40, linha_inteira=True),
    ]
    valores = None
    if cliente:
        valores = {**cliente, "documento": val.formatar_documento(cliente.get("documento")),
                   "telefone": val.formatar_telefone(cliente.get("telefone"))}

    def salvar(dados):
        if cliente:
            servicos.clientes.atualizar(cliente["id"], dados)
            novo_id = cliente["id"]
        else:
            novo_id = servicos.clientes.criar(dados)
        if ao_salvar:
            ao_salvar(novo_id)

    FormularioDialog(parent, "Editar cliente" if cliente else "Novo cliente", campos, salvar, valores, colunas=2,
                     mensagem_sucesso="Cliente salvo.")


def abrir_formulario_veiculo(parent, servicos, cliente_id: int, ao_salvar=None, veiculo=None) -> None:
    campos = [
        Campo("placa", "Placa", obrigatorio=True, mascara="placa", largura=14,
              dica="Padrão antigo (ABC-1234) ou Mercosul (ABC1D23)"),
        Campo("marca", "Marca", largura=20),
        Campo("modelo", "Modelo", obrigatorio=True, largura=20),
        Campo("ano", "Ano", largura=8),
        Campo("cor", "Cor", largura=14),
        Campo("km_atual", "Km atual", largura=14),
        Campo("observacoes", "Observações", "multilinha", largura=40, linha_inteira=True),
    ]
    valores = None
    if veiculo:
        valores = {**veiculo, "placa": val.formatar_placa(veiculo.get("placa"))}

    def salvar(dados):
        if veiculo:
            servicos.veiculos.atualizar(veiculo["id"], dados)
            novo_id = veiculo["id"]
        else:
            novo_id = servicos.veiculos.criar(cliente_id, dados)
        if ao_salvar:
            ao_salvar(novo_id)

    FormularioDialog(parent, "Editar veículo" if veiculo else "Novo veículo", campos, salvar, valores, colunas=2,
                     mensagem_sucesso="Veículo salvo.")


class ClientesView(View):
    titulo = "Clientes e Veículos"
    subtitulo = "Selecione um cliente para ver os veículos"

    def __init__(self, master, shell):
        super().__init__(master, shell)
        self.botao_acao("＋ Novo cliente (F2)", self.novo, "success")
        self.var_inativos = ttk.BooleanVar(value=False)
        ttk.Checkbutton(self.acoes, text="Mostrar inativos", variable=self.var_inativos, bootstyle="round-toggle",
                        command=self.atualizar).pack(side="left", padx=(14, 0))

        painel = ttk.Panedwindow(self, orient="vertical")
        painel.pack(fill="both", expand=True)

        topo = ttk.Frame(painel)
        self.tabela = TabelaDados(topo, [
            Coluna("nome", "Cliente", 240),
            Coluna("documento", "CPF/CNPJ", 150, formato=val.formatar_documento, esticar=False),
            Coluna("telefone", "Telefone", 140, formato=val.formatar_telefone, esticar=False),
            Coluna("email", "E-mail", 200, formato=lambda e: e or ""),
            Coluna("placas", "Placas", 200,
                   formato=lambda p: ", ".join(val.formatar_placa(x) for x in (p or "").split())),
        ], ao_abrir=self.editar, ao_selecionar=self._cliente_selecionado,
            texto_busca="Nome, CPF/CNPJ, telefone ou placa (F3)")
        self.tabela.pack(fill="both", expand=True)
        for texto, estilo, comando in (("Editar", "primary-outline", self.editar),
                                       ("Inativar/Reativar", "secondary-outline", self.alternar_ativo)):
            ttk.Button(self.tabela.barra, text=texto, bootstyle=estilo,
                       command=lambda c=comando: c()).pack(side="right", padx=(6, 0))
        painel.add(topo, weight=3)

        baixo = ttk.Frame(painel, padding=(0, 12, 0, 0))
        self.lbl_veiculos = titulo_secao(baixo, "Veículos do cliente", "Selecione um cliente acima")
        self.lbl_veiculos.pack(anchor="w")
        self.tabela_veiculos = TabelaDados(baixo, [
            Coluna("placa", "Placa", 100, "center", val.formatar_placa, esticar=False),
            Coluna("marca", "Marca", 120, formato=lambda x: x or ""),
            Coluna("modelo", "Modelo", 180, formato=lambda x: x or ""),
            Coluna("ano", "Ano", 60, "center", lambda x: x or "", esticar=False),
            Coluna("cor", "Cor", 90, formato=lambda x: x or ""),
            Coluna("km_atual", "Km atual", 100, "e", lambda k: f"{k or 0:,}".replace(",", "."), esticar=False),
        ], ao_abrir=self.editar_veiculo, com_busca=False, altura=6)
        self.tabela_veiculos.pack(fill="both", expand=True, pady=(6, 0))
        barra = self.tabela_veiculos.barra
        for texto, estilo, comando in (("＋ Novo veículo", "success", self.novo_veiculo),
                                       ("Editar veículo", "primary-outline", self.editar_veiculo),
                                       ("Histórico", "info-outline", self.historico),
                                       ("Abrir OS", "primary", self.abrir_os),
                                       ("Inativar veículo", "secondary-outline", self.inativar_veiculo)):
            ttk.Button(barra, text=texto, bootstyle=estilo, command=lambda c=comando: c()).pack(side="left",
                                                                                               padx=(0, 6))
        painel.add(baixo, weight=2)
        self.atualizar()
        self.tabela.focar_tabela()

    # ------------------------------------------------------------ clientes
    def atualizar(self):
        self.tabela.carregar(self.servicos.clientes.listar(incluir_inativos=self.var_inativos.get()),
                             tag=lambda c: None if c["ativo"] else "inativo")
        self._cliente_selecionado(self.tabela.selecionado())

    def focar_busca(self):
        self.tabela.focar_busca()

    def novo(self):
        abrir_formulario_cliente(self, self.servicos, ao_salvar=self._salvo)

    def _salvo(self, cliente_id):
        self.atualizar()
        self.tabela.selecionar_id(cliente_id)

    def editar(self, registro=None):
        cliente = registro or exigir_selecao(self.tabela.selecionado(), "Selecione um cliente.")
        abrir_formulario_cliente(self, self.servicos, ao_salvar=self._salvo, cliente=cliente)

    def alternar_ativo(self):
        cliente = exigir_selecao(self.tabela.selecionado(), "Selecione um cliente.")
        ativar = not cliente["ativo"]
        if confirmar(self, f"{'Reativar' if ativar else 'Inativar'} o cliente '{cliente['nome']}'?\n"
                           "O histórico de ordens de serviço é preservado."):
            self.servicos.clientes.definir_ativo(cliente["id"], ativar)
            self.atualizar()
            notificar("Cliente reativado." if ativar else "Cliente inativado.")

    # ------------------------------------------------------------ veículos
    def _cliente_selecionado(self, cliente):
        if not cliente:
            self.tabela_veiculos.carregar([])
            return
        for filho in self.lbl_veiculos.winfo_children()[1:]:
            filho.configure(text=f"{cliente['nome']} · duplo clique para editar")
        self.tabela_veiculos.carregar(self.servicos.veiculos.listar(cliente["id"]))

    def _cliente_atual(self) -> dict:
        return exigir_selecao(self.tabela.selecionado(), "Selecione um cliente na tabela de cima.")

    def novo_veiculo(self):
        cliente = self._cliente_atual()
        abrir_formulario_veiculo(self, self.servicos, cliente["id"], ao_salvar=lambda _id: self.atualizar())

    def editar_veiculo(self, registro=None):
        cliente = self._cliente_atual()
        veiculo = registro or exigir_selecao(self.tabela_veiculos.selecionado(), "Selecione um veículo.")
        abrir_formulario_veiculo(self, self.servicos, cliente["id"], ao_salvar=lambda _id: self.atualizar(),
                                 veiculo=veiculo)

    def inativar_veiculo(self):
        veiculo = exigir_selecao(self.tabela_veiculos.selecionado(), "Selecione um veículo.")
        if confirmar(self, f"Inativar o veículo {val.formatar_placa(veiculo['placa'])}?"):
            self.servicos.veiculos.definir_ativo(veiculo["id"], False)
            self.atualizar()
            notificar("Veículo inativado.")

    def historico(self):
        veiculo = exigir_selecao(self.tabela_veiculos.selecionado(), "Selecione um veículo.")
        self.shell.navegar("historico", placa=veiculo["placa"])

    def abrir_os(self):
        if not self.pode(Permissao.CRIAR_ORDEM):
            return
        from operix.ui.views.ordens import NovaOrdemDialog, abrir_ordem

        cliente = self._cliente_atual()
        veiculo = self.tabela_veiculos.selecionado()
        NovaOrdemDialog(self, self.servicos, ao_criar=lambda oid: abrir_ordem(self, oid),
                        cliente_id=cliente["id"], veiculo_id=veiculo["id"] if veiculo else None)
