"""Telas de Ordens de Serviço: lista, abertura e janela de detalhes."""

import tkinter as tk

import ttkbootstrap as ttk

from operix.models import FORMAS_PAGAMENTO, Permissao, StatusOrdem, TipoItem
from operix.ui.shell import View, exigir_selecao
from operix.ui.widgets import (
    FONTE,
    Campo,
    Coluna,
    ComboBusca,
    DialogoModal,
    FormularioDialog,
    TabelaDados,
    aplicar_formato_moeda,
    confirmar,
    notificar,
    perguntar_texto,
)
from operix.utils import formatters as fmt
from operix.utils import validators as val

S = StatusOrdem

COLUNAS_ORDENS = [
    Coluna("numero", "Nº OS", 70, "center", lambda n: f"{n:05d}", esticar=False),
    Coluna("status", "Status", 130, formato=lambda s: S(s).rotulo, esticar=False),
    Coluna("cliente_nome", "Cliente", 200),
    Coluna("placa", "Placa", 90, "center", val.formatar_placa, esticar=False),
    Coluna("veiculo", "Veículo", 160),
    Coluna("total", "Total", 110, "e", fmt.formatar_moeda, esticar=False),
    Coluna("mecanico_nome", "Mecânico", 130, formato=lambda n: n or "—"),
    Coluna("criado_em", "Abertura", 130, "center", fmt.formatar_data, esticar=False),
    Coluna("saldo", "Saldo", 110, "e", lambda v: fmt.formatar_moeda(v) if v else "—", esticar=False),
]

FILTROS = {
    "abertas": ("Em aberto", [S.ORCAMENTO, S.APROVADA, S.EM_EXECUCAO, S.AGUARDANDO_PECA, S.CONCLUIDA]),
    "orcamentos": ("Orçamentos", [S.ORCAMENTO]),
    "execucao": ("Em execução", [S.APROVADA, S.EM_EXECUCAO, S.AGUARDANDO_PECA]),
    "prontas": ("Prontas p/ entrega", [S.CONCLUIDA]),
    "finalizadas": ("Finalizadas", [S.ENTREGUE, S.CANCELADA, S.REPROVADA]),
    "todas": ("Todas", None),
}


def tag_status(registro: dict) -> str:
    return S(registro["status"]).cor


def abrir_ordem(parent, ordem_id: int, ao_alterar=None) -> None:
    OrdemDetalheJanela(parent, parent.servicos if hasattr(parent, "servicos") else parent.shell.servicos,
                       ordem_id, ao_alterar)


# ================================================================== lista
class OrdensView(View):
    titulo = "Ordens de Serviço"
    subtitulo = "Orçamentos e serviços da oficina"

    def __init__(self, master, shell, filtro: str = "abertas"):
        super().__init__(master, shell)
        if self.pode(Permissao.CRIAR_ORDEM):
            self.botao_acao("＋ Nova OS (F2)", self.novo, "success")
        self.botao_acao("Abrir OS (Enter)", self.abrir_selecionada, "primary-outline")

        barra = ttk.Frame(self)
        barra.pack(fill="x", pady=(0, 10))
        self.var_filtro = tk.StringVar(value=filtro if filtro in FILTROS else "abertas")
        for chave, (rotulo, _status) in FILTROS.items():
            ttk.Radiobutton(barra, text=rotulo, value=chave, variable=self.var_filtro, bootstyle="toolbutton-outline",
                            command=self.atualizar).pack(side="left", padx=(0, 4))

        self.tabela = TabelaDados(self, COLUNAS_ORDENS, ao_abrir=lambda r: self._abrir(r["id"]),
                                  texto_busca="Buscar por cliente, placa ou nº da OS (F3)")
        self.tabela.pack(fill="both", expand=True)
        legenda = ttk.Frame(self)
        legenda.pack(fill="x", pady=(6, 0))
        for status in S:
            ttk.Label(legenda, text=f"● {status.rotulo}", bootstyle=status.cor, font=(FONTE, 8)).pack(
                side="left", padx=(0, 12))
        self.atualizar()
        self.tabela.focar_tabela()

    def atualizar(self):
        _rotulo, status = FILTROS[self.var_filtro.get()]
        self.tabela.carregar(self.servicos.ordens.listar(status), tag=tag_status)

    def focar_busca(self):
        self.tabela.focar_busca()

    def novo(self):
        if not self.pode(Permissao.CRIAR_ORDEM):
            return
        NovaOrdemDialog(self, self.servicos, ao_criar=lambda oid: (self.atualizar(), self._abrir(oid)))

    def abrir_selecionada(self):
        registro = exigir_selecao(self.tabela.selecionado(), "Selecione uma ordem de serviço na tabela.")
        self._abrir(registro["id"])

    def _abrir(self, ordem_id: int):
        OrdemDetalheJanela(self, self.servicos, ordem_id, self.atualizar)


