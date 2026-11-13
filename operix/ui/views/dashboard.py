"""Painel inicial: situação da oficina em tempo real."""

from datetime import datetime

import ttkbootstrap as ttk

from operix.models import Permissao, StatusOrdem
from operix.ui.shell import View
from operix.ui.views.ordens import COLUNAS_ORDENS, abrir_ordem, tag_status
from operix.ui.widgets import CardIndicador, Coluna, TabelaDados, titulo_secao
from operix.utils import formatters as fmt

S = StatusOrdem


class DashboardView(View):
    titulo = "Painel"

    def __init__(self, master, shell):
        hora = datetime.now().hour
        saudacao = "Bom dia" if hora < 12 else "Boa tarde" if hora < 18 else "Boa noite"
        self.subtitulo = f"{saudacao}, {shell.servicos.sessao.usuario.nome.split()[0]}!"
        super().__init__(master, shell)
        if self.pode(Permissao.CRIAR_ORDEM):
            self.botao_acao("＋ Nova OS (F2)", self.novo, "success")
        self.botao_acao("⟳ Atualizar (F5)", self.atualizar, "secondary-outline")

        self.cards = ttk.Frame(self)
        self.cards.pack(fill="x")

        corpo = ttk.Frame(self)
        corpo.pack(fill="both", expand=True, pady=(18, 0))
        corpo.columnconfigure(0, weight=3)
        corpo.columnconfigure(1, weight=2)
        corpo.rowconfigure(1, weight=1)

        mecanico = not self.pode(Permissao.VER_TODAS_ORDENS)
        titulo_secao(corpo, "Minhas ordens de serviço" if mecanico else "Veículos na oficina",
                     "Duplo clique ou Enter para abrir").grid(row=0, column=0, sticky="w")
        self.tabela_os = TabelaDados(corpo, COLUNAS_ORDENS[:6], ao_abrir=self._abrir_os, altura=10)
        self.tabela_os.grid(row=1, column=0, sticky="nsew", padx=(0, 16))

        self.tabela_estoque = None
        if self.pode(Permissao.VER_ESTOQUE):
            titulo_secao(corpo, "Peças com estoque baixo", "Abaixo ou igual ao estoque mínimo").grid(
                row=0, column=1, sticky="w")
            self.tabela_estoque = TabelaDados(corpo, [
                Coluna("codigo", "Código", 80), Coluna("descricao", "Peça", 180),
                Coluna("estoque", "Saldo", 70, "e", fmt.formatar_quantidade),
                Coluna("estoque_minimo", "Mínimo", 70, "e", fmt.formatar_quantidade),
            ], com_busca=False, altura=10)
            self.tabela_estoque.grid(row=1, column=1, sticky="nsew")
        self.atualizar()

    def atualizar(self):
        dados = self.servicos.dashboard.operacional()
        for filho in self.cards.winfo_children():
            filho.destroy()
        cartoes = [
            ("Orçamentos pendentes", dados["orcamentos_pendentes"], "warning", "orcamentos", "aguardando aprovação"),
            ("Em execução", dados["em_execucao"], "primary", "execucao", "aprovadas + em serviço"),
            ("Aguardando peça", dados["aguardando_peca"], "danger", "execucao", "serviço parado"),
            ("Prontos p/ entrega", dados["prontas"], "success", "prontas", "avisar o cliente"),
        ]
        if self.pode(Permissao.VER_ESTOQUE):
            cartoes.append(("Estoque baixo", dados["estoque_baixo"], "danger" if dados["estoque_baixo"] else "info",
                            None, "peças para repor"))
        for indice, (titulo, valor, cor, filtro, detalhe) in enumerate(cartoes):
            acao = (lambda f=filtro: self.shell.navegar("ordens", filtro=f)) if filtro else \
                (lambda: self.shell.navegar("estoque", apenas_baixo=True))
            card = CardIndicador(self.cards, titulo, str(valor), cor, acao, detalhe)
            card.grid(row=0, column=indice, sticky="nsew", padx=(0 if indice == 0 else 12, 0))
            self.cards.columnconfigure(indice, weight=1, uniform="cards")

        abertas = [s for s in S if s.em_aberto]
        self.tabela_os.carregar(self.servicos.ordens.listar(abertas), tag=tag_status)
        if self.tabela_estoque is not None:
            pecas = [vars(p) for p in self.servicos.estoque.listar(apenas_baixo=True)]
            self.tabela_estoque.carregar(pecas, tag=lambda _r: "danger")

    def novo(self):
        if self.pode(Permissao.CRIAR_ORDEM):
            from operix.ui.views.ordens import NovaOrdemDialog

            NovaOrdemDialog(self, self.servicos, ao_criar=lambda oid: (self.atualizar(), abrir_ordem(self, oid,
                                                                                                   self.atualizar)))

    def focar_busca(self):
        self.tabela_os.focar_busca()

    def _abrir_os(self, registro):
        abrir_ordem(self, registro["id"], self.atualizar)