# ============================================================ abertura de OS
class NovaOrdemDialog(DialogoModal):
    """Abertura de OS: escolhe cliente → veículo, informa km e defeito relatado."""

    def __init__(self, master, servicos, ao_criar, cliente_id: int | None = None, veiculo_id: int | None = None):
        super().__init__(master, "Nova ordem de serviço", resizable=(False, False))
        self.servicos = servicos
        self.ao_criar = ao_criar
        quadro = ttk.Frame(self, padding=20)
        quadro.pack(fill="both", expand=True)
        ttk.Label(quadro, text="Nova ordem de serviço", font=(FONTE, 15, "bold")).grid(row=0, column=0, columnspan=2,
                                                                                    sticky="w")
        ttk.Label(quadro, text="A OS começa como orçamento. Inclua peças e mão de obra na próxima tela.",
                  bootstyle="secondary").grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))

        def rotulo(texto, linha, coluna=0):
            ttk.Label(quadro, text=texto, font=(FONTE, 9, "bold")).grid(row=linha, column=coluna, sticky="w",
                                                                        padx=(0, 16))

        clientes = servicos.clientes.listar()
        rotulo("Cliente * (digite para filtrar)", 2)
        self.cmb_cliente = ComboBusca(
            quadro, [(c["id"], f"{c['nome']}  ·  {val.formatar_documento(c['documento'])}") for c in clientes],
            ao_escolher=self._cliente_escolhido, width=48)
        self.cmb_cliente.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(2, 10))

        rotulo("Veículo *", 4)
        self.cmb_veiculo = ComboBusca(quadro, [], width=48, state="readonly", ao_escolher=self._veiculo_escolhido)
        self.cmb_veiculo.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(2, 10))

        rotulo("Km de entrada", 6)
        rotulo("Mecânico responsável", 6, 1)
        self.ent_km = ttk.Entry(quadro, width=18)
        self.ent_km.grid(row=7, column=0, sticky="w", pady=(2, 10))
        mecanicos = [(None, "— definir depois —")] + [
            (u.id, f"{u.nome} ({u.perfil_enum.rotulo})") for u in servicos.usuarios.listar_mecanicos()]
        self.cmb_mecanico = ComboBusca(quadro, mecanicos, width=28, state="readonly")
        self.cmb_mecanico.set(mecanicos[0][1])
        self.cmb_mecanico.grid(row=7, column=1, sticky="ew", pady=(2, 10))

        rotulo("Defeito relatado pelo cliente", 8)
        self.txt_defeito = tk.Text(quadro, width=56, height=4, wrap="word", font=(FONTE, 10), relief="solid",
                                   borderwidth=1)
        self.txt_defeito.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(2, 10))

        botoes = ttk.Frame(quadro)
        botoes.grid(row=10, column=0, columnspan=2, sticky="ew")
        if servicos.sessao.pode(Permissao.GERENCIAR_CLIENTES):
            ttk.Button(botoes, text="＋ Cadastrar cliente", bootstyle="link", command=self._novo_cliente).pack(
                side="left")
            ttk.Button(botoes, text="＋ Cadastrar veículo", bootstyle="link", command=self._novo_veiculo).pack(
                side="left")
        ttk.Button(botoes, text="Cancelar", bootstyle="secondary-outline", command=self.destroy).pack(side="right")
        ttk.Button(botoes, text="Abrir OS", bootstyle="success", command=self.salvar).pack(side="right", padx=8)

        self.exibir()
        if cliente_id:
            self.cmb_cliente.selecionar_valor(cliente_id)
            if veiculo_id:
                self.cmb_veiculo.selecionar_valor(veiculo_id)
            self.ent_km.focus_set()
        else:
            self.cmb_cliente.focus_set()

    def _cliente_escolhido(self, cliente_id):
        veiculos = self.servicos.veiculos.listar(cliente_id) if cliente_id else []
        self._veiculos = {v["id"]: v for v in veiculos}
        self.cmb_veiculo.definir_opcoes([
            (v["id"], f"{val.formatar_placa(v['placa'])}  ·  {v.get('marca') or ''} {v.get('modelo') or ''}".strip())
            for v in veiculos])
        if len(veiculos) == 1:
            self.cmb_veiculo.selecionar_valor(veiculos[0]["id"])
        else:
            self.cmb_veiculo.set("")

    def _veiculo_escolhido(self, veiculo_id):
        veiculo = getattr(self, "_veiculos", {}).get(veiculo_id)
        if veiculo and not self.ent_km.get():
            self.ent_km.insert(0, str(veiculo.get("km_atual") or ""))

    def _novo_cliente(self):
        from operix.ui.views.clientes import abrir_formulario_cliente

        def criado(cliente_id):
            self.cmb_cliente.definir_opcoes([
                (c["id"], f"{c['nome']}  ·  {val.formatar_documento(c['documento'])}")
                for c in self.servicos.clientes.listar()])
            self.cmb_cliente.selecionar_valor(cliente_id)

        abrir_formulario_cliente(self, self.servicos, ao_salvar=criado)

    def _novo_veiculo(self):
        from operix.ui.views.clientes import abrir_formulario_veiculo

        cliente_id = self.cmb_cliente.valor()
        if not cliente_id:
            raise val.ValidacaoError("Selecione o cliente antes de cadastrar o veículo.")

        def criado(veiculo_id):
            self._cliente_escolhido(cliente_id)
            self.cmb_veiculo.selecionar_valor(veiculo_id)

        abrir_formulario_veiculo(self, self.servicos, cliente_id, ao_salvar=criado)

    def salvar(self):
        if not self.cmb_cliente.valor():
            raise val.ValidacaoError("Selecione o cliente.")
        if not self.cmb_veiculo.valor():
            raise val.ValidacaoError("Selecione o veículo.")
        ordem_id = self.servicos.ordens.criar({
            "cliente_id": self.cmb_cliente.valor(), "veiculo_id": self.cmb_veiculo.valor(),
            "km_entrada": self.ent_km.get(), "mecanico_id": self.cmb_mecanico.valor(),
            "defeito_relatado": self.txt_defeito.get("1.0", "end-1c"),
        })
        self.destroy()
        notificar("Ordem de serviço aberta.")
        self.ao_criar(ordem_id)


# ======================================================= rótulos das ações
def rotulo_acao(atual: StatusOrdem, destino: StatusOrdem) -> tuple[str, str]:
    """Texto e cor do botão que leva a OS de ``atual`` para ``destino``."""
    if destino is S.EM_EXECUCAO:
        texto = {S.APROVADA: "▶ Iniciar execução", S.AGUARDANDO_PECA: "▶ Retomar execução"}.get(
            atual, "↺ Reabrir execução")
        return texto, "primary"
    return {
        S.APROVADA: ("✔ Aprovar orçamento", "success"),
        S.REPROVADA: ("✖ Reprovar", "secondary-outline"),
        S.ORCAMENTO: ("↺ Reabrir orçamento", "warning-outline"),
        S.AGUARDANDO_PECA: ("⏸ Aguardando peça", "warning"),
        S.CONCLUIDA: ("✔ Concluir serviço", "success"),
        S.ENTREGUE: ("🚗 Entregar veículo", "success"),
        S.CANCELADA: ("Cancelar OS", "danger-outline"),
    }[destino]


# ===================================================== janela de detalhes
class OrdemDetalheJanela(DialogoModal):
    def __init__(self, master, servicos, ordem_id: int, ao_alterar=None):
        super().__init__(master, "Ordem de serviço", size=(1140, 740), minsize=(1000, 640))
        self.servicos = servicos
        self.ordem_id = ordem_id
        self.ao_alterar = ao_alterar
        self.pode = servicos.sessao.pode
        self._montar()
        self.recarregar()
        self.exibir()
        self.bind("<F5>", lambda _e: self.recarregar())

    # -------------------------------------------------------------- layout
    def _montar(self):
        raiz = ttk.Frame(self, padding=18)
        raiz.pack(fill="both", expand=True)

        topo = ttk.Frame(raiz)
        topo.pack(fill="x")
        self.lbl_numero = ttk.Label(topo, font=(FONTE, 18, "bold"))
        self.lbl_numero.pack(side="left")
        self.lbl_status = ttk.Label(topo, font=(FONTE, 10, "bold"), padding=(10, 4))
        self.lbl_status.pack(side="left", padx=12)
        self.docs = ttk.Frame(topo)
        self.docs.pack(side="right")

        info = ttk.Frame(raiz)
        info.pack(fill="x", pady=(10, 8))
        self.lbl_cliente = ttk.Label(info, font=(FONTE, 10))
        self.lbl_cliente.grid(row=0, column=0, sticky="w")
        self.lbl_veiculo = ttk.Label(info, font=(FONTE, 10))
        self.lbl_veiculo.grid(row=1, column=0, sticky="w")
        self.lbl_extra = ttk.Label(info, bootstyle="secondary")
        self.lbl_extra.grid(row=2, column=0, sticky="w")

        # A barra de ações é empacotada antes das abas para nunca ser "espremida" para fora da janela
        self.barra_status = ttk.Frame(raiz)
        self.barra_status.pack(side="bottom", fill="x")
        self.abas = ttk.Notebook(raiz, bootstyle="primary")
        self.abas.pack(fill="both", expand=True, pady=(4, 10))
        self._aba_itens()
        self._aba_dados()
        self._aba_pagamentos()
        self._aba_historico()

    def _aba_itens(self):
        aba = ttk.Frame(self.abas, padding=10)
        self.abas.add(aba, text="  Peças e mão de obra  ")
        self.tabela_itens = TabelaDados(aba, [
            Coluna("tipo", "Tipo", 110, formato=lambda t: TipoItem(t).rotulo, esticar=False),
            Coluna("descricao", "Descrição", 360),
            Coluna("quantidade", "Qtd.", 70, "e", fmt.formatar_quantidade, esticar=False),
            Coluna("valor_unitario_centavos", "Valor unit.", 110, "e", fmt.formatar_moeda, esticar=False),
            Coluna("total_centavos", "Total", 120, "e", fmt.formatar_moeda, esticar=False),
        ], com_busca=False, altura=8)
        self.btns_itens = []
        if self.pode(Permissao.EDITAR_ITENS_ORDEM):
            barra = self.tabela_itens.barra
            for texto, estilo, comando in (("＋ Peça do estoque", "primary", self._adicionar_peca),
                                           ("＋ Mão de obra", "primary", self._adicionar_servico),
                                           ("Remover item", "danger-outline", self._remover_item),
                                           ("Desconto", "secondary-outline", self._desconto)):
                botao = ttk.Button(barra, text=texto, bootstyle=estilo, command=comando)
                botao.pack(side="left", padx=(0, 6))
                self.btns_itens.append(botao)
            self.tabela_itens.tree.bind("<Delete>", lambda _e: self._remover_item())

        totais = ttk.Labelframe(aba, text=" Totais ", padding=14, bootstyle="primary")
        totais.pack(side="right", fill="y", padx=(12, 0))
        self.tabela_itens.pack(side="left", fill="both", expand=True)
        self.lbl_totais = {}
        for linha, (chave, rotulo) in enumerate((("pecas", "Peças"), ("servicos", "Mão de obra"),
                                                 ("subtotal", "Subtotal"), ("desconto", "Desconto (−)"),
                                                 ("total", "TOTAL"), ("pago", "Pago"), ("saldo", "Saldo"))):
            negrito = chave in ("total", "saldo")
            ttk.Label(totais, text=rotulo, font=(FONTE, 11 if negrito else 10, "bold" if negrito else "normal")).grid(
                row=linha, column=0, sticky="w", pady=3)
            lbl = ttk.Label(totais, font=(FONTE, 13 if negrito else 10, "bold" if negrito else "normal"),
                            width=14, anchor="e")
            lbl.grid(row=linha, column=1, sticky="e", padx=(16, 0))
            self.lbl_totais[chave] = lbl
            if chave in ("subtotal", "total"):
                ttk.Separator(totais).grid(row=linha, column=0, columnspan=2, sticky="ews")

    def _aba_dados(self):
        aba = ttk.Frame(self.abas, padding=14)
        self.abas.add(aba, text="  Dados e diagnóstico  ")
        aba.columnconfigure(0, weight=1)
        aba.columnconfigure(1, weight=1)
        self.edita_dados = self.pode(Permissao.EDITAR_ITENS_ORDEM)

        ttk.Label(aba, text="Km de entrada", font=(FONTE, 9, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(aba, text="Mecânico responsável", font=(FONTE, 9, "bold")).grid(row=0, column=1, sticky="w")
        self.ent_km = ttk.Entry(aba, width=16)
        self.ent_km.grid(row=1, column=0, sticky="w", pady=(2, 10))
        self.mecanicos = [(None, "— não definido —")] + [
            (u.id, f"{u.nome} ({u.perfil_enum.rotulo})") for u in self.servicos.usuarios.listar_mecanicos()]
        self.cmb_mecanico = ComboBusca(aba, self.mecanicos, width=36, state="readonly")
        self.cmb_mecanico.grid(row=1, column=1, sticky="w", pady=(2, 10))

        self.textos = {}
        for linha, (chave, rotulo) in enumerate((("defeito_relatado", "Defeito relatado pelo cliente"),
                                                 ("diagnostico", "Diagnóstico técnico / serviço executado"),
                                                 ("observacoes", "Observações internas")), start=1):
            ttk.Label(aba, text=rotulo, font=(FONTE, 9, "bold")).grid(row=linha * 2, column=0, columnspan=2,
                                                                     sticky="w")
            texto = tk.Text(aba, height=4, wrap="word", font=(FONTE, 10), relief="solid", borderwidth=1)
            texto.grid(row=linha * 2 + 1, column=0, columnspan=2, sticky="nsew", pady=(2, 10))
            self.textos[chave] = texto
        self.btn_salvar_dados = ttk.Button(aba, text="Salvar dados", bootstyle="success", command=self._salvar_dados)
        self.btn_salvar_dados.grid(row=8, column=1, sticky="e")

    def _aba_pagamentos(self):
        aba = ttk.Frame(self.abas, padding=10)
        self.abas.add(aba, text="  Pagamentos  ")
        self.tabela_pag = TabelaDados(aba, [
            Coluna("data", "Data", 140, "center", fmt.formatar_data, esticar=False),
            Coluna("forma", "Forma", 160),
            Coluna("valor_centavos", "Valor", 120, "e", fmt.formatar_moeda, esticar=False),
            Coluna("usuario_nome", "Recebido por", 160),
            Coluna("observacao", "Observação", 240, formato=lambda o: o or ""),
        ], com_busca=False, altura=8)
        self.tabela_pag.pack(fill="both", expand=True)
        self.btn_pagar = None
        if self.pode(Permissao.REGISTRAR_PAGAMENTO):
            self.btn_pagar = ttk.Button(self.tabela_pag.barra, text="＋ Registrar pagamento", bootstyle="success",
                                        command=self._registrar_pagamento)
            self.btn_pagar.pack(side="left", padx=(0, 6))
        if self.pode(Permissao.ESTORNAR_PAGAMENTO):
            ttk.Button(self.tabela_pag.barra, text="Estornar pagamento", bootstyle="danger-outline",
                       command=self._estornar_pagamento).pack(side="left")

    def _aba_historico(self):
        aba = ttk.Frame(self.abas, padding=10)
        self.abas.add(aba, text="  Histórico  ")
        self.tabela_hist = TabelaDados(aba, [
            Coluna("data", "Data", 140, "center", fmt.formatar_data, esticar=False),
            Coluna("status_anterior", "De", 140, formato=lambda s: S(s).rotulo if s else "—", esticar=False),
            Coluna("status_novo", "Para", 140, formato=lambda s: S(s).rotulo, esticar=False),
            Coluna("usuario_nome", "Usuário", 160, formato=lambda n: n or "—"),
            Coluna("observacao", "Observação", 300, formato=lambda o: o or ""),
        ], com_busca=False, altura=8)
        self.tabela_hist.pack(fill="both", expand=True)

    # ------------------------------------------------------------- dados
    def recarregar(self):
        o = self.ordem = self.servicos.ordens.obter(self.ordem_id)
        status = o.status_enum
        self.title(f"OS {o.numero_formatado} · {o.cliente_nome}")
        self.lbl_numero.configure(text=f"{'Orçamento' if status is S.ORCAMENTO else 'OS'} nº {o.numero_formatado}")
        self.lbl_status.configure(text=status.rotulo.upper(), bootstyle=f"inverse-{status.cor}")
        self.lbl_cliente.configure(
            text=f"👤 {o.cliente_nome}   ·   {val.formatar_documento(o.cliente_documento)}   ·   "
                 f"{val.formatar_telefone(o.cliente_telefone) or 'sem telefone'}")
        self.lbl_veiculo.configure(text=f"🚗 {val.formatar_placa(o.veiculo_placa)}   ·   {o.veiculo_descricao or ''}")
        km = f"{o.km_entrada:,} km".replace(",", ".") if o.km_entrada else "km não informado"
        self.lbl_extra.configure(text=f"Aberta em {fmt.formatar_data(o.criado_em)}   ·   {km}   ·   "
                                      f"Mecânico: {o.mecanico_nome or 'não definido'}")

        self.tabela_itens.carregar([{**vars(i), "total_centavos": i.total_centavos} for i in o.itens])
        for chave, valor in (("pecas", o.total_pecas), ("servicos", o.total_servicos), ("subtotal", o.subtotal),
                             ("desconto", o.desconto_centavos), ("total", o.total), ("pago", o.total_pago),
                             ("saldo", o.saldo)):
            self.lbl_totais[chave].configure(text=fmt.formatar_moeda(valor))
        self.lbl_totais["saldo"].configure(bootstyle="danger" if o.saldo else "success")
        editavel = status.permite_editar_itens
        for botao in self.btns_itens:
            botao.configure(state="normal" if editavel else "disabled")

        # Aba de dados
        self.ent_km.configure(state="normal")
        self.ent_km.delete(0, "end")
        self.ent_km.insert(0, str(o.km_entrada or ""))
        self.cmb_mecanico.configure(state="readonly")
        self.cmb_mecanico.selecionar_valor(o.mecanico_id)
        for chave, widget in self.textos.items():
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.insert("1.0", getattr(o, chave) or "")
        pode_editar = not status.finalizada
        mecanico_responsavel = self.servicos.sessao.usuario.id == o.mecanico_id
        for chave, widget in self.textos.items():
            liberado = pode_editar and (self.edita_dados or (chave == "diagnostico" and mecanico_responsavel))
            widget.configure(state="normal" if liberado else "disabled")
        if not (pode_editar and self.edita_dados):
            self.ent_km.configure(state="disabled")
            self.cmb_mecanico.configure(state="disabled")
        self.btn_salvar_dados.configure(
            state="normal" if pode_editar and (self.edita_dados or mecanico_responsavel) else "disabled")

        self.tabela_pag.carregar([vars(p) for p in o.pagamentos])
        if self.btn_pagar:
            self.btn_pagar.configure(state="normal" if status.permite_pagamento and o.saldo else "disabled")
        self.tabela_hist.carregar([vars(h) for h in reversed(o.historico)])
        self._montar_acoes()

    def _montar_acoes(self):
        for filho in list(self.barra_status.winfo_children()) + list(self.docs.winfo_children()):
            filho.destroy()
        o = self.ordem
        atual = o.status_enum
        ttk.Label(self.barra_status, text="Próximo passo:", bootstyle="secondary").pack(side="left", padx=(0, 8))
        for destino in atual.transicoes:
            if not self._pode_transicao(atual, destino):
                continue
            texto, estilo = rotulo_acao(atual, destino)
            lado = "right" if destino in (S.CANCELADA, S.REPROVADA) else "left"
            ttk.Button(self.barra_status, text=texto, bootstyle=estilo,
                       command=lambda d=destino: self._mudar_status(d)).pack(side=lado, padx=4)
        if not atual.transicoes:
            ttk.Label(self.barra_status, text="OS finalizada — nenhuma ação pendente.", bootstyle="secondary").pack(
                side="left")

        documentos = [("📄 Orçamento", "orcamento")]
        if atual not in (S.ORCAMENTO, S.REPROVADA, S.CANCELADA):
            documentos.append(("📄 Ordem de serviço", "ordem"))
        if o.total_pago:
            documentos.append(("🧾 Recibo", "recibo"))
        for texto, tipo in documentos:
            ttk.Button(self.docs, text=texto, bootstyle="secondary-outline",
                       command=lambda t=tipo: self._gerar_pdf(t)).pack(side="left", padx=(6, 0))

    def _pode_transicao(self, atual: StatusOrdem, destino: StatusOrdem) -> bool:
        if destino in (S.APROVADA, S.REPROVADA) or (atual is S.REPROVADA and destino is S.ORCAMENTO):
            return self.pode(Permissao.APROVAR_ORDEM)
        if destino in (S.ENTREGUE, S.CANCELADA):
            return self.pode(Permissao.ENTREGAR_CANCELAR_ORDEM)
        return self.pode(Permissao.ALTERAR_STATUS_EXECUCAO)

    def _depois_de_alterar(self, mensagem: str | None = None):
        self.recarregar()
        if self.ao_alterar:
            self.ao_alterar()
        if mensagem:
            notificar(mensagem)

    # -------------------------------------------------------------- ações
    def _mudar_status(self, destino: StatusOrdem):
        o = self.ordem
        observacao = None
        permitir_saldo = False
        if destino is S.APROVADA:
            pecas = [i for i in o.itens if i.tipo == TipoItem.PECA.value]
            aviso = f"\n\n{len(pecas)} peça(s) serão baixadas do estoque." if pecas else ""
            if not confirmar(self, f"Aprovar o orçamento de {fmt.formatar_moeda(o.total)}?{aviso}"):
                return
        elif destino in (S.CANCELADA, S.REPROVADA):
            acao = "cancelar esta OS" if destino is S.CANCELADA else "reprovar este orçamento"
            extra = "\nAs peças já baixadas voltarão ao estoque." if o.estoque_baixado else ""
            if not confirmar(self, f"Deseja realmente {acao}?{extra}"):
                return
            observacao = perguntar_texto(self, "Motivo", "Informe o motivo (opcional):")
        elif destino is S.AGUARDANDO_PECA:
            observacao = perguntar_texto(self, "Aguardando peça", "Qual peça está sendo aguardada? (opcional)")
        elif destino is S.ENTREGUE:
            if o.saldo:
                if not confirmar(self, f"Esta OS tem saldo em aberto de {fmt.formatar_moeda(o.saldo)}.\n\n"
                                       "Deseja entregar o veículo mesmo assim (fica registrado como pendência)?",
                                 "Saldo em aberto"):
                    return
                permitir_saldo = True
            elif not confirmar(self, "Confirmar a entrega do veículo ao cliente?"):
                return
        self.servicos.ordens.alterar_status(self.ordem_id, destino, observacao, permitir_saldo)
        self._depois_de_alterar(f"Status alterado para '{destino.rotulo}'.")

    def _adicionar_peca(self):
        SelecionarPecaDialog(self, self.servicos, lambda peca_id, qtd, valor: (
            self.servicos.ordens.adicionar_peca(self.ordem_id, peca_id, qtd, valor),
            self._depois_de_alterar("Peça incluída.")))

    def _adicionar_servico(self):
        catalogo = self.servicos.catalogo.listar()
        precos = {s.descricao: s for s in catalogo}

        def salvar(dados):
            item = precos.get(dados["descricao"])
            self.servicos.ordens.adicionar_servico(self.ordem_id, dados["descricao"], dados["quantidade"] or "1",
                                                   dados["valor"], item.id if item else None)
            self._depois_de_alterar()

        dialogo = FormularioDialog(
            self, "Incluir mão de obra",
            [Campo("descricao", "Serviço (escolha do catálogo ou digite)", "combo_busca", True,
                   [(s.descricao, s.descricao) for s in catalogo], largura=46),
             Campo("quantidade", "Quantidade / horas", largura=12),
             Campo("valor", "Valor unitário (R$)", "moeda", True, largura=16)],
            salvar, valores={"quantidade": "1"}, colunas=2, texto_botao="Incluir",
            mensagem_sucesso="Mão de obra incluída.")
        combo = dialogo.widgets["descricao"]
        entrada_valor = dialogo.widgets["valor"]

        def preencher_preco(_evento=None):
            item = precos.get(combo.get())
            if item and not entrada_valor.get():
                entrada_valor.insert(0, fmt.formatar_moeda(item.preco_centavos, simbolo=False))

        combo.bind("<<ComboboxSelected>>", preencher_preco, add="+")
        # O ComboBusca devolve o valor só se for uma opção; aqui aceitamos texto livre
        combo.valor = combo.get

    def _remover_item(self):
        item = exigir_selecao(self.tabela_itens.selecionado(), "Selecione o item a remover.")
        if confirmar(self, f"Remover o item '{item['descricao']}'?"):
            self.servicos.ordens.remover_item(self.ordem_id, item["id"])
            self._depois_de_alterar("Item removido.")

    def _desconto(self):
        FormularioDialog(
            self, "Desconto", [Campo("valor", "Valor do desconto (R$)", "moeda", largura=18)],
            lambda d: (self.servicos.ordens.definir_desconto(self.ordem_id, d["valor"] or "0"),
                       self._depois_de_alterar()),
            valores={"valor": fmt.formatar_moeda(self.ordem.desconto_centavos, simbolo=False)},
            subtitulo=f"Subtotal atual: {fmt.formatar_moeda(self.ordem.subtotal)}", mensagem_sucesso="Desconto aplicado.")

    def _salvar_dados(self):
        dados = {chave: widget.get("1.0", "end-1c") for chave, widget in self.textos.items()}
        dados.update(km_entrada=self.ent_km.get(), mecanico_id=self.cmb_mecanico.valor())
        self.servicos.ordens.atualizar_dados(self.ordem_id, dados)
        self._depois_de_alterar("Dados da OS salvos.")

    def _registrar_pagamento(self):
        FormularioDialog(
            self, "Registrar pagamento",
            [Campo("valor", "Valor recebido (R$)", "moeda", True, largura=18),
             Campo("forma", "Forma de pagamento", "combo", True, list(FORMAS_PAGAMENTO), largura=22),
             Campo("observacao", "Observação (ex.: parcela 1/2)", largura=44, linha_inteira=True)],
            lambda d: (self.servicos.ordens.registrar_pagamento(self.ordem_id, d["valor"], d["forma"],
                                                                d["observacao"]),
                       self._depois_de_alterar()),
            valores={"valor": fmt.formatar_moeda(self.ordem.saldo, simbolo=False), "forma": "PIX"}, colunas=2,
            subtitulo=f"Saldo em aberto: {fmt.formatar_moeda(self.ordem.saldo)}", texto_botao="Registrar",
            mensagem_sucesso="Pagamento registrado.")

    def _estornar_pagamento(self):
        pagamento = exigir_selecao(self.tabela_pag.selecionado(), "Selecione o pagamento a estornar.")
        if confirmar(self, f"Estornar o pagamento de {fmt.formatar_moeda(pagamento['valor_centavos'])}?"):
            self.servicos.ordens.estornar_pagamento(self.ordem_id, pagamento["id"])
            self._depois_de_alterar("Pagamento estornado.")

    def _gerar_pdf(self, tipo: str):
        from operix.reports.pdf import abrir_arquivo, gerar_pdf_ordem

        caminho = gerar_pdf_ordem(self.servicos.ordens.obter(self.ordem_id), self.servicos.empresa.obter(), tipo)
        notificar(f"PDF salvo em {caminho.parent}", "Documento gerado", "info")
        abrir_arquivo(caminho)


# ================================================= seleção de peça (estoque)
class SelecionarPecaDialog(DialogoModal):
    """Busca a peça no estoque, informa quantidade e valor e inclui na OS."""

    def __init__(self, master, servicos, ao_incluir):
        super().__init__(master, "Incluir peça do estoque", size=(820, 560))
        self.ao_incluir = ao_incluir
        quadro = ttk.Frame(self, padding=16)
        quadro.pack(fill="both", expand=True)
        ttk.Label(quadro, text="Incluir peça do estoque", font=(FONTE, 14, "bold")).pack(anchor="w")
        ttk.Label(quadro, text="Digite para buscar · ↓ para ir à tabela · Enter para escolher",
                  bootstyle="secondary").pack(anchor="w", pady=(0, 8))
        pecas = [vars(p) for p in servicos.estoque.listar()]
        self.tabela = TabelaDados(quadro, [
            Coluna("codigo", "Código", 90, esticar=False), Coluna("descricao", "Descrição", 300),
            Coluna("estoque", "Disponível", 90, "e", fmt.formatar_quantidade, esticar=False),
            Coluna("unidade", "Un.", 50, "center", esticar=False),
            Coluna("preco_centavos", "Preço", 110, "e", fmt.formatar_moeda, esticar=False),
        ], ao_abrir=lambda _r: self.ent_qtd.focus_set(), ao_selecionar=self._selecionada, altura=10,
            texto_busca="Código ou descrição")
        self.tabela.pack(fill="both", expand=True)
        self.tabela.carregar(pecas, tag=lambda p: "danger" if p["estoque"] <= 0 else None)

        rodape = ttk.Frame(quadro)
        rodape.pack(fill="x", pady=(12, 0))
        ttk.Label(rodape, text="Quantidade", font=(FONTE, 9, "bold")).pack(side="left")
        self.ent_qtd = ttk.Entry(rodape, width=8, justify="right")
        self.ent_qtd.insert(0, "1")
        self.ent_qtd.pack(side="left", padx=(6, 18))
        ttk.Label(rodape, text="Valor unitário (R$)", font=(FONTE, 9, "bold")).pack(side="left")
        self.ent_valor = ttk.Entry(rodape, width=12, justify="right")
        aplicar_formato_moeda(self.ent_valor)
        self.ent_valor.pack(side="left", padx=6)
        ttk.Button(rodape, text="Cancelar", bootstyle="secondary-outline", command=self.destroy).pack(side="right")
        ttk.Button(rodape, text="Incluir na OS", bootstyle="success", command=self._incluir).pack(side="right",
                                                                                                   padx=8)
        for entry in (self.ent_qtd, self.ent_valor):
            entry.bind("<Return>", lambda _e: self._incluir())
        self.exibir()
        self.tabela.focar_busca()

    def _selecionada(self, peca):
        if peca:
            self.ent_valor.delete(0, "end")
            self.ent_valor.insert(0, fmt.formatar_moeda(peca["preco_centavos"], simbolo=False))

    def _incluir(self):
        peca = exigir_selecao(self.tabela.selecionado(), "Selecione a peça na tabela.")
        self.ao_incluir(peca["id"], self.ent_qtd.get(), self.ent_valor.get())
        self.destroy()
